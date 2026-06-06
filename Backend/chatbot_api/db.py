"""MySQL 연결 — DBUtils 커넥션 풀.

기존 get_connection() 컨텍스트 매니저 인터페이스는 그대로 유지하고
내부만 PooledDB 에서 연결을 대여/반환하도록 바꿨다(호출부 변경 없음).
"""

from contextlib import contextmanager
from pathlib import Path
import os
import threading

from dotenv import load_dotenv
import pymysql
from pymysql.cursors import DictCursor
from dbutils.pooled_db import PooledDB

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")

_pool: PooledDB | None = None
_pool_lock = threading.Lock()


def _build_pool() -> PooledDB:
    return PooledDB(
        creator=pymysql,
        maxconnections=int(os.environ.get("DB_POOL_MAX", "10")),
        mincached=1,
        maxcached=4,
        blocking=True,
        ping=1,
        host=os.environ.get("MYSQL_HOST", "localhost"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=(os.environ.get("MYSQL_USER", "root") or "").strip(),
        password=os.environ.get("MYSQL_PASSWORD", ""),
        database=os.environ.get("MYSQL_DATABASE", "chatbotdb"),
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
    )


def _get_pool() -> PooledDB:
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is None:
            _pool = _build_pool()
    return _pool


@contextmanager
def get_connection():
    conn = _get_pool().connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()  # 실제 종료가 아니라 풀로 반환
