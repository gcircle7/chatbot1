"""챗봇 워커 서버.

구조:
 - 디스패처(메인 루프)가 브로커 통지(또는 짧은 폴링)를 받아 claim_request() 로
   pending 요청을 가용 슬롯만큼 집어 ThreadPoolExecutor 에 제출한다.
 - 워커는 스테이트리스: 요청마다 Chatbot 을 생성(컨텍스트는 DB 에서 로드)해 처리하고 폐기한다.
 - 같은 세션의 요청은 세션 락으로 직렬화하여 메시지 순서를 보장한다.
 - 완료 시 브로커로 응답 도착을 통지(chat:response:{request_id})하여 API 의 폴링을 대체한다.
"""

import logging
import os
import signal
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from app.chatbot import Chatbot
from _utils.common import model, CHATBOT_NAME
from app.characters import system_role, instruction
from app.request_service import claim_request, request_status_update
from app.session_service import get_session_if_active
from app.response_service import response_send
from app.queue_maintenance import cleanup_old_queue_rows
from broker import get_broker, CHANNEL_REQUESTS, response_channel

logger = logging.getLogger(__name__)

_GC_INTERVAL_SEC = 300  # 큐 GC 주기(5분)
_NOTIFY_WAIT_SEC = 2.0  # 통지 대기(브로커) — 유실 대비 fallback 폴링 간격
_POLL_WAIT_SEC = 0.5    # 브로커 미사용 시 폴링 간격


