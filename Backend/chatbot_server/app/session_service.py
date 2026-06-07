"""DB 기반 로그인 세션·이력 관리."""

import logging
from datetime import datetime

from _utils.db import get_connection

logger = logging.getLogger(__name__)


def get_valid_sessions() -> list[dict]:
    now = datetime.now()
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT s.id AS session_id, s.db_user_id, s.session_token, s.status, s.expires_at,
                        u.login_id, u.role, u.username AS display_name
                    FROM user_session s
                    INNER JOIN user_info u ON u.id = s.db_user_id
                    WHERE s.status = 'active'
                    """,
                )
                return cur.fetchall()
    except Exception:
        logger.exception("활성 세션 조회 실패(get_valid_sessions)")
        return []


def get_session_if_active(session_id: int) -> dict | None:
    """session_id 가 active 이고 (channel 이거나 미만료) 이면 세션 정보를 반환.

    스테이트리스 워커가 매 요청마다 세션 유효성을 확인하는 진입점.
    만료된 세션은 expired 로 마킹하고 None 을 돌려준다.
    """
    now = datetime.now()
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT s.id AS session_id, s.db_user_id, s.status, s.expires_at,
                        u.login_id, u.role, u.username AS display_name
                    FROM user_session s
                    INNER JOIN user_info u ON u.id = s.db_user_id
                    WHERE s.id = %s AND s.status = 'active'
                    """,
                    (session_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None

                expires_at = row.get("expires_at")
                # channel(카카오 등) 역할은 만료 예외
                if row.get("role") != "channel" and expires_at is not None and now > expires_at:
                    cur.execute(
                        "UPDATE user_session SET status = 'expired' WHERE id = %s",
                        (session_id,),
                    )
                    return None
                return row
    except Exception:
        logger.exception("세션 조회 실패(get_session_if_active) session_id=%s", session_id)
        return None


def set_expire_sessions(session_ids: list[int]) -> dict:
    if not session_ids:
        return {"ok": True}
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                placeholders = ", ".join(["%s"] * len(session_ids))
                cur.execute(
                    f"""
                    UPDATE user_session
                    SET status = 'expired'
                    WHERE id in ({placeholders})
                    """,
                    tuple(session_ids),
                )
                return {"ok": True}
    except Exception as e:
        logger.exception("세션 만료 처리 실패(set_expire_sessions)")
        return {"ok": False, "error": "데이터베이스 연결에 실패했어요.(set_expire_sessions) " + str(e)}
