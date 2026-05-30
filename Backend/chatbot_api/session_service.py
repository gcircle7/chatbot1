"""DB 기반 로그인 세션·이력 관리."""

from datetime import datetime, timedelta
import os
from pathlib import Path
import secrets

from db import get_connection

def _read_dotenv_value(key: str) -> str | None:
    """
    매우 단순한 .env 파서.
    - 의존성 추가 없이 SESSION_TTL_HOURS 같은 단일 값 읽기 목적
    - 환경변수가 이미 설정되어 있으면 .env는 사용하지 않음
    """

    # api/ 디렉토리 기준으로 프로젝트 루트의 .env를 찾는다.
    dotenv_path = (Path(__file__).resolve().parent.parent / ".env").resolve()
    if not dotenv_path.exists():
        return None

    try:
        for raw in dotenv_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            k, v = line.split("=", 1)
            k = k.strip()
            if k != key:
                continue

            v = v.strip()
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            return v
    except OSError:
        return None

    return None


def _get_session_ttl_hours(default: int = 24) -> int:
    raw = os.environ.get("SESSION_TTL_HOURS")
    if raw is None:
        raw = _read_dotenv_value("SESSION_TTL_HOURS")
    if raw is None:
        return default
    try:
        hours = int(raw)
        return hours if hours > 0 else default
    except (TypeError, ValueError):
        return default


SESSION_TTL_HOURS = _get_session_ttl_hours()


def _ttl() -> timedelta:
    return timedelta(hours=SESSION_TTL_HOURS)


def create_session(
    db_user_id: int,
    ip_address: str | None,
    user_agent: str | None,
) -> dict:
    token = secrets.token_hex(32)
    now = datetime.now()
    expires = now + _ttl()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_session
                    (db_user_id, session_token, status, ip_address, user_agent,
                     created_at, last_activity_at, expires_at)
                VALUES (%s, %s, 'active', %s, %s, %s, %s, %s)
                """,
                (db_user_id, token, ip_address, user_agent, now, now, expires),
            )
            session_id = cur.lastrowid
            _log_event(
                cur,
                db_user_id=db_user_id,
                session_id=session_id,
                event_type="login_success",
                login_id=None,
                ip_address=ip_address,
                user_agent=user_agent,
                message="로그인 성공",
            )

    return {
        "session_id": session_id,
        "db_user_id": db_user_id,
        "session_token": token,
        "expires_at": expires.isoformat(sep=" ", timespec="seconds"),
    }


def validate_session(session_token: str) -> dict:
    if not session_token:
        return {"ok": False, "error": "세션이 없어요."}

    now = datetime.now()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT s.id AS session_id, s.session_token, s.status, s.expires_at,
                       u.id AS db_user_id, u.login_id, u.username AS display_name
                FROM user_session s
                INNER JOIN user_info u ON u.id = s.db_user_id
                WHERE s.session_token = %s
                  AND u.status = 'active'
                  AND u.deleted_at IS NULL
                """,
                (session_token,),
            )
            row = cur.fetchone()

            if not row:
                return {"ok": False, "error": "유효하지 않은 세션이에요."}

            if row["status"] != "active":
                return {"ok": False, "error": "종료된 세션이에요."}

            if row["expires_at"] < now:
                cur.execute(
                    """
                    UPDATE user_session
                    SET status = 'expired'
                    WHERE id = %s
                    """,
                    (row["session_id"],),
                )
                _log_event(
                    cur,
                    db_user_id=row["db_user_id"],
                    session_id=row["session_id"],
                    event_type="session_expired",
                    login_id=row["login_id"],
                    message="세션 만료",
                )
                return {"ok": False, "error": "세션이 만료되었어요. 다시 로그인해주세요."}

            cur.execute(
                """
                UPDATE user_session
                SET last_activity_at = %s, 
                    expires_at = %s
                WHERE id = %s
                """,
                (now, now + timedelta(hours=SESSION_TTL_HOURS), row["session_id"]),
            )

    return {
        "ok": True,
        "login_id": row["login_id"],
        "db_user_id": row["db_user_id"],
        "session_id": row["session_id"],
        "session_token": row["session_token"],
        "display_name": row["display_name"],
    }


def logout_session(session_token: str, ip_address: str | None, user_agent: str | None) -> dict:
    if not session_token:
        return {"ok": True}

    now = datetime.now()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT s.id AS session_id, s.db_user_id, u.login_id
                FROM user_session s
                INNER JOIN user_info u ON u.id = s.db_user_id
                WHERE s.session_token = %s AND s.status = 'active'
                """,
                (session_token,),
            )
            row = cur.fetchone()
            if not row:
                return {"ok": True}

            cur.execute(
                """
                UPDATE user_session
                SET status = 'logged_out', logged_out_at = %s
                WHERE id = %s
                """,
                (now, row["session_id"]),
            )
            _log_event(
                cur,
                db_user_id=row["db_user_id"],
                session_id=row["session_id"],
                event_type="logout",
                login_id=row["login_id"],
                ip_address=ip_address,
                user_agent=user_agent,
                message="로그아웃",
            )

    return {"ok": True}


def log_login_failed(
    login_id: str,
    ip_address: str | None,
    user_agent: str | None,
    message: str,
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            _log_event(
                cur,
                db_user_id=None,
                session_id=None,
                event_type="login_failed",
                login_id=login_id,
                ip_address=ip_address,
                user_agent=user_agent,
                message=message,
            )


_ACCESS_EVENT_LABELS = {
    "login_success": "로그인",
    "login_failed": "로그인 실패",
    "logout": "로그아웃",
    "session_expired": "세션 만료",
    "password_reset": "비밀번호 재설정",
}


def list_access_history(db_user_id: int, limit: int = 30) -> list[dict]:
    """사용자별 로그인·세션 이벤트 이력 (최신순)."""
    limit = max(1, min(int(limit), 100))
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT event_type, ip_address, user_agent, message, created_at
                FROM user_session_log
                WHERE db_user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (db_user_id, limit),
            )
            rows = cur.fetchall()

    items = []
    for row in rows:
        created = row["created_at"]
        items.append(
            {
                "event_type": row["event_type"],
                "event_label": _ACCESS_EVENT_LABELS.get(
                    row["event_type"], row["event_type"]
                ),
                "ip_address": row["ip_address"] or "-",
                "user_agent": _short_user_agent(row["user_agent"]),
                "message": row["message"] or "",
                "created_at": created.strftime("%Y-%m-%d %H:%M:%S")
                if hasattr(created, "strftime")
                else str(created),
            }
        )
    return items


def _short_user_agent(user_agent: str | None, max_len: int = 72) -> str:
    if not user_agent:
        return "-"
    ua = user_agent.strip()
    if len(ua) <= max_len:
        return ua
    return ua[: max_len - 1] + "…"


def log_password_reset(
    db_user_id: int,
    ip_address: str | None,
    user_agent: str | None,
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            _log_event(
                cur,
                db_user_id=db_user_id,
                session_id=None,
                event_type="password_reset",
                login_id=None,
                ip_address=ip_address,
                user_agent=user_agent,
                message="비밀번호 재설정",
            )


def _log_event(
    cur,
    *,
    db_user_id: int | None,
    session_id: int | None,
    event_type: str,
    login_id: str | None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    message: str | None = None,
):
    cur.execute(
        """
        INSERT INTO user_session_log
            (db_user_id, session_id, event_type, login_id,
             ip_address, user_agent, message)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (db_user_id, session_id, event_type, login_id, ip_address, user_agent, message),
    )
