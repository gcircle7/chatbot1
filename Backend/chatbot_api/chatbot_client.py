import time
from db import get_connection
import json 

class ChatbotClient:
    
    def __init__(self, db_user_id, session_id):
        self.db_user_id = db_user_id
        self.session_id = session_id

    def add_user_message(self, user_message):
        # self.context.append({"role": "user", "content": user_message, "saved" : False})

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
                conn.commit()
        return request_id

    def _retrieve_request_status(self, request_id):
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM cb_request_queue WHERE id = %s 
                    """,
                    (request_id,),
                )
                print(f"retrieve_request cur.query: {cur.query}")
                return cur.fetchone() or None

    def _retrieve_response(self, request_id):
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM cb_response_queue WHERE request_id = %s 
                    """,
                    (request_id,),
                )
                return cur.fetchone() or None

    def _response_received(self, response_id):
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE cb_response_queue SET status = %s WHERE id = %s
                    """,
                    ("received", response_id),
                )
                conn.commit()

    def get_response_content(self, request_id) -> tuple[dict, str]:
        max_polling_time = 20
        start_time = time.time()
        retrieved_status = ''
        while True:
            elapsed_time = time.time() - start_time
            if elapsed_time > max_polling_time:
                retrieved_status = 'failed'
                return retrieved_status, "", "대기 시간 초과(retrieve)입니다."

            # 요청 상태 조회
            request_chk = self._retrieve_request_status(request_id)
            if request_chk is None:
                retrieved_status = 'failed'
                return retrieved_status, "", "요청이 존재하지 않습니다."
            else:
                if request_chk['status'] == "completed":
                    retrieved_status = request_chk['status']
                    print(f"request_chk: {retrieved_status}, 경과:{elapsed_time: .2f}초 / Max {max_polling_time} 초") 
                    break
                elif request_chk['status'] in ["failed", "cancelled", "incomplete"]:
                    return 'failed', "", request_chk['error_message']
                elif request_chk['status'] in ["in_progress"]:
                    print(f"request_chk: {request_chk['status']}, 경과:{elapsed_time: .2f}초") 
                else:  
                    print(f"request_chk: {request_chk['status']}, 경과:{elapsed_time: .2f}초") 
                time.sleep(1)    
        # 응답 내용 조회
        response = self._retrieve_response(request_id)
        if response is None:
            retrieved_status = 'failed'
            return retrieved_status, "", "등록된 답변이 존재하지 않습니다."
        # 응답 수신 처리
        self._response_received(response['id']) 
        return retrieved_status, response['response_message'], ""
