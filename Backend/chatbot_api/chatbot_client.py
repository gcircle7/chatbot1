import time
import logging

from db import get_connection
from broker import get_broker, CHANNEL_REQUESTS, response_channel

logger = logging.getLogger(__name__)


class ChatbotClient:

    def __init__(self, db_user_id, session_id):
        self.db_user_id = db_user_id
        self.session_id = session_id

    def add_user_message(self, user_message):
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO cb_request_queue
                        (db_user_id, session_id, status, request_message, created_at)
                    VALUES (%s, %s, %s, %s, NOW())
                    """,
                    (self.db_user_id, self.session_id, "pending", user_message),
                )
                request_id = cur.lastrowid

        # 워커에 새 요청 도착을 통지(폴링 대체). 실패해도 워커의 fallback 폴링이 처리.
        try:
            get_broker().publish(
                CHANNEL_REQUESTS,
                {"request_id": request_id, "session_id": self.session_id},
            )
        except Exception:
            logger.warning("요청 통지 실패 — 워커 폴링이 대신 처리합니다.", exc_info=True)

        return request_id

    def _retrieve_request_status(self, request_id):
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM cb_request_queue WHERE id = %s",
                    (request_id,),
                )
                return cur.fetchone() or None

    def _retrieve_response(self, request_id):
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM cb_response_queue WHERE request_id = %s",
                    (request_id,),
                )
                return cur.fetchone() or None

    def _response_received(self, response_id):
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE cb_response_queue SET status = %s WHERE id = %s",
                    ("received", response_id),
                )

    def get_response_content(self, request_id) -> tuple[str, str, str]:
        """응답을 기다린다.

        브로커 통지(chat:response:{id})로 즉시 깨어나되, 통지 유실/늦은 구독에
        대비해 매 주기 DB 상태를 확인한다(DB 가 source of truth).
        """
        max_polling_time = 20
        start_time = time.time()

        subscription = None
        try:
            subscription = get_broker().subscribe(response_channel(request_id))
        except Exception:
            logger.warning("응답 채널 구독 실패 — 폴링으로 대기합니다.", exc_info=True)

        try:
            while True:
                elapsed_time = time.time() - start_time
                if elapsed_time > max_polling_time:
                    logger.warning("응답 대기 타임아웃 — request_id=%s", request_id)
                    return "failed", "", "대기 시간 초과(retrieve)입니다."

                # 통지를 최대 1초 대기(오면 즉시 반환). 없으면 1초 주기 폴링.
                if subscription is not None:
                    subscription.get(timeout=1.0)
                else:
                    time.sleep(1)

                request_chk = self._retrieve_request_status(request_id)
                if request_chk is None:
                    return "failed", "", "요청이 존재하지 않습니다."

                status = request_chk["status"]
                if status == "completed":
                    logger.info("응답 수신 — request_id=%s (경과 %.2fs)", request_id, elapsed_time)
                    break
                if status in ("failed", "cancelled", "incomplete"):
                    return "failed", "", request_chk.get("error_message")
                # pending / in_progress → 계속 대기

            response = self._retrieve_response(request_id)
            if response is None:
                return "failed", "", "등록된 답변이 존재하지 않습니다."

            self._response_received(response["id"])
            return "completed", response["response_message"], ""
        finally:
            if subscription is not None:
                subscription.close()
