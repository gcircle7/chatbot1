"""큐 테이블 정리(GC).

완료/실패 처리되어 더 이상 필요 없는 오래된 큐 row 를 주기적으로 삭제한다.
무한 누적으로 폴링/조회 쿼리가 느려지는 것을 막는다.
"""

import logging

from _utils.db import get_connection

logger = logging.getLogger(__name__)


def cleanup_old_queue_rows(days: int = 1) -> int:
    """N일 이상 지난 완료성 큐 row 를 삭제하고 삭제 건수를 반환.

    - cb_response_queue: 생성 후 N일 경과 분(이미 수신됐거나 미수신이어도 무의미)
    - cb_request_queue: completed/failed/cancelled 상태 + N일 경과 분
    response 를 먼저 지워 FK 참조가 있어도 안전하게 한다.
    """
    deleted = 0
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM cb_response_queue
                    WHERE created_at < (NOW() - INTERVAL %s DAY)
                    """,
                    (days,),
                )
                deleted += cur.rowcount
                cur.execute(
                    """
                    DELETE FROM cb_request_queue
                    WHERE status IN ('completed', 'failed', 'cancelled')
                      AND created_at < (NOW() - INTERVAL %s DAY)
                    """,
                    (days,),
                )
                deleted += cur.rowcount
        return deleted
    except Exception:
        logger.exception("큐 정리 실패(cleanup_old_queue_rows)")
        return 0
