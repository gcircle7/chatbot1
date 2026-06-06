"""메시지 브로커 추상화.

폴링 기반 통신을 대체하는 Pub/Sub 인터페이스.
구현체(RedisBroker 등)는 이 인터페이스만 따르면 되며,
BROKER_TYPE 설정으로 Redis ↔ RabbitMQ 등으로 교체할 수 있다.
"""

from abc import ABC, abstractmethod


# ===== 채널 이름 규약 =====
# 새 요청 도착 통지(워커 깨우기) — payload: {"request_id": int, "session_id": int}
CHANNEL_REQUESTS = "chat:requests"


def response_channel(request_id: int) -> str:
    """요청별 응답 통지 채널 이름. payload: {"request_id": int, "status": str}"""
    return f"chat:response:{request_id}"


class Subscription(ABC):
    """구독 핸들. get()으로 1건 대기하거나 listen()으로 스트림을 받는다."""

    @abstractmethod
    def get(self, timeout: float) -> dict | None:
        """timeout(초) 안에 메시지 1건을 받아 dict로 반환. 없으면 None."""

    @abstractmethod
    def listen(self):
        """메시지를 무한히 yield 하는 제너레이터(dict)."""

    @abstractmethod
    def close(self) -> None:
        """구독 해제 및 자원 정리."""


class MessageBroker(ABC):
    """발행/구독 브로커."""

    @abstractmethod
    def publish(self, channel: str, payload: dict) -> None:
        """채널에 payload(dict)를 발행."""

    @abstractmethod
    def subscribe(self, *channels: str) -> Subscription:
        """채널들을 구독하고 Subscription 핸들을 반환."""

    @abstractmethod
    def ping(self) -> bool:
        """브로커 연결 상태 확인."""

    @abstractmethod
    def close(self) -> None:
        """브로커 연결 종료."""
