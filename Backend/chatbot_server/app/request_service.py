"""요청 큐(cb_request_queue) 처리."""

import logging

from _utils.db import get_connection

logger = logging.getLogger(__name__)


def claim_request() -> dict:
    """pending + 세션 active 인 요청 1건을 원자적으로 집어 in_progress 로 만든다.

    FOR UPDATE ... SKIP LOCKED 로 행을 잠근 채 상태를 바꾸므로,
    워커가 여러 대여도 같은 요청을 중복으로 집지 않는다(수평 확장의 전제).
    SELECT 와 UPDATE 가 같은 트랜잭션 안에서 일어난다.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT q.id, q.db_user_id, q.session_id, q.request_message, q.status
                    FROM cb_request_queue q
                    INNER JOIN user_session s ON s.id = q.session_id
                    WHERE q.status = 'pending'
                      AND s.status = 'active'
                    ORDER BY q.created_at ASC
                    LIMIT 1
                    FOR UPDATE OF q SKIP LOCKED
                    """,
                )
                request = cur.fetchone()
                if request:
                    cur.execute(
                        """
                        UPDATE cb_request_queue
                        SET status = 'in_progress'
                        WHERE id = %s
                        """,
                        (request["id"],),
                    )
                # with 블록 종료 시 commit → 행 잠금 해제
                return {"ok": True, "request": request}
    except Exception as e:
        logger.exception("요청 큐 픽업 실패(claim_request)")
        return {"ok": False, "error": "데이터베이스 연결에 실패했어요.(claim_request) " + str(e)}


def request_status_update(request_id: int, status: str, **kwargs):
    error_message = kwargs.get("error_message")
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                if status == "failed":
                    cur.execute(
                        """
                        UPDATE cb_request_queue
                        SET status = %s, error_message = %s
                        WHERE id = %s
                        """,
                        (status, error_message if error_message else None, request_id),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE cb_request_queue
                        SET status = %s
                        WHERE id = %s
                        """,
                        (status, request_id),
                    )
    except Exception:
        logger.exception("요청 상태 업데이트 실패(request_status_update) request_id=%s", request_id)
