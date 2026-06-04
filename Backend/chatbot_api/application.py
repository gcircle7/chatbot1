"""챗봇 백엔드 (룰 베이스 + 인증 API).

프론트엔드(application.py)와 별도 프로세스로 동작하며 포트 8006에서 API 제공.
프론트엔드가 다른 포트에서 서빙되므로 CORS 응답 헤더를 직접 추가한다.
"""
from flask import Flask, request, jsonify
import sys
import random
import re
from chatbot_client import ChatbotClient

from auth import (
    login as auth_login,
    signup as auth_signup,
    reset_password as auth_reset_password,
    logout as auth_logout,
    check_session as auth_check_session,
    get_access_history as auth_get_access_history,
)

from common import chatgpt_respone_format 
import concurrent

import requests
from concurrent.futures import ThreadPoolExecutor
executor = ThreadPoolExecutor(max_workers=1)

def async_send_request(callbackUrl, future):
    # future가 완료될 때까지 대기. 이후는 개선 전 코드와 동일
    response_status, response_message, error_message = future.result()
    print(f"response_status: {response_status}, response_message: {response_message}, error_message: {error_message}")
    if response_status == "failed":
        response_to_kakao = chatgpt_respone_format(error_message, useCallback=False)
    else:
        response_to_kakao = chatgpt_respone_format(response_message, useCallback=False)
    print(f"response_to_kakao: {response_to_kakao}")
    callbackResponse = requests.post(callbackUrl, json=response_to_kakao)
    print("CallbackResponse:", callbackResponse)
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
        # 프리플라이트 응답
        return ("", 204)

    data = request.get_json(silent=True) or {}
    request_message = (data.get("request_message") or "").strip()
    if not request_message:
        return jsonify({"response_message": "뭐라고? 다시 한 번 말해줄래?"})

    session_token = data.get("session_token") or ""
    result = auth_check_session(session_token)
    if not result.get("ok") or result.get("ok") == False:
        print(f"session check error: {result.get('error')}")
        return jsonify({
            "status": "error", 
            "response_message": "",
            "error_message": result.get("error")
            })

    # 대화 진행 
    cb_client = ChatbotClient(result.get("db_user_id"), result.get("session_id"))
    print(f"user message:  {request_message}")
    request_id = cb_client.add_user_message(request_message)
    response_status, response_message, error_message = cb_client.get_response_content(request_id)
    print(f"response message:  {response_status}, {response_message}, {error_message}")
    return jsonify({"status": response_status, "response_message": response_message, "error_message": error_message})

@application.route("/chat-kakao", methods=["POST", "OPTIONS"])
def chat_kakao():
    if request.method == "OPTIONS":
        # 프리플라이트 응답 
        return ("", 204) 

    data = request.get_json(silent=True) or {}
    user_request = data.get("userRequest") or {}
    print(f"{'-'*50}\n 카카오톡 메시지 수신: {data}\n{'-'*50}")

    request_message = (user_request.get("utterance") or "").strip()
    if not request_message:
        return chatgpt_respone_format("무슨 말인지 다시 한 번 말해줄래?")

    print(f"request_message: {request_message}")
    callbackUrl = user_request.get("callbackUrl")
    print(f"콜백 callbackUrl: {callbackUrl}")

    # return chatgpt_respone_format("반가워!!", useCallback=False)

    db_user_id = 2
    session_id = 2  # session_token = '71d7c0fc31e1725f880facdcbe790f01a4556917c00b9f55f28d6725aa11aba5'
    print(f"kakaotalk db_user_id:  {db_user_id}, session_id:  {session_id}")

    # 대화 진행 
    cb_client = ChatbotClient(db_user_id, session_id)
    print(f"user message:  {request_message}")
    request_id = cb_client.add_user_message(request_message)
    print(f"request_id:  {request_id}")
    # jjinchin.send_request 메소드가 실행될 미래를 담고 있는 future 객체 반환     
    future = executor.submit(cb_client.get_response_content, request_id)
    try:
        # jjinchin.send_request가 종료되면 그 결과를 반환
        # 단, 3초까지 기다리다가 완료가 안되면 concurrent.futures.TimeoutError 예외 발생 
        response_status, response_message, error_message = future.result(timeout=3)
        message = error_message if response_status == "failed" else response_message
        response_to_kakao = chatgpt_respone_format(message, useCallback=False)
        print("3초 내 응답:", response_to_kakao)
        return jsonify(response_to_kakao)
    except concurrent.futures.TimeoutError:
        print(f"콜백 응답 예정: {callbackUrl}")
        if callbackUrl:
            # 3초 초과 + callbackUrl 있음 → 나중에 콜백으로 응답
            executor.submit(async_send_request, callbackUrl, future)
            immediate_response = chatgpt_respone_format("잠시만요...", useCallback=True)
            return jsonify(immediate_response)
        # 오픈빌더 테스트 등 callbackUrl 없음 → 완료될 때까지 동기 대기
        response_status, response_message, error_message = future.result()
        message = error_message if response_status == "failed" else response_message
        response_to_kakao = chatgpt_respone_format(message, useCallback=False)
        print(" @@@@@@@@@@@@@@@ callbackUrl 없음, 동기 응답:", response_to_kakao)
        return jsonify(response_to_kakao)

@application.route("/health")
def health():
    return jsonify({"status": "ok"})


def _start_ngrok(port: int):
    """pyngrok으로 외부 접속용 공개 URL(터널) 생성.

    - NGROK_AUTHTOKEN 환경변수가 있으면 인증 토큰으로 사용한다(없으면 ngrok 기본 동작).
    - NGROK_DOMAIN 환경변수가 있으면 고정 도메인으로 연결한다.
    실패해도 로컬 서버 실행은 계속되도록 예외를 흡수한다.
    """
    import os
    try:
        from pyngrok import conf, ngrok
    except ImportError:
        print("[ngrok] pyngrok 미설치 — 'uv add pyngrok' 후 다시 실행하세요. 로컬로만 실행합니다.")
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
        print(f"{'=' * 60}")
        print(f"[ngrok] 외부 접속 주소: {tunnel.public_url}")
        print(f"[ngrok] 로컬 포트     : {port}")
        print(f"[ngrok] 헬스체크      : {tunnel.public_url}/health")
        print(f"{'=' * 60}")
        return tunnel
    except Exception as exc:  # noqa: BLE001 - 터널 실패 시에도 로컬 서버는 띄운다
        print(f"[ngrok] 터널 생성 실패: {exc}")
        print("[ngrok] NGROK_AUTHTOKEN 환경변수가 설정되었는지 확인하세요. 로컬로만 실행합니다.")
        return None


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8006

    # ngrok 비활성화: NGROK_DISABLE=1 (또는 reloader 자식 프로세스에서 중복 실행 방지)
    import os
    if os.environ.get("NGROK_DISABLE") != "1":
        _start_ngrok(port)

    application.run(host="0.0.0.0", port=port)
