# chatbot1 — 모노레포

Flask 기반 챗봇 프로젝트를 단일 저장소(Monorepo)로 관리합니다.

---

## 폴더 구조

```
chatbot1/
├── Backend/
│   ├── chatbot_api/       # Flask API 서버 (Python 3.12+)
│   └── chatbot_server/    # 챗봇 코어 서버 (Python 3.11)
├── Frontend/
│   └── python/            # Flask 프론트엔드 서버 (Python 3.12+)
└── .gitignore             # 루트 통합 gitignore
```

각 패키지는 독립적인 `pyproject.toml`과 가상환경(`.venv`)을 가지며, 서로 의존하지 않습니다.

---

## 로컬 개발 환경 설정

각 패키지 디렉토리에서 개별적으로 설정합니다.

```bash
# 예: chatbot_server
cd Backend/chatbot_server
cp .env.example .env      # 환경변수 설정
uv sync                   # 의존성 설치
uv run python main.py     # 실행
```

> `uv`가 없으면 먼저 설치: `pip install uv`

---

## 환경변수

각 패키지 루트에 `.env.example` 파일이 있습니다.  
`.env` 파일을 직접 만들어 실제 값을 채워 넣으세요.  
`.env`는 `.gitignore`에 포함되어 있으므로 **절대 커밋되지 않습니다.**

---

## Git 브랜치 전략

```
main        ← 배포 기준 브랜치 (직접 push 지양)
dev         ← 통합 개발 브랜치
feature/*   ← 기능 개발 (예: feature/login-api)
fix/*       ← 버그 수정 (예: fix/session-timeout)
```

### 기본 작업 흐름

```bash
# 새 기능 시작
git checkout dev
git pull origin dev
git checkout -b feature/my-feature

# 작업 후 커밋
git add .
git commit -m "feat(chatbot_api): 로그인 API 추가"

# dev로 병합
git checkout dev
git merge feature/my-feature
git push origin dev

# 배포 시 main으로 병합
git checkout main
git merge dev
git push origin main
```

---

## 커밋 메시지 규칙

```
<type>(<scope>): <설명>
```

| type | 용도 |
|------|------|
| `feat` | 새 기능 |
| `fix` | 버그 수정 |
| `chore` | 빌드/설정 변경 |
| `docs` | 문서 수정 |
| `refactor` | 리팩토링 |
| `test` | 테스트 추가/수정 |

**scope 예시:** `chatbot_api`, `chatbot_server`, `frontend`, `root`

```bash
# 예시
git commit -m "feat(chatbot_server): 메모리 매니저 추가"
git commit -m "fix(frontend): 세션 만료 오류 수정"
git commit -m "chore(root): .gitignore 업데이트"
```

---

## GitHub 저장소

- **URL:** https://github.com/gcircle7/chatbot1
- **기본 브랜치:** `main`
- **작성자:** KimHongKwon (gcircle3@gmail.com)

### 원격 저장소 연결 확인

```bash
git remote -v
# origin  https://github.com/gcircle7/chatbot1.git (fetch)
# origin  https://github.com/gcircle7/chatbot1.git (push)
```

### 자주 쓰는 명령어

```bash
# 최신 코드 받기
git pull origin main

# 변경사항 올리기
git push origin <브랜치명>

# 브랜치 목록 확인
git branch -a

# 원격 브랜치 삭제
git push origin --delete <브랜치명>

# 태그 생성 및 push (버전 관리)
git tag v1.0.0
git push origin v1.0.0
```

---

## .gitignore 주요 제외 항목

| 항목 | 이유 |
|------|------|
| `.env`, `.env.*` | API 키 등 민감 정보 |
| `.venv/` | 가상환경 (재설치 가능) |
| `__pycache__/`, `*.pyc` | Python 컴파일 캐시 |
| `sysfiles/` | 서버 생성 파일 |
| `.DS_Store` | macOS 시스템 파일 |

---

## 새 패키지 추가 시

1. 적절한 위치에 디렉토리 생성 (`Backend/` 또는 `Frontend/`)
2. `pyproject.toml` 및 `.env.example` 작성
3. 해당 패키지의 `.gitignore` 추가 (또는 루트 `.gitignore`에 경로 추가)
4. 이 README의 폴더 구조 섹션 업데이트
