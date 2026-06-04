"""챗봇 프론트엔드 서버.

세션 기반 로그인 흐름을 가진다.
- `/` 서비스 안내 페이지(index.html), 로그인은 `/login` 링크로 이동
- 로그인·회원가입·비밀번호 재설정은 api/application.py(포트 8006) + MySQL로 처리
"""

from flask import (
    Flask, render_template, request, redirect, url_for, session
)
from functools import wraps
import os
import sys
import atexit

from backend_client import (
    auth_login,
    auth_signup,
    auth_reset_password,
    auth_logout,
    auth_validate_session,
    auth_access_history,
)

application = Flask(__name__)

application.secret_key = os.environ.get(
    "FLASK_SECRET_KEY", "dev-secret-change-me"
)


def login_required(view):
    """DB 세션 토큰 검증 후 보호 라우트 접근."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        token = session.get("session_token")
        if not token:
            return redirect(url_for("login"))

        result = auth_validate_session(token)
        if not result.get("ok"):
            session.clear()
            return redirect(url_for("login"))

        session["login_id"] = result["login_id"]
        session["display_name"] = result["display_name"]
        if result.get("db_user_id"):
            session["db_user_id"] = result["db_user_id"]
        return view(*args, **kwargs)
    return wrapper


def _fetch_access_history(limit: int = 30) -> list[dict]:
    """접속 이력 조회 (chatbot_api에 HTTP 위임). 실패·없음이면 빈 목록."""
    token = session.get("session_token")
    if not token:
        return []

    result = auth_access_history(token, limit=limit)
    if result.get("ok"):
        return result.get("items") or []
    return []


def _start_session_from_api(result: dict):
    session["login_id"] = result["login_id"]
    session["db_user_id"] = result.get("db_user_id")
    session["session_id"] = result.get("session_id")
    session["display_name"] = result["display_name"]
    session["session_token"] = result["session_token"]


@application.route("/")
def index():
    is_logged_in = False
    display_name = None
    login_id = None
    token = session.get("session_token")
    if token:
        result = auth_validate_session(token)
        if result.get("ok"):
            is_logged_in = True
            login_id = result["login_id"]
            display_name = result["display_name"]
            session["login_id"] = login_id
            session["display_name"] = display_name
        else:
            session.clear()
    return render_template(
        "index.html",
        is_logged_in=is_logged_in,
        display_name=display_name,
        login_id=login_id,
    )


@application.route("/login", methods=["GET", "POST"])
def login():
    if session.get("session_token"):
        if auth_validate_session(session["session_token"]).get("ok"):
            return redirect(url_for("index"))
        session.clear()

    error = None
    if request.method == "POST":
        login_id = (request.form.get("login_id") or "").strip()
        password = request.form.get("password") or ""
        result = auth_login(login_id, password, request)
        if result.get("ok") and result.get("session_id"):
            _start_session_from_api(result)
            return redirect(url_for("index"))
        error = result.get("error", "로그인에 실패했어요.")

    return render_template("login.html", error=error)


@application.route("/logout")
def logout():
    token = session.get("session_token")
    if token:
        auth_logout(token, request)
    session.clear()
    return redirect(url_for("index"))


@application.route("/signup", methods=["GET", "POST"])
def signup():
    if session.get("session_token"):
        if auth_validate_session(session["session_token"]).get("ok"):
            return redirect(url_for("chat_app"))
        session.clear()

    error = None
    if request.method == "POST":
        login_id = (request.form.get("login_id") or "").strip()
        display_name = (request.form.get("display_name") or "").strip()
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""
        password_confirm = request.form.get("password_confirm") or ""

        result = auth_signup(
            login_id, display_name, email, password, password_confirm, request
        )
        if result.get("ok") and result.get("session_token"):
            _start_session_from_api(result)
            return redirect(url_for("chat_app"))
        if result.get("ok"):
            return redirect(url_for("login"))
        error = result.get("error", "회원가입에 실패했어요.")

    return render_template("signup.html", error=error)


@application.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if session.get("session_token"):
        if auth_validate_session(session["session_token"]).get("ok"):
            return redirect(url_for("chat_app"))
        session.clear()

    error = None
    success_message = None
    submitted_login_id = ""

    if request.method == "POST":
        submitted_login_id = (request.form.get("login_id") or "").strip()
        email = (request.form.get("email") or "").strip()
        display_name = (request.form.get("display_name") or "").strip()
        new_password = request.form.get("new_password") or ""
        new_password_confirm = request.form.get("new_password_confirm") or ""

        result = auth_reset_password(
            submitted_login_id,
            email,
            display_name,
            new_password,
            new_password_confirm,
            request,
        )
        if result.get("ok"):
            success_message = result.get(
                "message", "비밀번호가 변경되었어요. 새 비밀번호로 로그인해주세요."
            )
        else:
            error = result.get("error", "요청을 처리할 수 없어요.")

    return render_template(
        "forgot_password.html",
        error=error,
        success_message=success_message,
        submitted_login_id=submitted_login_id,
    )


@application.route("/mypage")
@login_required
def mypage():
    return render_template(
        "mypage.html",
        is_logged_in=True,
        nav_active="mypage",
        login_id=session["login_id"],
        display_name=session["display_name"],
        access_history=_fetch_access_history(30),
    )


@application.route("/chat-app")
@login_required
def chat_app():
    print("login_id=", session.get("login_id"))
    print("display_name=", session.get("display_name"))
    print("session_token=", session.get("session_token"))
    embed = request.args.get("embed") == "1"

    return render_template(
        "chat.html",
        login_id=session["login_id"] if session.get("login_id") else None,
        db_user_id=session["db_user_id"] if session.get("db_user_id") else None,
        session_token=session["session_token"] if session.get("session_token") else None,
        display_name=session["display_name"] if session.get("display_name") else None,
        embed=embed,
        CHATBOT_API_URL=os.environ.get("CHATBOT_API_URL"),
    )

@atexit.register
def shutdown():
    print("flask shutting down...")


if __name__ == "__main__":
    application.run(host="0.0.0.0", port=int(sys.argv[1]))
