"""DB 기반 로그인 세션·이력 관리."""

from datetime import datetime, timedelta 
from _utils.db import get_connection

def get_valid_sessions() -> list[dict]:
    now = datetime.now()
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("START TRANSACTION")
                cur.execute(
                    """
                    SELECT s.id AS session_id, s.db_user_id, s.session_token, s.status, s.expires_at,
                        u.login_id, u.username AS display_name
                    FROM user_session s
                    INNER JOIN user_info u ON u.id = s.db_user_id
                    WHERE s.status = 'active'
                    """,
                )
                rows = cur.fetchall()
                cur.execute("COMMIT")
                conn.commit()
                # print("sessions count: ", len(rows))
                # print("sessions", rows)
                return rows
    except Exception:
        return []


def set_expire_sessions(session_ids: list[int]) -> dict:
    if not session_ids or len(session_ids) == 0:
        return {"ok": True}
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("START TRANSACTION")
                placeholders = ", ".join(["%s"] * len(session_ids))
                cur.execute(
                    f"""
                    UPDATE user_session
                    SET status = 'expired'
                    WHERE id in ({placeholders})
                    """,
                    tuple(session_ids),
                )
                cur.execute("COMMIT")
                conn.commit()
                return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": "데이터베이스 연결에 실패했어요.(set_expire_sessions) " + str(e)}