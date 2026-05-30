"""MySQL 연결 (pymysql)."""

from contextlib import contextmanager
from pathlib import Path
import os

from dotenv import load_dotenv
import pymysql
from pymysql.cursors import DictCursor

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")


def _db_config() -> dict:
    return {
        "host": os.environ.get("MYSQL_HOST", "localhost"),
        "port": int(os.environ.get("MYSQL_PORT", "3306")),
        "user": os.environ.get("MYSQL_USER", "root"),
        "password": os.environ.get("MYSQL_PASSWORD", ""),
        "database": os.environ.get("MYSQL_DATABASE", "chatbotdb"),
        "charset": "utf8mb4",
        "cursorclass": DictCursor,
        "autocommit": False,
    }


@contextmanager
def get_connection():
    conn = pymysql.connect(**_db_config())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
