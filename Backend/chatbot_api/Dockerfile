FROM python:3.12-slim

WORKDIR /app

# uv 설치
RUN pip install uv

# 의존성 파일 먼저 복사 (레이어 캐시 활용)
COPY pyproject.toml uv.lock ./

# 의존성 설치
RUN uv sync --frozen --no-dev

# 소스 복사
COPY . .

EXPOSE 8006

CMD ["uv", "run", "gunicorn", "--workers", "4", "--bind", "0.0.0.0:8006", "chatbot_api_main:application"]
