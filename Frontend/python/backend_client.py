"""프론트엔드 → api/application.py HTTP 클라이언트."""

import json
import os
import urllib.error
import urllib.request

API_BASE = os.environ.get("CHATBOT_API_BASE_URL", "http://localhost:8006").rstrip("/")

_CONNECTION_ERROR = {
    "ok": False,
    "error": "백엔드 서버에 연결할 수 없어요. api 서버가 실행 중인지 확인해주세요.",
}


def _request(
    method: str,
    path: str,
    payload: dict | None = None,
    *,
    client_ip: str | None = None,
    user_agent: str | None = None,
) -> dict:
    url = f"{API_BASE}{path}"
    body = dict(payload) if payload else {}
    if client_ip:
        body["client_ip"] = client_ip
    if user_agent:
        body["user_agent"] = user_agent

    data = None
    headers = {"Accept": "application/json"}
    if method != "GET":
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        if e.code == 404 and path == "/auth/session/history":
            return {"ok": True, "items": []}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"ok": False, "error": f"요청 처리 중 오류가 발생했어요. ({e.code})"}
    except (urllib.error.URLError, TimeoutError, OSError):
        return dict(_CONNECTION_ERROR)


def _client_meta(request) -> tuple[str | None, str | None]:
    forwarded = request.headers.get("X-Forwarded-For", "")
    ip = forwarded.split(",")[0].strip() if forwarded else request.remote_addr
    return ip, request.headers.get("User-Agent", "")


def auth_login(login_id: str, password: str, request) -> dict:
    ip, ua = _client_meta(request)
    return _request(
        "POST",
        "/auth/login",
        {"login_id": login_id, "password": password},
        client_ip=ip,
        user_agent=ua,
    )


def auth_signup(
    login_id: str,
    display_name: str,
    email: str,
    password: str,
    password_confirm: str,
    request,
) -> dict:
    ip, ua = _client_meta(request)
    return _request(
        "POST",
        "/auth/signup",
        {
            "login_id": login_id,
            "display_name": display_name,
            "email": email,
            "password": password,
            "password_confirm": password_confirm,
        },
        client_ip=ip,
        user_agent=ua,
    )


def auth_reset_password(
    login_id: str,
    email: str,
    display_name: str,
    new_password: str,
    new_password_confirm: str,
    request,
) -> dict:
    ip, ua = _client_meta(request)
    return _request(
        "POST",
        "/auth/reset-password",
        {
            "login_id": login_id,
            "email": email,
            "display_name": display_name,
            "new_password": new_password,
            "new_password_confirm": new_password_confirm,
        },
        client_ip=ip,
        user_agent=ua,
    )


def auth_logout(session_token: str, request) -> dict:
    ip, ua = _client_meta(request)
    return _request(
        "POST",
        "/auth/logout",
        {"session_token": session_token},
        client_ip=ip,
        user_agent=ua,
    )


def auth_validate_session(session_token: str) -> dict:
    return _request("POST", "/auth/session/validate", {"session_token": session_token})


def auth_access_history(session_token: str, limit: int = 30) -> dict:
    return _request(
        "POST",
        "/auth/session/history",
        {"session_token": session_token, "limit": limit},
    )
