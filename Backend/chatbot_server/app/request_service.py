"""요청 큐(cb_request_queue) 처리."""

from _utils.db import get_connection


def get_request_queue() -> dict:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT q.id, q.db_user_id, q.session_id, q.request_message, q.status
                    FROM cb_request_queue q
                    INNER JOIN user_session s ON s.id = q.session_id
                    WHERE q.status = 'pending'
                      AND s.status = 'active'
                    ORDER BY q.created_at ASC
                    LIMIT 1
                    """,
                )
                request = cur.fetchone()
                if request:
                    cur.execute(
                        """
                        UPDATE cb_request_queue
                        SET status = 'in_progress'
                        WHERE id = %s
                        """,
                        (request["id"],),
                    )
                return {"ok": True, "request": request}
    except Exception as e:
        return {"ok": False, "error": "데이터베이스 연결에 실패했어요.(get_request_queue) " + str(e)}


def request_status_update(request_id: int, status: str, **kwargs):
    error_message = kwargs.get("error_message")
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                if status == "failed":
                    cur.execute(
                        """
                        UPDATE cb_request_queue
                        SET status = %s, error_message = %s
                        WHERE id = %s
                        """,
                        (status, error_message if error_message else None, request_id),
                    )
                else: 
                    cur.execute(
                        """
                        UPDATE cb_request_queue
                        SET status = %s
                        WHERE id = %s
                        """,
                        (status, request_id),
                    )
    except Exception as e:
        print("데이터베이스 연결에 실패했어요.(request_status_update) " + str(e))
