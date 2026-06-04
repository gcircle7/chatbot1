# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 저장소 개요

"홍자봇 / 내 찐친 고비" 챗봇의 모노레포. **세 개의 독립 프로세스**가 단일 git 저장소에서 관리되며, 서로 HTTP나 함수 호출이 아니라 **MySQL 큐 테이블을 통해 비동기로 디커플링**되어 있다.

| 패키지 | 경로 | 역할 | Python | 진입점 |
|--------|------|------|--------|--------|
| frontend | `Frontend/python/` | 웹 UI·로그인 세션 (Flask) | 3.12+ | `application.py <port>` |
| chatbot_api | `Backend/chatbot_api/` | 인증·채팅 API (Flask, 포트 8006) | 3.12 | `application.py [port]` |
| chatbot_server | `Backend/chatbot_server/` | OpenAI 챗봇 워커 (HTTP 없음) | 3.11 | `chatbot_main.py` |

각 패키지는 **독립된 `.venv`·`pyproject.toml`·`.env`** 를 가진다. 패키지 디렉토리 안에서 작업하고 실행해야 한다(임포트와 `.env` 로딩이 cwd 기준).

## 데이터 흐름 (핵심 아키텍처)

세 프로세스는 직접 통신하지 않는다. 사용자 메시지 한 건이 처리되는 경로:

```
브라우저 (chat.html)
  │  POST /chat-api  { request_message, session_token }
  ▼
chatbot_api (8006)  /chat-api
  │  ① auth_check_session(session_token) 으로 db_user_id·session_id 확인
  │  ② cb_request_queue 에 row INSERT (status='pending')          ← ChatbotClient.add_user_message
  │  ③ cb_request_queue.status / cb_response_queue 를 1초 간격 폴링 ← get_response_content (최대 20초)
  ▼
[ MySQL: cb_request_queue / cb_response_queue ]   ← 두 프로세스의 유일한 접점
  ▲
chatbot_server (워커, _work_loop 루프)
  │  ① get_request_queue(): pending + 세션 active 인 요청 1건 집어 status='in_progress'
  │  ② 세션별 Chatbot 인스턴스로 OpenAI 호출 → 응답 생성
  │  ③ response_send(): cb_response_queue INSERT, cb_request_queue.status='completed'
```

- **api ↔ server 는 오직 큐 테이블로만 연결된다.** 한쪽 코드를 바꿔도 컨트랙트(테이블 컬럼)만 지키면 다른 쪽은 무관하다.
- api 의 폴링 타임아웃은 20초(`chatbot_client.py`), 카카오 경로(`/chat-kakao`)는 3초 후 ngrok callbackUrl 로 비동기 응답하는 별도 흐름.
- frontend ↔ api 는 HTTP. `Frontend/python/backend_client.py` 가 `CHATBOT_API_BASE`(기본 `http://localhost:8006`)에 `/auth/*` 를 붙여 호출. 브라우저 채팅은 `CHATBOT_CHAT_URL`(기본 `{베이스}/chat-api`)로 직접 POST. 로그인 세션 검증은 매 보호 라우트마다 api 의 `/auth/session/validate` 를 탄다(`login_required` 데코레이터).

## 실행 방법

세 프로세스를 **각각 다른 터미널**에서 띄워야 전체 동작한다. 의존성은 모두 `uv` 사용.

```powershell
# 1) 챗봇 워커 — 반드시 패키지 루트에서 실행 (app.* / _utils.* 임포트, .env 로딩)
cd Backend\chatbot_server
uv sync
uv run python chatbot_main.py

# 2) 인증·채팅 API — 포트 생략 시 8006
cd Backend\chatbot_api
uv sync
uv run python application.py            # NGROK_DISABLE=1 로 ngrok 끌 수 있음

# 3) 프론트엔드 — 포트 인자 필수 (sys.argv[1], 누락 시 IndexError)
cd Frontend\python
uv sync
uv run python application.py 8000
```

UI 확인: `http://localhost:8000/` → 로그인 후 `/chat-app`. API 헬스체크: `GET http://localhost:8006/health`.

각 패키지에 `.env.example` 이 있으면 `cp .env.example .env` 후 값 채우기. **`Backend/chatbot_server` 는 `.env.example` 이 없으므로** 직접 만들어야 하며, MySQL 변수 외에 `OPENAI_API_KEY`, `PINECONE_API_KEY`, `MONGO_CLUSTER_URI`, `CHATBOT_NAME` 이 필요하다(`_utils/common.py`, `app/memory_manager.py`).

