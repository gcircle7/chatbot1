"""챗봇 백엔드 (인증 API + 채팅 큐 입력/응답 대기).

프론트엔드(application.py)와 별도 프로세스로 동작하며 포트 8006에서 API 제공.
프론트엔드가 다른 포트에서 서빙되므로 CORS 응답 헤더를 직접 추가한다.
"""
import logging
import sys

from logging_config import setup_logging

# 로깅을 가장 먼저 초기화(콘솔 UTF-8 + data/log 일자 파일)
setup_logging("chatbot_api")
logger = logging.getLogger(__name__)

from flask import Flask, request, jsonify

from chatbot_client import ChatbotClient

from auth import (
    login as auth_login,
    signup as auth_signup,
    reset_password as auth_reset_password,
    logout as auth_logout,
    check_session as auth_check_session,
    get_access_history as auth_get_access_history,
)
from session_service import get_or_create_channel_session

from common import chatgpt_respone_format
import concurrent
import requests
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=4)


def async_send_request(callbackUrl, future):
    # future가 완료될 때까지 대기. 이후 카카오 콜백으로 응답 전송.
    response_status, response_message, error_message = future.result()
    logger.info(
        "kakao callback 응답 status=%s message=%s error=%s",
        response_status, response_message, error_message,
    )
    if response_status == "failed":
        response_to_kakao = chatgpt_respone_format(error_message, useCallback=False)
    else:
        response_to_kakao = chatgpt_respone_format(response_message, useCallback=False)
    callbackResponse = requests.post(callbackUrl, json=response_to_kakao)
    logger.info("kakao callbackResponse: %s", callbackResponse)
    return response_to_kakao


application = Flask(__name__)


@application.route("/")
def hello():
    return "홍자봇 채팅서버 (카톡 채널: 홍자봇)"


@application.after_request
def add_cors_headers(response):
    """프론트엔드가 다른 포트(예: 8000)에서 호출하므로 CORS 허용."""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


def _request_meta(data: dict) -> dict:
    """프론트엔드가 넘긴 클라이언트 IP·UA를 API 핸들러에 전달."""
    if "client_ip" not in data:
        data = {**data, "client_ip": request.headers.get("X-Client-IP")}
    if "user_agent" not in data:
        data = {**data, "user_agent": request.headers.get("User-Agent")}
    return data


@application.route("/auth/login", methods=["POST", "OPTIONS"])
def auth_login_route():
    if request.method == "OPTIONS":
        return ("", 204)
    data = _request_meta(request.get_json(silent=True) or {})
    login_id = (data.get("login_id") or "").strip()
    password = data.get("password") or ""
    return jsonify(auth_login(login_id, password, data))


