"""Redis Pub/Sub 기반 MessageBroker 구현."""

import json
import logging

import redis

from .base import MessageBroker, Subscription

logger = logging.getLogger(__name__)


class RedisSubscription(Subscription):
    def __init__(self, pubsub):
        self._pubsub = pubsub

    def get(self, timeout: float) -> dict | None:
        # ignore_subscribe_messages=True 로 구독 확인 메시지는 건너뛴다.
        msg = self._pubsub.get_message(timeout=timeout, ignore_subscribe_messages=True)
        if msg and msg.get("type") == "message":
            return self._decode(msg.get("data"))
        return None

    def listen(self):
        for msg in self._pubsub.listen():
            if msg.get("type") == "message":
                decoded = self._decode(msg.get("data"))
                if decoded is not None:
                    yield decoded

    @staticmethod
    def _decode(data):
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
    def __init__(self, host: str, port: int, db: int):
        self._redis = redis.Redis(
            host=host, port=port, db=db,
            decode_responses=True,
            socket_keepalive=True,
            health_check_interval=30,
        )

    def publish(self, channel: str, payload: dict) -> None:
        try:
            self._redis.publish(channel, json.dumps(payload, ensure_ascii=False))
        except Exception as e:  # noqa: BLE001 - 통지 실패는 폴링 fallback이 흡수
            logger.warning("브로커 publish 실패(channel=%s): %s", channel, e)

    def subscribe(self, *channels: str) -> RedisSubscription:
        pubsub = self._redis.pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe(*channels)
        return RedisSubscription(pubsub)

    def ping(self) -> bool:
        try:
            return bool(self._redis.ping())
        except Exception as e:  # noqa: BLE001
            logger.warning("Redis ping 실패: %s", e)
            return False

    def close(self) -> None:
        try:
            self._redis.close()
        except Exception as e:  # noqa: BLE001
            logger.warning("Redis 연결 종료 실패: %s", e)
