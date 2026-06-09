"""프로세스별 일자 로깅 설정.

로그는 프로세스 루트의 data/log/ 폴더에 일자별 파일로 저장한다.
 - 현재 로그 파일: data/log/<process_name>.log
 - 자정 롤오버 시: data/log/<process_name>.log.YYYY-MM-DD (날짜별로 분리 보관)
"""

import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"

# .env 미로딩 상태에서도 환경변수만으로 동작하도록 os.getenv 직접 참조
# .env 는 application.py 에서 load_dotenv() 후 이 함수를 호출하므로 정상 반영됨
def _env_level() -> int:
    val = os.getenv("LOG_LEVEL", "INFO").upper()
    return getattr(logging, val, logging.INFO)


def setup_logging(process_name: str, root_dir=None, level: int | None = None) -> logging.Logger:
    """루트 로거에 콘솔 + 일자 파일 핸들러를 설정한다. 중복 호출은 무시.

    레벨은 .env 의 LOG_LEVEL(DEBUG|INFO|WARNING|ERROR) 로 제어한다.
    level 인자를 명시하면 .env 보다 우선한다.
    """
    root = Path(root_dir) if root_dir else Path.cwd()
    log_dir = root / "data" / "log"
    log_dir.mkdir(parents=True, exist_ok=True)

    effective_level = level if level is not None else _env_level()

    logger = logging.getLogger()
    if getattr(logger, "_chatbot_configured", False):
        return logger

    logger.setLevel(effective_level)
    formatter = logging.Formatter(_FORMAT, datefmt=_DATEFMT)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    console = logging.StreamHandler(stream=sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)

    file_handler = TimedRotatingFileHandler(
        log_dir / f"{process_name}.log",
        when="midnight",
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    logger._chatbot_configured = True  # type: ignore[attr-defined]
    if effective_level <= logging.DEBUG:
        logger.info("로깅 초기화 완료 — 파일: %s  레벨: %s",
                    log_dir / f"{process_name}.log",
                    logging.getLevelName(effective_level))
    return logger
