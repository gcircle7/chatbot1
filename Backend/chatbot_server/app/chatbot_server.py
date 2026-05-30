import os
import signal
import threading
import time
from datetime import datetime

from app.chatbot import Chatbot
from _utils.common import model, CHATBOT_NAME
from app.characters import system_role, instruction
from app.request_service import get_request_queue, request_status_update
from app.session_service import get_valid_sessions, set_expire_sessions
from app.response_service import response_send

def _shutdown_immediately(signum, frame) -> None:
    print(f"\nChatbotServer 종료... \nsignum={signum}, frame={frame}")
    os._exit(0)


### 챗봇 서버 코드 ###
class ChatbotServer:
    """메인 스레드에서 일정 주기로 챗봇 실행을 돌린다."""

    def __init__(
        self
    ):
        self._is_running = True
        self._chatbot: dict[str, Chatbot] = {}
        self._stop = threading.Event()
        self.session_active_list = []    

        # # 데몬 구동
        # bg_thread = threading.Thread(target=self._background_task)
        # bg_thread.daemon = True
        # bg_thread.start()
        
    def _background_task(self):
        while True:
            # self.save_chat()
            # self.context = [{"role": v['role'], "content": v['content'], "saved": True} for v in self.context]
            # self.memoryManager.build_memory()            
            time.sleep(3600)  # 1시간마다 반복
            #time.sleep(120)  # 테스트 용도

    def _generate_chatbot(self) -> None:
        sessions = get_valid_sessions()
        if not sessions:   
            return

        now = datetime.now()
        session_expire_ids = []
        session_active_ids = []
        for session in sessions:
            # expire 시각이 현재 시각보다 작으면 실행 (세션 만료 상태로 간주)
            expires_at = session.get("expires_at")
            if expires_at is not None and now > expires_at:
                session_expire_ids.append(session["session_id"])       
            else:
                session_active_ids.append(session["session_id"])     

        set_expire_sessions(session_expire_ids)

        self.session_active_list = session_active_ids
        for session in sessions:
            if session["session_id"] not in session_active_ids:
                continue

            if session["session_id"] not in self._chatbot:
                adjusted_system_role = system_role.format(user=session["display_name"])

                self._chatbot[session["session_id"]] = Chatbot(
                    model=model.advanced,
                    system_role=adjusted_system_role,
                    instruction=instruction,
                    db_user_id=session["db_user_id"],
                    session_id=session["session_id"],
                    user_name=session["display_name"],
                    assistant=CHATBOT_NAME,
                )

    def _sleep(self, seconds: float) -> bool:
        """짧은 구간으로 나눠 대기. True면 종료 요청."""
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if self._stop.is_set() or not self._is_running:
                return True
            remaining = deadline - time.monotonic()
            time.sleep(min(0.1, remaining))
        return self._stop.is_set() or not self._is_running

    def _work_loop(self) -> None:
        # active session에 대한 챗봇 생성
        self._generate_chatbot() 

        print(f"챗봇 서비스를 시작합니다 .... 시작 챗봇수={len(self.session_active_list)}")

        _no_request_loop_count = 0
        while self._is_running and not self._stop.is_set():
            try:
                request = get_request_queue() 
                # print("request", request)
                if not request["ok"] or request["request"] is None:
                    # 활성화된 세션 중에서 요청이 없는 세션 제거
                    for session_id in list(self._chatbot.keys()):
                        if session_id not in self.session_active_list:
                            self._chatbot.pop(session_id, None)
                            print(f"세션 종료 챗봇(session_id={session_id}) 제거")

                    _no_request_loop_count += 1
                    if _no_request_loop_count > 11:
                        print("request 없음 --- 1분 경과")
                        _no_request_loop_count = 0
                    self._sleep(5)
                    continue 

                request_id = request["request"]["id"]
                session_id = request["request"]["session_id"] 
                if session_id not in self.session_active_list:
                    # active session 에 대한 챗봇 생성 상태 업데이트
                    self._generate_chatbot() 
                    if session_id not in self.session_active_list:
                        print(f"session_id={session_id}에 세션이 종료되어 요청을 'failed'로 처리합니다. (request_id={request_id})")
                        request_status_update(request_id, "failed", error_message="session_id에 해당하는 챗봇이 없어 요청을 'failed'로 처리합니다.")
                        continue
                    
                    print(f"세션 확인 .... 현재 챗봇수={len(self.session_active_list)}")

                if session_id not in self._chatbot:
                    print(f"session_id={session_id}에 해당하는 챗봇이 없어 요청을 'failed'로 처리합니다. (request_id={request_id})")
                    request_status_update(request_id, "failed", error_message="session_id에 해당하는 챗봇이 없어 요청을 'failed'로 처리합니다.")
                    continue

                cb_bot = self._chatbot[session_id]
                cb_bot.add_user_message(request["request"]["request_message"])
                cb_bot.save_one_chat()  # 챗봇 내역 DB에 저장

                tf, response = cb_bot.send_request()
                if not tf:
                    error_message=response["choices"][0]["message"]["content"]
                    request_status_update(request_id, "failed", error_message=error_message) 
                else:
                    # print("response :", response)   
                    # 챗봇 응답 메모리에 추가
                    cb_bot.add_ai_message(response)

                    # Client 전달용 테이블에 챗봇 응답 저장
                    response_message=response["choices"][0]["message"]["content"]
                    retval = response_send(request_id, session_id, status="responsed", response_message=response_message) 
                    # 챗봇 응답 상태 업데이트 (completed or failed)
                    if not retval["ok"]:
                        request_status_update(request_id, "failed", error_message=retval["error"])
                    else:
                        request_status_update(request_id, "completed")

                cb_bot.handle_token_limit(response)
                cb_bot.clean_context()
                cb_bot.save_one_chat()  #  instruction 제거(clean_context) 후 챗봇 내역 DB에 저장 
            except Exception as e:
                import traceback
                print("오류 발생:", e)
                traceback.print_exc()

            if self._stop.is_set():
                return

    def run(self) -> None:
        signal.signal(signal.SIGINT, _shutdown_immediately)
        signal.signal(signal.SIGTERM, _shutdown_immediately)
        self._is_running = True
        self._stop.clear()
        try:
            self._work_loop()
        finally:
            self._chatbot = {}

    def stop(self) -> None:
        self._is_running = False
        self._stop.set()
