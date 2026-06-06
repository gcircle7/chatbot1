# 시스템 구조 개선 제안 및 적용 계획

> 작성일: 2026-06-06
> 대상: 홍자봇 / 내 찐친 고비 챗봇 모노레포 (frontend · chatbot_api · chatbot_server)
> 배경: 세 프로세스 기동 → Playwright 로 로그인·회원가입·채팅(실제 OpenAI 응답)·멀티턴 E2E 검증 후 도출한 구조적 개선점.

---

## 1. 진단 요약

세 프로세스는 **MySQL 큐 테이블(`cb_request_queue` / `cb_response_queue`)을 통해서만** 비동기로 연결된다.
E2E 동작은 정상이나, 다음과 같은 **확장성·안정성·보안** 측면의 구조적 한계가 확인되었다.

| # | 영역 | 문제 | 근거 위치 |
|---|------|------|-----------|
| 1 | 처리량 | 단일 워커 직렬 처리 — OpenAI 호출이 블로킹되어 동시 사용자 증가 시 큐 적체 | `chatbot_server/app/chatbot_server.py` `_work_loop` |
| 2 | 동시성 | 큐 픽업에 행 잠금 없음(`SELECT` 후 별도 `UPDATE`) — 다중 워커 시 중복 처리 | `chatbot_server/app/request_service.py` `get_request_queue` |
| 3 | 통신 | 폴링 기반(API 1초 / 워커 5초 sleep) — 지연 + DB 부하 | `chatbot_api/chatbot_client.py`, `chatbot_server.py` |
| 4 | 안정성 | `print` 한 줄(이모지)이 cp949 인코딩 오류로 워커 프로세스 전체 다운(실제 발생). 구조화된 로깅 부재 | `chat_history_manager.py:86` 등 |
| 5 | 확장성 | 상태ful 워커 — 세션별 `Chatbot` 인스턴스를 프로세스 메모리에 캐시 → 장애 복구·수평 확장 취약 | `chatbot_server.py` `self._chatbot` |
| 6 | 보안 | 카카오 경로에서 `db_user_id=2`, `session_id=2` 하드코딩 → 모든 카카오 사용자가 동일 세션 공유 | `chatbot_api/application.py` `/chat-kakao` |
| 7 | 운영 | 커넥션 풀 부재(매 쿼리 새 연결) + 완료 큐 row 정리(GC) 없음 | `db.py`, `_utils/db.py` |
| 8 | 기능 | 장기기억 빌드(`_background_task`)가 주석 처리되어 비활성 | `chatbot_server.py:36` |

---

## 2. 사용자 수락 사항 (적용 결정)

아래는 제안에 대한 사용자의 결정 사항이다. **#1~#7 은 적용**, **#8 은 현 상태 유지**.

### #1 큐 처리 모델 개선 — **적용**
- ① 세션 단위 동시 처리(워커 풀)로 OpenAI 호출 병렬화.
- ② `get_request_queue` 를 `SELECT ... FOR UPDATE SKIP LOCKED` 로 변경해 워커 N대 안전 확장.

### #2 큐 픽업 행 잠금 — **적용**
- `SELECT ... WHERE status='pending' ... LIMIT 1 FOR UPDATE SKIP LOCKED` + **같은 트랜잭션 내 `UPDATE`**.
- 수평 확장의 전제 조건.

### #3 폴링 → 메시지 브로커 — **적용**
- 폴링 기반 통신을 **Redis Pub/Sub** 로 변경.
- **추후 설정(`BROKER_TYPE`)으로 메시지 큐(RabbitMQ 등) 푸시 기반으로 교체 가능**하도록 브로커 추상화 인터페이스를 둔다.

### #4 운영 안정성 — **적용**
- 모든 `print` 를 `logging` 모듈로 전환.
- 로그는 **프로세스별 루트의 `data/log/` 폴더에 일자별 파일**로 저장.

### #5 상태ful 워커 → 스테이트리스 — **적용**
- 컨텍스트를 **매 요청 DB/Redis 에서 로드**하는 스테이트리스 워커로 전환(인메모리 세션 캐시 제거).

### #6 카카오 하드코딩 세션 — **적용**
- 카카오 사용자 식별자 기반으로 세션을 매핑/생성하도록 적절히 처리(채널 전용 계정·세션).

### #7 커넥션 풀 + 큐 GC — **적용**
- **커넥션 풀(DBUtils/SQLAlchemy pool)** 도입.
- 완료된 큐 row 의 주기적 정리(GC) 추가.

### #8 장기기억 기능 — **유지(보류)**
- 추후 별도 개발 예정이므로 현재 비활성 상태를 그대로 둔다.

