"""요청 큐(cb_request_queue) 처리."""

from _utils.db import get_connection


def get_response_queue(request_id: int) -> dict:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT r.response_message
                    FROM cb_response_queue r
                    WHERE r.request_id = %s
                    ORDER BY r.created_at ASC
                    LIMIT 1
                    """,
                    (request_id,),
                )
                response = cur.fetchone()
                if response:
                    return {"ok": True, "response": response}
                else:
                    return {"ok": False, "error": "데이터베이스 연결에 실패했어요.(get_response_queue) " + str(e)}
    except Exception as e:
        print("데이터베이스 조회에 실패했습니다.(get_response_queue) " + str(e))
        return {"ok": False, "error": "데이터베이스 연결에 실패했어요.(get_response_queue) " + str(e)}


def response_send(request_id: int, session_id: int, status: str, **kwargs) -> dict:
    response_message = kwargs.get("response_message")
    image_url = kwargs.get("image_url")
    audio_url = kwargs.get("audio_url")
    video_url = kwargs.get("video_url")

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO cb_response_queue (request_id, session_id, status, response_message, image_url, audio_url, video_url)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (   request_id, 
                        session_id, 
                        status,
                        response_message if response_message else '', 
                        image_url if image_url else '', 
                        audio_url if audio_url else '', 
                        video_url if video_url else ''
                    ),
                )
                conn.commit()
                return {"ok": True}
    except Exception as e:
        print("데이터베이스 등록에 실패했습니다.(response_send) " + str(e))
        return {"ok": False, "error": "데이터베이스 등록에 실패했습니다.(response_send) " + str(e)}
