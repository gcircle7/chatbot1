"""Redis Pub/Sub 기반 MessageBroker 구현."""

import json
import logging

import redis

from .base import MessageBroker, Subscription

logger = logging.getLogger(__name__)


class RedisSubscription(Subscription):
    """Redis pubsub 핸들을 Subscription 인터페이스로 감싼다."""

    def __init__(self, pubsub):
        self._pubsub = pubsub

    def get(self, timeout: float) -> dict | None:
        """timeout 동안 메시지 1건 대기. 없으면 None."""
        msg = self._pubsub.get_message(timeout=timeout, ignore_subscribe_messages=True)
        if msg and msg.get("type") == "message":
            return self._decode(msg.get("data"))
        return None

    def listen(self):
        """구독 채널의 메시지를 무한히 yield."""
        for msg in self._pubsub.listen():
            if msg.get("type") == "message":
                decoded = self._decode(msg.get("data"))
                if decoded is not None:
                    yield decoded

    @staticmethod
    def _decode(data):
        """JSON 문자열을 dict로 파싱. 실패 시 raw 키로 감싼다."""
        if data is None:
            return None
        try:
            return json.loads(data)
        except (TypeError, ValueError):
            return {"raw": data}

    def close(self) -> None:
        try:
            self._pubsub.close()
        except Exception as e:  # noqa: BLE001
            logger.warning("Redis 구독 종료 실패: %s", e)


class RedisBroker(MessageBroker):
    """Redis Pub/Sub 발행·구독 브로커."""

    def __init__(self, host: str, port: int, db: int):
        self._redis = redis.Redis(
            host=host, port=port, db=db,
            decode_responses=True,       # str로 수신 (json.loads 바로 가능)
            socket_keepalive=True,
            health_check_interval=30,
        )

    def publish(self, channel: str, payload: dict) -> None:
        """채널에 JSON payload 발행. 실패해도 예외를 올리지 않는다."""
        try:
            self._redis.publish(channel, json.dumps(payload, ensure_ascii=False))
        except Exception as e:  # noqa: BLE001 - 통지 실패는 폴링 fallback이 흡수
            logger.warning("브로커 publish 실패(channel=%s): %s", channel, e)

    def subscribe(self, *channels: str) -> RedisSubscription:
        """채널 구독 후 Subscription 핸들 반환."""
        pubsub = self._redis.pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe(*channels)
        return RedisSubscription(pubsub)

    def ping(self) -> bool:
        """Redis 연결 상태 확인."""
        try:
            return bool(self._redis.ping())
        except Exception as e:  # noqa: BLE001
            logger.warning("Redis ping 실패: %s", e)
            return False

    def close(self) -> None:
        """Redis 클라이언트 연결 종료."""
        try:
            self._redis.close()
        except Exception as e:  # noqa: BLE001
            logger.warning("Redis 연결 종료 실패: %s", e)
