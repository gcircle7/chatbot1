# chatbot1 — 모노레포

세 개의 독립 패키지를 단일 저장소에서 관리합니다.

---

## 패키지 구성

| 패키지 | 경로 | Python |
|--------|------|--------|
| chatbot_api | `Backend/chatbot_api/` | 3.12+ |
| chatbot_server | `Backend/chatbot_server/` | 3.11 |
| frontend (python) | `Frontend/python/` | 3.12+ |

---

## 이력(History) 관리 방식

세 패키지는 **하나의 git 저장소**에서 관리되지만, 각 패키지의 변경 이력은 **커밋 메시지의 scope**와 **브랜치 네이밍**으로 구분합니다.

git은 파일 단위로 이력을 추적하므로, 특정 패키지의 변경 이력만 조회할 수 있습니다.

### 패키지별 이력 조회

```bash
# chatbot_api 변경 이력만 보기
git log --oneline -- Backend/chatbot_api/

# chatbot_server 변경 이력만 보기
git log --oneline -- Backend/chatbot_server/

# frontend 변경 이력만 보기
git log --oneline -- Frontend/python/

# 특정 파일의 이력
git log --oneline -- Backend/chatbot_server/app/chatbot.py
```

---

## 브랜치 전략

```
main               ← 배포 기준 (직접 push 금지)
dev                ← 통합 개발 브랜치
api/feature-name   ← chatbot_api 작업
server/feature-name ← chatbot_server 작업
front/feature-name  ← frontend 작업
```

브랜치 이름 앞에 패키지 prefix를 붙여 어느 패키지 작업인지 한눈에 구분합니다.

```bash
# 예시
git checkout -b api/add-auth
git checkout -b server/memory-refactor
git checkout -b front/login-page
```

---

## 커밋 메시지 규칙

```
<type>(<패키지>): <설명>
```

**패키지 scope:**

| scope | 대상 |
|-------|------|
| `api` | Backend/chatbot_api |
| `server` | Backend/chatbot_server |
| `front` | Frontend/python |
| `root` | 루트 설정 파일 |

```bash
# 예시
git commit -m "feat(api): 세션 조회 엔드포인트 추가"
git commit -m "fix(server): 메모리 매니저 누락 처리"
git commit -m "refactor(front): 백엔드 클라이언트 분리"
git commit -m "chore(root): .gitignore 업데이트"
```

scope를 일관되게 쓰면 나중에 `git log --grep`으로 패키지별 이력만 필터링할 수 있습니다.

```bash
# "api" 관련 커밋만 검색
git log --oneline --grep="(api)"
```

---

## 작업 흐름

### 단일 패키지 작업

```bash
git checkout dev
git pull origin dev

# 패키지별 브랜치 생성
git checkout -b api/my-feature

# 해당 패키지 디렉토리에서만 작업
cd Backend/chatbot_api
# ... 코드 수정 ...

# 루트에서 커밋
cd ../..
git add Backend/chatbot_api/
git commit -m "feat(api): 내용"

git push origin api/my-feature
```

### 여러 패키지 동시 작업 시 유의사항

> ⚠️ 여러 패키지를 동시에 수정한 경우, `git add .` 대신 **패키지 경로를 지정해서 커밋을 분리**하는 것을 권장합니다.

```bash
# 좋은 예 — 패키지별로 커밋 분리
git add Backend/chatbot_api/
git commit -m "feat(api): 인증 처리 추가"

git add Backend/chatbot_server/
git commit -m "fix(server): 응답 포맷 수정"

# 피해야 할 예 — 여러 패키지가 한 커밋에 섞임
git add .
git commit -m "여러 작업"   # ← 이력 추적이 어려워짐
```

---

## 로컬 환경 설정

각 패키지는 독립된 가상환경을 사용합니다. 패키지 디렉토리에서 개별 설정하세요.

```bash
cd Backend/chatbot_api        # 또는 Backend/chatbot_server / Frontend/python
cp .env.example .env          # 환경변수 파일 생성 후 값 입력
uv sync                       # 의존성 설치
uv run python application.py  # 실행 (패키지마다 진입점 다를 수 있음)
```

> `uv`가 없으면: `pip install uv`

---

## 환경변수 유의사항

- 각 패키지에 `.env.example`이 있으며 필요한 키 목록이 적혀 있습니다.
- `.env`는 `.gitignore`로 차단되어 **절대 커밋되지 않습니다.**
- `.env.example`은 실제 값 없이 키 이름만 남겨 커밋에 포함합니다.
- 패키지마다 별도의 `.env`가 필요하며 공유되지 않습니다.

---

## 자주 쓰는 Git 명령어

```bash
# 최신 코드 받기
git pull origin main

# 내 브랜치를 dev 기준으로 최신화
git fetch origin
git rebase origin/dev

# 특정 패키지에 어떤 파일이 변경됐는지 확인
git diff HEAD -- Backend/chatbot_server/

# 패키지별 변경 파일 목록만 보기
git diff --name-only HEAD -- Frontend/python/

# 원격 브랜치 삭제 (작업 완료 후)
git push origin --delete api/my-feature
```

---

## GitHub 저장소

- **URL:** https://github.com/gcircle7/chatbot1
- **기본 브랜치:** `main`
- **관리자:** KimHongKwon (gcircle3@gmail.com)