class ChatbotServer:
    """디스패처 + 워커 풀."""

    def __init__(self):
        self._is_running = True
        self._stop = threading.Event()

        self._concurrency = int(os.environ.get("WORKER_CONCURRENCY", "4"))
        self._executor = ThreadPoolExecutor(
            max_workers=self._concurrency, thread_name_prefix="cb-worker"
        )

        # 세션별 직렬화 락 (같은 세션의 메시지 순서 보장)
        self._session_locks: dict[int, threading.Lock] = defaultdict(threading.Lock)
        self._session_locks_guard = threading.Lock()

        # 처리 중(in-flight) request_id — 가용 슬롯 계산용
        self._inflight: set[int] = set()
        self._inflight_guard = threading.Lock()

        self._broker = None
        self._gc_days = int(os.environ.get("QUEUE_GC_DAYS", "1"))
        self._last_gc = 0.0

        # 장기기억 빌드(#8)는 추후 별도 개발 예정 — 현재 비활성.
        # 아래 데몬 시작을 열면 _background_task 가 주기 실행된다(현재는 호출하지 않음).
        # bg = threading.Thread(target=self._background_task, daemon=True)
        # bg.start()

    def _background_task(self) -> None:
        """[비활성/추후 개발] 장기기억 빌드 스케줄러 골격(#8).

        전날 대화를 요약해 Pinecone/Mongo 에 적재(MemoryManager.build_memory)하는
        주기 작업 자리. 스테이트리스 워커에 맞춰 세션 단위가 아니라 사용자 단위
        배치로 재설계 예정이라 현재는 호출하지 않는다(기존 비활성 상태 유지).
        """
        while True:
            # 예: 활성 사용자별로 MemoryManager(...).build_memory() 수행
            time.sleep(3600)  # 1시간 주기

    # ----- 보조 -----
    def _session_lock(self, session_id: int) -> threading.Lock:
        with self._session_locks_guard:
            return self._session_locks[session_id]

    def _inflight_count(self) -> int:
        with self._inflight_guard:
            return len(self._inflight)

    def _notify(self, request_id: int, status: str) -> None:
        if self._broker is not None:
            self._broker.publish(
                response_channel(request_id),
                {"request_id": request_id, "status": status},
            )

    # ----- 메인 루프 -----
    def _work_loop(self) -> None:
        logger.info("챗봇 워커 시작 — 동시성=%d", self._concurrency)

        subscription = None
        try:
            self._broker = get_broker()
            if self._broker.ping():
                subscription = self._broker.subscribe(CHANNEL_REQUESTS)
                logger.info("브로커 구독 시작: %s", CHANNEL_REQUESTS)
            else:
                logger.warning("브로커 연결 실패 — 폴링 모드로 동작합니다.")
                self._broker = None
        except Exception:
            logger.exception("브로커 초기화 실패 — 폴링 모드로 동작합니다.")
            self._broker = None

        while self._is_running and not self._stop.is_set():
            try:
                dispatched = self._dispatch_available()
                self._maybe_gc()

                if dispatched == 0:
                    # 처리할 게 없으면 통지를 기다린다(오면 즉시 깨어남).
                    if subscription is not None:
                        subscription.get(timeout=_NOTIFY_WAIT_SEC)
                    else:
                        self._sleep(_POLL_WAIT_SEC)
                # dispatched > 0 이면 곧장 다음 루프에서 추가 픽업 시도
            except Exception:
                logger.exception("워커 디스패처 루프 오류")
                self._sleep(1)

            if self._stop.is_set():
                break

        if subscription is not None:
            subscription.close()
        logger.info("챗봇 워커 종료")

    def _dispatch_available(self) -> int:
        """가용 슬롯만큼 pending 요청을 집어 워커 풀에 제출. 제출 건수를 반환."""
        free = self._concurrency - self._inflight_count()
        count = 0
        for _ in range(max(0, free)):
            result = claim_request()
            if not result.get("ok") or result.get("request") is None:
                break
            req = result["request"]
            with self._inflight_guard:
                self._inflight.add(req["id"])
            self._executor.submit(self._process_request, req)
            count += 1
        return count

    def _process_request(self, req: dict) -> None:
        request_id = req["id"]
        session_id = req["session_id"]
        try:
            # 같은 세션은 직렬화(메시지 순서 보장). 다른 세션끼리는 병렬.
            with self._session_lock(session_id):
                session = get_session_if_active(session_id)
                if session is None:
                    logger.warning(
                        "세션 비활성/만료 — request_id=%s session_id=%s → failed",
                        request_id, session_id,
                    )
                    request_status_update(
                        request_id, "failed",
                        error_message="세션이 활성 상태가 아니라 요청을 처리할 수 없습니다.",
                    )
                    self._notify(request_id, "failed")
                    return

                # 스테이트리스: 매 요청마다 컨텍스트를 DB 에서 로드해 Chatbot 생성
                adjusted_system_role = system_role.format(user=session["display_name"])
                bot = Chatbot(
                    model=model.advanced,
                    system_role=adjusted_system_role,
                    instruction=instruction,
                    db_user_id=session["db_user_id"],
                    session_id=session_id,
                    user_name=session["display_name"],
                    assistant=CHATBOT_NAME,
                )

                bot.add_user_message(req["request_message"])
                bot.save_one_chat()

                tf, response = bot.send_request()
                if not tf:
                    error_message = response["choices"][0]["message"]["content"]
                    request_status_update(request_id, "failed", error_message=error_message)
                    self._notify(request_id, "failed")
                    return

                bot.add_ai_message(response)
                response_message = response["choices"][0]["message"]["content"]
                logger.info("응답 생성 — request_id=%s: %s", request_id, response_message)

                retval = response_send(
                    request_id, session_id, status="responsed",
                    response_message=response_message,
                )
                if not retval.get("ok"):
                    request_status_update(request_id, "failed", error_message=retval.get("error"))
                    self._notify(request_id, "failed")
                    return

                request_status_update(request_id, "completed")
                bot.handle_token_limit(response)
                bot.clean_context()
                bot.save_one_chat()  # instruction 제거 후 정제된 내역 저장
                self._notify(request_id, "completed")
        except Exception:
            logger.exception("요청 처리 오류 — request_id=%s", request_id)
            try:
                request_status_update(
                    request_id, "failed",
                    error_message="요청 처리 중 서버 오류가 발생했습니다.",
                )
                self._notify(request_id, "failed")
            except Exception:
                logger.exception("실패 상태 업데이트 오류 — request_id=%s", request_id)
        finally:
            with self._inflight_guard:
                self._inflight.discard(request_id)

    def _maybe_gc(self) -> None:
        now = time.monotonic()
        if now - self._last_gc < _GC_INTERVAL_SEC:
            return
        self._last_gc = now
        deleted = cleanup_old_queue_rows(self._gc_days)
        if deleted:
            logger.info("큐 정리: %d건 삭제(%d일 경과분)", deleted, self._gc_days)

    def _sleep(self, seconds: float) -> bool:
        """짧은 구간으로 나눠 대기. True면 종료 요청."""
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if self._stop.is_set() or not self._is_running:
                return True
            remaining = deadline - time.monotonic()
            time.sleep(min(0.1, max(0.0, remaining)))
        return self._stop.is_set() or not self._is_running

    # ----- 수명주기 -----
    def run(self) -> None:
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)
        self._is_running = True
        self._stop.clear()
        try:
            self._work_loop()
        finally:
            self._executor.shutdown(wait=False)

    def _handle_signal(self, signum, frame) -> None:
        logger.info("종료 신호 수신 signum=%s", signum)
        self.stop()
        os._exit(0)

    def stop(self) -> None:
        self._is_running = False
        self._stop.set()
