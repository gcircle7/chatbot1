"""브로커 팩토리.

BROKER_TYPE 환경변수로 구현체를 선택한다.
- redis (기본)
- rabbitmq (추후 지원 — RabbitMQBroker 추가 후 분기만 열면 됨)

import 예:
    from broker import get_broker, CHANNEL_REQUESTS, response_channel
"""

import os
import threading

from .base import MessageBroker, CHANNEL_REQUESTS, response_channel

_broker: MessageBroker | None = None
_lock = threading.Lock()


def get_broker() -> MessageBroker:
    """프로세스 단일 브로커 인스턴스를 반환(lazy, thread-safe)."""
    global _broker
    if _broker is not None:
        return _broker
    with _lock:
        if _broker is not None:
            return _broker
        broker_type = os.environ.get("BROKER_TYPE", "redis").lower()
        if broker_type == "redis":
            from .redis_broker import RedisBroker
            _broker = RedisBroker(
                host=os.environ.get("REDIS_HOST", "localhost"),
                port=int(os.environ.get("REDIS_PORT", "6379")),
                db=int(os.environ.get("REDIS_DB", "0")),
            )
        elif broker_type == "rabbitmq":
            # 추후: from .rabbitmq_broker import RabbitMQBroker; _broker = RabbitMQBroker(...)
            raise NotImplementedError(
                "RabbitMQ 브로커는 추후 지원 예정입니다. BROKER_TYPE=redis 를 사용하세요."
            )
        else:
            raise ValueError(f"알 수 없는 BROKER_TYPE: {broker_type}")
    return _broker


__all__ = ["get_broker", "MessageBroker", "CHANNEL_REQUESTS", "response_channel"]
