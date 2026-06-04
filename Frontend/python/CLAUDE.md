# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> 저장소 전체 구조(3개 프로세스·큐 기반 데이터 흐름)는 루트 `../../CLAUDE.md` 참고. 이 문서는 **frontend 패키지** 전용 메모.

## 역할

세션 기반 로그인 흐름을 가진 Flask 웹 UI. **회원가입·로그인·세션 검증·접속이력은 직접 처리하지 않고** chatbot_api(포트 8006)에 HTTP 위임한다. 챗봇 대화 자체도 프론트 서버를 거치지 않고 **브라우저가 chatbot_api 로 직접** POST 한다.

- Python `>=3.12`, 패키지 매니저 **uv**.
- 주요 의존성: `flask`, `pymysql`, `bcrypt`, `requests`, `pyngrok`, `python-dotenv`.

## 실행

```powershell
uv sync
uv run python application.py 8000   # 포트 인자 필수 — sys.argv[1], 누락 시 IndexError
```

`http://localhost:8000/` 접속. 정상 동작하려면 **chatbot_api(8006)가 함께 떠 있어야** 한다(로그인·세션 검증이 거기로 간다).

`.env`: `cp .env.example .env`. 핵심 키 — `FLASK_SECRET_KEY`(세션 서명), `CHATBOT_API_BASE`(api 베이스, 기본 `http://localhost:8006`), `CHATBOT_CHAT_URL`(브라우저 채팅 POST, 기본 `{베이스}/chat-api`). 구 `CHATBOT_API_URL` 은 `CHATBOT_API_BASE` 폴백으로만 인식.

## 인증 구조

- **세션 검증은 매 보호 라우트마다 chatbot_api 를 탄다.** `login_required` 데코레이터(`application.py`)가 Flask 세션의 `session_token` 을 꺼내 `auth_validate_session`(→ api `/auth/session/validate`)으로 검증하고, 실패 시 `session.clear()` 후 `/login` 으로 리다이렉트.
- Flask 세션에 저장되는 값: `session_token`, `login_id`, `db_user_id`, `session_id`, `display_name`. 권위 있는 상태는 DB(api 쪽)에 있고 Flask 세션은 토큰 보관용 캐시에 가깝다.
- api 호출은 전부 **`backend_client.py`** 를 경유한다(`auth_login`/`auth_signup`/`auth_reset_password`/`auth_logout`/`auth_validate_session`/`auth_access_history`). 새 인증 동작을 추가하면 여기에 함수를 더하고 api 쪽 `/auth/*` 라우트와 컨트랙트를 맞춘다. 비밀번호 해싱·검증은 **api 의 `auth.py`(bcrypt)** 에서 일어나며 프론트는 평문을 그대로 넘긴다.

## 라우트 (`application.py`)

- `GET /` — `index.html`. 세션 유효하면 로그인 상태로 렌더(로그인 강제 아님).
- `GET|POST /login`, `/signup`, `/forgot-password` — 폼 렌더 + api 위임. 이미 로그인 상태면 리다이렉트.
- `GET /logout` — api `/auth/logout` 호출 후 `session.clear()`.
- `GET /mypage` — `@login_required`. 접속이력(`_fetch_access_history`) 포함.
- `GET /chat-app` — `@login_required`. `chat.html` 렌더. `?embed=1` 로 임베드 모드. 세션 값과 `CHATBOT_CHAT_URL` 을 템플릿에 주입.

## 프론트엔드 ↔ chatbot_api 채팅 컨트랙트

`templates/chat.html` 의 `fetchResponse()` 가 **`{{ CHATBOT_CHAT_URL }}` 로 직접** POST(프론트 서버 경유 X). ngrok 등 공개 URL을 쓸 때는 `CHATBOT_CHAT_URL` 만 바꾸면 된다. 인증 호출은 `backend_client` 가 `CHATBOT_API_BASE` 에 `/auth/*` 를 붙인다.

- 요청 본문: `{ db_user_id, session_token, request_message }`
- 응답 본문: `{ status, response_message, error_message }` — `status` 가 `failed`/`error` 면 `error_message` 를 콘솔에 출력.

응답 메시지는 Handlebars triple-stash(`{{{...}}}`, **HTML 이스케이프 미적용**)로 삽입되므로 api 가 신뢰 불가 HTML 을 반환하지 않게 할 것. 서버 측 Jinja2 와 클라이언트 Handlebars 가 같은 `{{ }}` 문법을 쓰므로 Handlebars 블록은 `{% raw %}...{% endraw %}` 로 감싼다.

## 알아둘 점

- 접속이력(`_fetch_access_history`)을 포함한 모든 DB 의존 동작은 `backend_client` 를 통해 api 에 HTTP 위임한다. frontend 는 DB 테이블에 직접 접근하지 않는다(`backend_client._request` 가 `/auth/session/history` 의 404 를 빈 목록으로 흡수).
- DB 스키마·초기화 스크립트는 이 패키지가 아니라 **`Backend/chatbot_api/scripts/`** 에 있다(테이블을 실제로 쓰는 api/server 쪽으로 이전됨).
- UI 카피("내 찐친 고비" 등)는 한국어 고정.
