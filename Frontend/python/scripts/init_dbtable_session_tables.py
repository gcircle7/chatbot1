"""세션 테이블 생성 및 DB 연결 확인."""

from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "api"))

from dotenv import load_dotenv
import pymysql

load_dotenv(_ROOT / ".env")


def main():
    import os

    cfg = {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER"),
        "password": os.getenv("MYSQL_PASSWORD"),
        "database": os.getenv("MYSQL_DATABASE", "chatbotdb"),
        "charset": "utf8mb4",
    }
    sql_path = _ROOT / "scripts" / "sql" / "create_session_tables.sql"
    raw = sql_path.read_text(encoding="utf-8")

    conn = pymysql.connect(**cfg)
    cur = conn.cursor()
    for stmt in raw.split(";"):
        s = stmt.strip()
        if not s or s.upper().startswith("USE "):
            continue
        cur.execute(s)
    conn.commit()

    cur.execute("SHOW TABLES LIKE 'user_session%'")
    print("session tables:", [r[0] for r in cur.fetchall()])

    cur.execute(
        "SELECT id, login_id, username, email, status FROM user_info "
        "WHERE deleted_at IS NULL LIMIT 10"
    )
    print("users:")
    for row in cur.fetchall():
        print(" ", row)

    conn.close()
    print("done.")


if __name__ == "__main__":
    main()
