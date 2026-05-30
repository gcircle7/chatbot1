# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

Flask 기반 챗봇으로 **프론트엔드와 백엔드가 별도 프로세스**로 동작합니다.

- **프론트엔드** (`application.py`): 정적 챗봇 UI(`templates/chat.html`) 서빙. 임의 포트.
- **백엔드** (`api/application.py`): 룰 베이스 응답 API `/chat-api`. 포트 **8006** 고정 (프론트엔드가 그 주소로 하드코딩 호출).

두 서버가 다른 포트라 백엔드는 `after_request`에서 CORS 헤더를 응답에 직접 추가합니다.

- Python `>=3.12`
- 패키지 매니저: **uv** (`uv.lock` 사용)
- 단일 의존성: `flask>=3.1.3`

## 자주 쓰는 명령어

### 의존성 설치
```powershell
uv sync
```
`requirements.txt`는 `uv pip compile pyproject.toml -o requirements.txt`로 자동 생성된 파일입니다. 의존성을 추가/변경하려면 `pyproject.toml`을 수정한 뒤 `uv sync` 후 위 명령으로 재생성하세요.

### 개발 서버 실행
두 서버를 **각각 다른 터미널**에서 실행해야 합니다.

프론트엔드 — 포트 번호는 필수 (`application.py:20`에서 `sys.argv[1]` 직접 참조, 누락 시 `IndexError`):
```powershell
uv run python application.py 8000
```

백엔드 — 인자 생략 시 기본 8006 (`api/application.py`):
```powershell
uv run python api/application.py
```

`host='0.0.0.0'`으로 바인딩되므로 같은 네트워크에서 접근 가능합니다. 챗봇 UI는 `http://localhost:8000/chat-app`에서 확인합니다. 백엔드만 따로 점검할 때는 `GET http://localhost:8006/health`로 헬스체크 가능.

## 아키텍처

### 프론트엔드 라우트 (`application.py`)
- `GET /` — 세션 검사 후 `/chat-app`(로그인됨) 또는 `/login`(로그인 안 됨)으로 리다이렉트
- `GET /login` — 로그인 폼(`templates/login.html`) 렌더
- `POST /login` — `MOCK_USERS` dict로 자격증명 검증, 성공 시 세션에 `username`/`display_name` 저장
- `GET /logout` — `session.clear()` 후 `/login`으로 리다이렉트
- `GET /chat-app` — `@login_required` 보호. 미로그인 시 `/login`으로 302

`login_required` 데코레이터는 `session["username"]` 존재 여부만 본다. 새 보호 라우트가 필요하면 같은 데코레이터를 붙이면 된다.

**세션 키**: `application.secret_key`는 `FLASK_SECRET_KEY` 환경변수가 있으면 그 값, 없으면 `"dev-secret-change-me"` 폴백. 운영에서는 환경변수로 반드시 주입할 것.

**목업 유저** (`MOCK_USERS` in `application.py`): `minji/1234`, `hongkwon/1234`, `test/test`. 비밀번호 해시 미적용 — 로컬/데모 한정. 실제 인증으로 교체할 때는 `MOCK_USERS` 조회 부분만 DB/외부 IDP 호출로 바꾸면 된다. 로그인 페이지(`templates/login.html`) 하단에 목업 계정 표가 노출되어 있으므로 진짜 사용자 컨텍스트에서는 이 표 블록(`.mock-users`)을 제거해야 한다.

### 백엔드 라우트 (`api/application.py`)
- `POST /chat-api` — 사용자 메시지를 룰 매칭하여 응답 반환 (`OPTIONS` 프리플라이트도 처리)
- `GET /health` — `{"status": "ok"}` 헬스체크

백엔드의 응답 로직은 `RULES`(정규식 → 후보 리스트)와 `DEFAULTS`(기본 응답)로 구성. 매칭 시 `random.choice`로 후보 중 하나 반환, 매칭 실패 시 기본 응답. 룰을 늘리거나 줄일 때는 `api/application.py`의 `RULES` 리스트만 손대면 됩니다.

### 프론트엔드-백엔드 결합점
`templates/chat.html`의 `fetchResponse()`가 `http://localhost:8006/chat-api`로 하드코딩된 POST 요청을 보냅니다.
- 요청 본문: `{ "request_message": "<사용자 입력>" }`
- 응답 본문: `{ "response_message": "<봇 응답>" }`

백엔드 주소나 컨트랙트를 바꿀 때는 이 함수와 백엔드 코드를 함께 수정해야 합니다. 프론트엔드는 백엔드 응답을 신뢰하여 `{{{messageOutput}}}` (Handlebars triple-stash, **HTML 이스케이프 미적용**)으로 그대로 삽입하므로 백엔드가 신뢰할 수 없는 HTML을 반환하지 않도록 주의하세요.

### UI 인터랙션 흐름 (`addMessage` 메서드)
사용자 메시지 전송 → 즉시 사용자 메시지 렌더 → 500ms 후 로딩 버블 표시 → 백엔드 응답 도착 → 최소 3.5초 대기 후 응답 표시. `showBubbleAfterSeconds`/`waitSeconds`를 `Promise.all` 없이 순차 `await`하는 구조라 이 타이밍 보장을 수정할 때는 흐름 전체를 같이 봐야 합니다.

### 템플릿 렌더링
- 서버 측: Jinja2 (Flask 기본). `chat.html` 안에서 Handlebars 템플릿을 그대로 보내기 위해 `{% raw %}...{% endraw %}` 블록으로 Jinja2 파싱을 회피합니다.
- 클라이언트 측: Handlebars.js (CDN) — 메시지 버블 두 종류(`#message-template`, `#message-response-template`)를 컴파일하여 사용.

### 정적 파일
`static/images/`의 `logo.png`(헤더 아바타), `jjinchin.png`(봇 메시지 아바타)만 사용. `chat.html`은 `url_for('static', ...)`와 직접 경로(`/static/images/...`)를 혼용하므로 경로 변경 시 두 형태 모두 확인 필요.

## 알아둘 점

- `application.py`에는 `atexit.register`로 등록된 종료 로그가 있을 뿐 별도 정리 로직은 없습니다.
- 챗봇 UI 텍스트와 키 카피("내 찐친 고비", "민지의 chatbot")는 한국어 고정입니다.
- 백엔드의 `Access-Control-Allow-Origin: *`은 개발 편의용입니다. 배포 시에는 프론트엔드 오리진으로 좁히세요.