## 데이터 저장소

- **MySQL** (`chatbotdb`, 세 패키지 공유): `user_info`, `user_session`, `cb_request_queue`, `cb_response_queue`, `cb_chat_history`. 연결은 각 패키지의 `db.py` / `_utils/db.py`(pymysql, DictCursor, autocommit=False).
  - 스키마·초기화 스크립트는 `Backend/chatbot_api/scripts/` 에 모여 있다: `sql/create_*.sql` 과 이를 실행하는 `init_dbtable_*.py`(테이블별 1개). 각 스크립트는 `chatbot_api/db.py` 의 `get_connection` 을 재사용하므로 **`chatbot_api/.env` 를 설정한 뒤 그 패키지 안에서** `uv run python scripts/init_dbtable_*.py` 로 실행한다.
- **MongoDB** (`jjinchin` DB, chatbot_server 전용): `chats`(원본 대화), `memory`(요약된 장기기억). `app/memory_manager.py`.
- **Pinecone** (`jjinchin-memory` 인덱스, chatbot_server 전용): 기억 요약문 임베딩 벡터. MongoDB `memory._id` 와 같은 정수 id 로 연결된다.

## chatbot_server 내부 구조

`ChatbotServer._work_loop`(`app/chatbot_server.py`)가 메인 루프. 세션별로 `Chatbot` 인스턴스(`app/chatbot.py`)를 캐시하고, 활성 세션이 사라지면 인스턴스를 제거한다.

`Chatbot.send_request` 한 번에 일어나는 일:
1. `WarningAgent`(`app/warning_agent.py`)가 유해 발화를 감지하면 경고 응답으로 단락.
2. `retrieve_memory`: `MemoryManager.needs_memory`(과거 기억을 묻는지 LLM 판단) → Pinecone 검색 → MongoDB 본문 조회 → `filter`(유사도 LLM 재검증). 통과 시 `[귓속말]` 형태로 마지막 유저 메시지에 instruction 주입.
3. OpenAI `chat.completions` 호출(`model.advanced` = `gpt-4o`, `_utils/common.py`의 `Model`).
4. context length 초과 예외 시 오래된 메시지를 잘라 재시도(`_send_request` 재귀), 그리고 `handle_token_limit` 으로 누적 토큰을 사전 제어.
5. `clean_context` 로 주입했던 instruction 을 제거한 뒤 `ChatHistoryManager` 로 DB 저장.

장기기억 빌드(`MemoryManager.build_memory`: 전날 대화를 주제별 5개 이하로 요약 → Pinecone/Mongo 적재)는 현재 `_background_task` 가 주석 처리되어 자동 실행되지 않는다.

## 알아둘 점 / 함정

- **워커 진입점은 `chatbot_main.py`** (신규, 아직 untracked). 과거의 `Backend/chatbot_server/main.py` 는 삭제됨. `cb_server.run()` 은 `_work_loop` 를 메인 스레드에서 블로킹 실행한다.
- `Frontend/python/CLAUDE.md` 는 **옛 룰 베이스 아키텍처를 설명하는 구버전 문서**라 현재 코드(인증 API + 큐 기반)와 맞지 않는다. 프론트 작업 시 코드를 신뢰할 것.
- `chat.html` 은 백엔드 응답을 Handlebars triple-stash(`{{{...}}}`, **HTML 이스케이프 미적용**)로 삽입한다. 백엔드가 신뢰 불가 HTML 을 반환하지 않게 주의.
- chatbot_api 의 CORS 는 `Access-Control-Allow-Origin: *`(개발 편의용). 배포 시 좁힐 것.
- 비밀번호는 `bcrypt` 해시(`auth.py`). 회원가입·로그인·재설정 모두 chatbot_api 에서 처리되고 프론트는 `backend_client` 를 거친다.

## 브랜치·커밋 규칙 (README.md 발췌)

- 브랜치: `main`(배포·직접 push 금지) / `dev`(통합) / `api|server|front/feature-name`(패키지 prefix).
- 커밋: `<type>(<scope>): <설명>` — scope 는 `api` / `server` / `front` / `root`. 한국어로 작성.
- **여러 패키지를 동시에 수정했으면 `git add .` 대신 패키지 경로별로 커밋을 분리**한다. 패키지별 이력은 `git log -- <경로>` 또는 `git log --grep="(scope)"` 로 조회.