---

## 3. 적용 아키텍처 개요

### 3.1 통신 구조 (변경 후)

```
브라우저 ──POST /chat-api──► chatbot_api
                                │ ① cb_request_queue INSERT (status=pending)
                                │ ② broker.publish("chat:requests", {request_id, session_id})  ← 워커 즉시 깨우기
                                │ ③ broker.subscribe("chat:response:{request_id}") 로 응답 대기
                                ▼
              [ MySQL 큐(영속·정합성) ] + [ Redis Pub/Sub(즉시 통지) ]
                                ▲
chatbot_server (디스패처 + 워커 풀)
   │ ① broker 구독 + 짧은 폴링 fallback
   │ ② claim_request(): SELECT ... FOR UPDATE SKIP LOCKED + UPDATE in_progress (단일 트랜잭션)
   │ ③ ThreadPoolExecutor 로 세션별 병렬 처리(같은 세션은 직렬)
   │ ④ 스테이트리스: 요청마다 DB 에서 컨텍스트 로드 → 처리 → 저장 → 폐기
   │ ⑤ response_send() + broker.publish("chat:response:{request_id}")
```

- **MySQL 큐는 source of truth(영속성·SKIP LOCKED) 로 유지**, Redis Pub/Sub 는 "빠른 깨우기" 통지 채널.
- Pub/Sub 유실에 대비해 워커·API 모두 **짧은 폴링 fallback** 을 유지(정합성 보장).

### 3.2 브로커 추상화 (교체 가능 구조)

```
broker/
  base.py          # MessageBroker 인터페이스(ABC): publish / subscribe / close
  redis_broker.py  # RedisBroker 구현
  __init__.py      # get_broker(): BROKER_TYPE 로 구현체 선택 (redis | rabbitmq[추후])
```

### 3.3 로깅

- `setup_logging(process_name)` 공통 모듈. 콘솔 + 파일 핸들러(UTF-8).
- 파일 경로: `<패키지 루트>/data/log/YYYY-MM-DD.log` (`TimedRotatingFileHandler`, 자정 롤오버).

### 3.4 DB 커넥션 풀

- `DBUtils.PooledDB` 로 `db.py` 내부 교체.
- 기존 `get_connection()` 컨텍스트 매니저 **인터페이스는 그대로 유지**(호출부 무변경), 내부만 풀에서 대여.

### 3.5 스테이트리스 워커

- `self._chatbot` 인메모리 캐시 제거.
- 요청마다 `Chatbot` 생성 시 `restore_session_chats()` 로 DB 컨텍스트 로드 → 처리 → DB 저장 → 인스턴스 폐기.

### 3.6 카카오 채널 세션

- `get_or_create_channel_session(channel_user_id)`:
  카카오 `userRequest.user.id` 기준으로 채널 전용 계정(`user_info`, role=`channel`)·세션을 조회/생성하여 사용자별로 분리.

---

## 4. 신규/변경 구성요소

| 구분 | 경로 | 내용 |
|------|------|------|
| 신규 | `*/broker/` | 메시지 브로커 추상화(Redis 구현, RabbitMQ 확장 지점) |
| 신규 | `*/logging_config.py` (또는 `_utils/`) | 일자별 파일 로깅 설정 |
| 변경 | `*/db.py`, `*/_utils/db.py` | 커넥션 풀(DBUtils) |
| 변경 | `chatbot_server/app/chatbot_server.py` | 스테이트리스 + 워커 풀 + 디스패처 + GC |
| 변경 | `chatbot_server/app/request_service.py` | `claim_request()` SKIP LOCKED |
| 변경 | `chatbot_api/chatbot_client.py` | broker 기반 응답 대기 |
| 변경 | `chatbot_api/application.py` + `session_service.py` | 카카오 채널 세션 |
| 변경 | 전 패키지 | `print` → `logging` 전환 |
| 설정 | `.env` / `.env.example` | `BROKER_TYPE`, `REDIS_*`, `WORKER_CONCURRENCY`, `QUEUE_GC_DAYS`, `DB_POOL_MAX` |
| 인프라 | Docker | `redis:7-alpine` 컨테이너(`chatbot-redis`, 6379) |

---

## 5. 적용 범위에서 제외 / 보류

- **#8 장기기억 빌드** — 추후 별도 개발(현 상태 유지).
- 프론트엔드 채팅 컨트랙트(`{ db_user_id, session_token, request_message }` ↔ `{ status, response_message, error_message }`)는 **변경하지 않음**(API 내부만 개선).
- 큐 테이블 컬럼(컨트랙트)은 유지하여 점진적 마이그레이션 보장.