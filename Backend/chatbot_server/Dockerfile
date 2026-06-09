FROM python:3.11-slim

# 비root 사용자 생성 (보안)
RUN useradd -m -u 1000 appuser

WORKDIR /app

# uv 설치
RUN pip install uv

# 의존성 파일 먼저 복사 (레이어 캐시 활용)
COPY pyproject.toml uv.lock ./

# 의존성 설치
RUN uv sync --frozen --no-dev

# 소스 복사
COPY . .

# 로그 디렉토리 생성 및 소유권 설정
RUN mkdir -p data/log && chown -R appuser:appuser /app

USER appuser

CMD ["uv", "run", "python", "chatbot_server_main.py"]