@application.route("/auth/signup", methods=["POST", "OPTIONS"])
def auth_signup_route():
    if request.method == "OPTIONS":
        return ("", 204)
    data = _request_meta(request.get_json(silent=True) or {})
    login_id = (data.get("login_id") or "").strip()
    display_name = (data.get("display_name") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    password_confirm = data.get("password_confirm") or ""
    return jsonify(
        auth_signup(login_id, display_name, email, password, password_confirm, data)
    )


@application.route("/auth/reset-password", methods=["POST", "OPTIONS"])
def auth_reset_password_route():
    if request.method == "OPTIONS":
        return ("", 204)
    data = _request_meta(request.get_json(silent=True) or {})
    return jsonify(
        auth_reset_password(
            (data.get("login_id") or "").strip(),
            (data.get("email") or "").strip(),
            (data.get("display_name") or "").strip(),
            data.get("new_password") or "",
            data.get("new_password_confirm") or "",
            data,
        )
    )


@application.route("/auth/logout", methods=["POST", "OPTIONS"])
def auth_logout_route():
    if request.method == "OPTIONS":
        return ("", 204)
    data = _request_meta(request.get_json(silent=True) or {})
    session_token = data.get("session_token") or ""
    return jsonify(auth_logout(session_token, data))


@application.route("/auth/session/validate", methods=["POST", "OPTIONS"])
def auth_validate_session_route():
    if request.method == "OPTIONS":
        return ("", 204)
    data = request.get_json(silent=True) or {}
    session_token = data.get("session_token") or ""
    return jsonify(auth_check_session(session_token))


@application.route("/auth/session/history", methods=["POST", "OPTIONS"])
def auth_access_history_route():
    if request.method == "OPTIONS":
        return ("", 204)
    data = request.get_json(silent=True) or {}
    session_token = data.get("session_token") or ""
    limit = data.get("limit", 30)
    return jsonify(auth_get_access_history(session_token, limit=limit))


@application.route("/chat-api", methods=["POST", "OPTIONS"])
def chat_api():
    if request.method == "OPTIONS":
        return ("", 204)

    data = request.get_json(silent=True) or {}
    request_message = (data.get("request_message") or "").strip()
    if not request_message:
        return jsonify({"response_message": "뭐라고? 다시 한 번 말해줄래?"})

    session_token = data.get("session_token") or ""
    result = auth_check_session(session_token)
    if not result.get("ok"):
        logger.warning("세션 검증 실패: %s", result.get("error"))
        return jsonify({
            "status": "error",
            "response_message": "",
            "error_message": result.get("error"),
        })

    # 대화 진행
    cb_client = ChatbotClient(result.get("db_user_id"), result.get("session_id"))
    logger.info("user message: %s", request_message)
    request_id = cb_client.add_user_message(request_message)
    response_status, response_message, error_message = cb_client.get_response_content(request_id)
    logger.info("response status=%s message=%s error=%s", response_status, response_message, error_message)
    return jsonify({
        "status": response_status,
        "response_message": response_message,
        "error_message": error_message,
    })


@application.route("/chat-kakao", methods=["POST", "OPTIONS"])
def chat_kakao():
    if request.method == "OPTIONS":
        return ("", 204)

    data = request.get_json(silent=True) or {}
    user_request = data.get("userRequest") or {}
    logger.info("카카오톡 메시지 수신: %s", data)

    request_message = (user_request.get("utterance") or "").strip()
    if not request_message:
        return jsonify(chatgpt_respone_format("무슨 말인지 다시 한 번 말해줄래?"))

    callbackUrl = user_request.get("callbackUrl")

    # 카카오 사용자 식별자로 채널 전용 세션을 확보(하드코딩 세션 제거)
    kakao_user = user_request.get("user") or {}
    channel_user_id = kakao_user.get("id")
    if not channel_user_id:
        logger.warning("카카오 사용자 식별자 없음: %s", user_request)
        return jsonify(chatgpt_respone_format("사용자 식별에 실패했어요. 잠시 뒤 다시 시도해줄래?"))

    sess = get_or_create_channel_session(channel_user_id)
    if not sess.get("ok"):
        return jsonify(chatgpt_respone_format("일시적인 오류가 발생했어요. 잠시 뒤 다시 시도해줄래?"))

    db_user_id = sess["db_user_id"]
    session_id = sess["session_id"]
    logger.info("kakao db_user_id=%s session_id=%s", db_user_id, session_id)

    cb_client = ChatbotClient(db_user_id, session_id)
    request_id = cb_client.add_user_message(request_message)
    future = executor.submit(cb_client.get_response_content, request_id)
    try:
        # 3초까지 기다리다가 완료가 안되면 TimeoutError → 콜백 흐름으로 전환
        response_status, response_message, error_message = future.result(timeout=3)
        message = error_message if response_status == "failed" else response_message
        response_to_kakao = chatgpt_respone_format(message, useCallback=False)
        logger.info("kakao 3초 내 응답: %s", response_to_kakao)
        return jsonify(response_to_kakao)
    except concurrent.futures.TimeoutError:
        logger.info("kakao 콜백 응답 예정: %s", callbackUrl)
        if callbackUrl:
            executor.submit(async_send_request, callbackUrl, future)
            return jsonify(chatgpt_respone_format("잠시만요...", useCallback=True))
        # callbackUrl 없음(오픈빌더 테스트 등) → 완료까지 동기 대기
        response_status, response_message, error_message = future.result()
        message = error_message if response_status == "failed" else response_message
        response_to_kakao = chatgpt_respone_format(message, useCallback=False)
        logger.info("kakao callbackUrl 없음, 동기 응답: %s", response_to_kakao)
        return jsonify(response_to_kakao)


@application.route("/health")
def health():
    return jsonify({"status": "ok"})


def _start_ngrok(port: int):
    """pyngrok으로 외부 접속용 공개 URL(터널) 생성. 실패해도 로컬 실행은 계속."""
    import os
    try:
        from pyngrok import conf, ngrok
    except ImportError:
        logger.warning("[ngrok] pyngrok 미설치 — 로컬로만 실행합니다.")
        return None

    authtoken = os.environ.get("NGROK_AUTHTOKEN")
    if authtoken:
        conf.get_default().auth_token = authtoken

    try:
        connect_kwargs = {"proto": "http"}
        domain = os.environ.get("NGROK_DOMAIN")
        if domain:
            connect_kwargs["domain"] = domain
        tunnel = ngrok.connect(port, **connect_kwargs)
        logger.info("[ngrok] 외부 접속 주소: %s (로컬 포트 %s)", tunnel.public_url, port)
        return tunnel
    except Exception as exc:  # noqa: BLE001
        logger.warning("[ngrok] 터널 생성 실패: %s — 로컬로만 실행합니다.", exc)
        return None


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8006

    import os
    if os.environ.get("NGROK_DISABLE") != "1":
        _start_ngrok(port)

    application.run(host="0.0.0.0", port=port)
