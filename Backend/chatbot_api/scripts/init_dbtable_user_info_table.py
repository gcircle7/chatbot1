"""user_info 테이블 생성 및 DB 연결 확인."""

from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from db import get_connection


def main():
    sql_path = _ROOT / "scripts" / "sql" / "create_table_user_info.sql"
    raw = sql_path.read_text(encoding="utf-8")

    with get_connection() as conn:
        with conn.cursor() as cur:
            for stmt in raw.split(";"):
                s = stmt.strip()
                if not s or s.upper().startswith("USE "):
                    continue
                cur.execute(s)
            conn.commit()

            cur.execute("SHOW TABLES LIKE 'user_info%'")
            print("user_info table:", [list(r.values())[0] for r in cur.fetchall()])

    print("done.")


if __name__ == "__main__":
    main()
