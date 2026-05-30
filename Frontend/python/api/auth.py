"""인증·회원가입·비밀번호 재설정 (MySQL user_info)."""

import re
from datetime import datetime

import bcrypt

from db import get_connection
from session_service import (
    create_session,
    validate_session,
    logout_session,
    log_login_failed,
    log_password_reset,
    list_access_history,
)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _check_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def _client_meta(data: dict) -> tuple[str | None, str | None]:
    ip = (data.get("client_ip") or "").strip() or None
    ua = (data.get("user_agent") or "").strip() or None
    if ua and len(ua) > 500:
        ua = ua[:500]
    return ip, ua


def login(login_id: str, password: str, data: dict | None = None) -> dict:
    data = data or {}
    ip, ua = _client_meta(data)
    login_id = (login_id or "").strip()

    if not login_id or not password:
        log_login_failed(login_id, ip, ua, "입력값 누락")
        return {"ok": False, "error": "아이디와 비밀번호를 입력해주세요."}

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, login_id, username, password_hash, status
                    FROM user_info
                    WHERE login_id = %s AND deleted_at IS NULL
                    """,
                    (login_id,),
                )
                user = cur.fetchone()
    except Exception:
        return {"ok": False, "error": "데이터베이스 연결에 실패했어요."}

    if not user:
        log_login_failed(login_id, ip, ua, "존재하지 않는 계정")
        return {"ok": False, "error": "아이디 또는 비밀번호가 올바르지 않아요."}

    if user["status"] != "active":
        log_login_failed(login_id, ip, ua, f"비활성 계정 ({user['status']})")
        return {"ok": False, "error": "사용할 수 없는 계정이에요. 관리자에게 문의해주세요."}

    if not _check_password(password, user["password_hash"]):
        log_login_failed(login_id, ip, ua, "비밀번호 불일치")
        return {"ok": False, "error": "아이디 또는 비밀번호가 올바르지 않아요."}

    try:
        session_info = create_session(user["id"], ip, ua)
        now = datetime.now()
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE user_info
                    SET last_login_at = %s, last_login_ip = %s
                    WHERE id = %s
                    """,
                    (now, ip, user["id"]),
                )
    except Exception:
        return {"ok": False, "error": "세션 생성에 실패했어요."}

    return {
        "ok": True,
        "login_id": user["login_id"],
        "display_name": user["username"],
        "db_user_id": user["id"],
        **session_info,
    }


def signup(
    login_id: str,
    display_name: str,
    email: str,
    password: str,
    password_confirm: str,
    data: dict | None = None,
) -> dict:
    login_id = (login_id or "").strip()
    display_name = (display_name or "").strip()
    email = (email or "").strip().lower()

    if not login_id or not display_name or not email or not password:
        return {"ok": False, "error": "모든 항목을 입력해주세요."}
    if len(login_id) > 30:
        return {"ok": False, "error": "아이디는 30자 이하로 입력해주세요."}
    if len(display_name) > 50:
        return {"ok": False, "error": "표시 이름은 50자 이하로 입력해주세요."}
    if not _EMAIL_RE.match(email):
        return {"ok": False, "error": "올바른 이메일 형식이 아니에요."}
    if len(password) < 8:
        return {"ok": False, "error": "비밀번호는 8자 이상으로 해주세요."}
    if password != password_confirm:
        return {"ok": False, "error": "비밀번호 확인이 일치하지 않아요."}

    password_hash = _hash_password(password)

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM user_info WHERE login_id = %s AND deleted_at IS NULL",
                    (login_id,),
                )
                if cur.fetchone():
                    return {"ok": False, "error": "이미 사용 중인 아이디예요."}

                cur.execute(
                    "SELECT id FROM user_info WHERE email = %s AND deleted_at IS NULL",
                    (email,),
                )
                if cur.fetchone():
                    return {"ok": False, "error": "이미 등록된 이메일이에요."}

                cur.execute(
                    """
                    INSERT INTO user_info
                        (login_id, email, password_hash, username, role, status)
                    VALUES (%s, %s, %s, %s, 'user', 'active')
                    """,
                    (login_id, email, password_hash, display_name),
                )
                db_user_id = cur.lastrowid
    except Exception as e:
        if "Duplicate" in str(e):
            return {"ok": False, "error": "이미 등록된 아이디 또는 이메일이에요."}
        return {"ok": False, "error": "회원가입 처리 중 오류가 발생했어요."}

    data = data or {}
    ip, ua = _client_meta(data)
    try:
        session_info = create_session(db_user_id, ip, ua)
    except Exception:
        return {
            "ok": True,
            "login_id": login_id,
            "display_name": display_name,
            "db_user_id": db_user_id,
            "message": "가입은 완료됐지만 자동 로그인에 실패했어요. 로그인해주세요.",
        }

    return {
        "ok": True,
        "login_id": login_id,
        "display_name": display_name,
        "db_user_id": db_user_id,
        **session_info,
    }


def reset_password(
    login_id: str,
    email: str,
    display_name: str,
    new_password: str,
    new_password_confirm: str,
    data: dict | None = None,
) -> dict:
    data = data or {}
    ip, ua = _client_meta(data)
    login_id = (login_id or "").strip()
    email = (email or "").strip().lower()
    display_name = (display_name or "").strip()

    if not login_id or not email or not display_name:
        return {"ok": False, "error": "모든 항목을 입력해주세요."}
    if len(new_password) < 8:
        return {"ok": False, "error": "새 비밀번호는 8자 이상으로 해주세요."}
    if new_password != new_password_confirm:
        return {"ok": False, "error": "새 비밀번호 확인이 일치하지 않아요."}

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, password_hash
                    FROM user_info
                    WHERE login_id = %s AND email = %s AND username = %s
                      AND status = 'active' AND deleted_at IS NULL
                    """,
                    (login_id, email, display_name),
                )
                user = cur.fetchone()
                if not user:
                    return {"ok": False, "error": "입력하신 정보와 일치하는 계정을 찾을 수 없어요."}

                cur.execute(
                    """
                    UPDATE user_info
                    SET password_hash = %s, updated_at = %s
                    WHERE id = %s
                    """,
                    (_hash_password(new_password), datetime.now(), user["id"]),
                )
                db_user_id = user["id"]
    except Exception:
        return {"ok": False, "error": "비밀번호 변경 중 오류가 발생했어요."}

    try:
        log_password_reset(db_user_id, ip, ua)
    except Exception:
        pass

    return {"ok": True, "message": "비밀번호가 변경되었어요. 새 비밀번호로 로그인해주세요."}


def logout(session_token: str, data: dict | None = None) -> dict:
    data = data or {}
    ip, ua = _client_meta(data)
    try:
        return logout_session(session_token, ip, ua)
    except Exception:
        return {"ok": False, "error": "로그아웃 처리 중 오류가 발생했어요."}

def check_session(session_token: str) -> dict:
    try:
        return validate_session(session_token)
    except Exception:
        return {"ok": False, "error": "세션 확인 중 오류가 발생했어요."}


def get_access_history(session_token: str, limit: int = 30) -> dict:
    try:
        session = validate_session(session_token)
        if not session.get("ok"):
            return session
        items = list_access_history(session["db_user_id"], limit=limit)
        return {"ok": True, "items": items}
    except Exception:
        return {"ok": False, "error": "접속 이력을 불러오지 못했어요."}
