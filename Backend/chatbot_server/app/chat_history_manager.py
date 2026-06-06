"""채팅 내역 관리."""
import logging
from _utils.db import get_connection

logger = logging.getLogger(__name__)

class ChatHistoryManager:
    def __init__(self, **kwargs):
        self.db_user_id = kwargs["db_user_id"]
        self.session_id = kwargs["session_id"]

    def get_chat_history(self) -> dict:
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT h.id, h.db_user_id, h.session_id, h.role, h.content, h.created_at
                        FROM cb_chat_history h
                        WHERE h.db_user_id  = %s
                          AND h.session_id = %s
                        ORDER BY h.created_at ASC
                        """,
                        (self.db_user_id, self.session_id),
                    )
                    chat_history = cur.fetchall()
                    return {"ok": True, "chat_history": chat_history}
        except Exception:
            logger.exception("채팅 내역 조회 실패(get_chat_history)")
            return {"ok": False, "chat_history": []}

    def save_one_chat(self, last_context):     
        try:  
            with get_connection() as conn:
                with conn.cursor() as cur:     
                    cur.execute("START TRANSACTION")
                    cur.execute(
                        """
                        INSERT INTO cb_chat_history (db_user_id, session_id, role, content)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (   self.db_user_id, 
                            self.session_id, 
                            last_context["role"], 
                            last_context["content"]
                        ),
                    )
                    cur.execute("COMMIT")
                    conn.commit()
                    last_context["saved"] = True
                    return {"ok": True, "last_context": last_context}
        except Exception as e:
            logger.exception("채팅 저장 실패(save_one_chat)")
            return {"ok": False, "error": "데이터베이스 등록에 실패했습니다.(save_one_chat) " + str(e)}


    def save_session_chats(self, context):  
        try:  
            with get_connection() as conn:
                with conn.cursor() as cur:     
                    cur.execute("START TRANSACTION")

                    for idx, message in enumerate(context):
                        if message.get("saved", True): 
                            continue
                        cur.execute(
                            """
                            INSERT INTO cb_chat_history (db_user_id, session_id, role, content)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (   self.db_user_id, 
                                self.session_id, 
                                message["role"], 
                                message["content"]
                            ),
                        )
                        context[idx]['saved'] = True

                    cur.execute("COMMIT")
                    conn.commit()
                    return {"ok": True}
        except Exception as e:
            logger.exception("세션 채팅 일괄 저장 실패(save_session_chats)")
            return {"ok": False, "error": "데이터베이스 등록에 실패했습니다.(save_session_chats) " + str(e)}


    def restore_session_chats(self) -> list[dict]:
        chat_history = self.get_chat_history()["chat_history"]
        logger.debug("restore_session_chats: %d건 복원", len(chat_history))
        return [{"role": v['role'], "content": v['content'], "saved": True} for v in chat_history]


