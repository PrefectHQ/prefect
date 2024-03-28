import abc
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import (
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Dict,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Protocol,
    TypeVar,
    Union,
)
from typing_extensions import Self

from cachetools import TTLCache

from prefect.settings import PREFECT_MESSAGING_CACHE, PREFECT_MESSAGING_BROKER
from prefect.logging import get_logger

logger = get_logger(__name__)


class Message(Protocol):
    """
    A protocol representing a message sent to a message broker.
    """

    data: Union[bytes, str]
    attributes: Dict[str, Any]


M = TypeVar("M", bound=Message)


class Cache(abc.ABC):
    @abc.abstractmethod
    async def clear_recently_seen_messages(self) -> None:
        ...

    @abc.abstractmethod
    async def without_duplicates(self, attribute: str, messages: List[M]) -> List[M]:
        ...

    @abc.abstractmethod
    async def forget_duplicates(self, attribute: str, messages: List[M]) -> None:
        ...


class Publisher(abc.ABC):
    @abc.abstractmethod
    async def __aenter__(self) -> Self:
        ...

    @abc.abstractmethod
    async def __aexit__(self, exc_type, exc_value, traceback):
        ...

    @abc.abstractmethod
    async def publish_data(self, data: bytes, attributes: Dict[str, str]):
        ...


MessageHandler = Callable[[Message], Awaitable[None]]


@asynccontextmanager
async def ephemeral_subscription(topic: str) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Creates an ephemeral subscription to the given source, removing it when the context exits.

    Will create a subscription for PubSub. If the process crashes, the subscription will expire in 1 day (the
    lowest value that Pub/Sub supports).

    Will create a consumer group for Redis Streams.
    """
    if PREFECT_MESSAGING_BROKER.value() == "memory":
        from . import memory

        subscription = memory.ephemeral_subscription(topic)

    else:
        raise ValueError(
            f"Unknown message broker configured: {PREFECT_MESSAGING_BROKER.value()}"
        )

    async with subscription as info:
        yield info


class StopConsumer(Exception):
    """
    Exception to raise to stop a consumer.
    """

    def __init__(self, ack: bool = False):
        self.ack = ack


class Consumer(abc.ABC):
    """
    Abstract base class for consumers that receive messages from a message broker and
    call a handler function for each message received.
    """

    @abc.abstractmethod
    async def run(self, handler: MessageHandler) -> None:
        """Runs the consumer (indefinitely)"""
        ...


def create_cache() -> Cache:
    """
    Creates a new cache with the applications default settings.
    Returns:
        a new Cache instance
    """
    if PREFECT_MESSAGING_CACHE.value() == "memory":
        from . import memory

        return memory.MemoryCache()
    else:
        raise ValueError(f"Unknown cache configured: {PREFECT_MESSAGING_CACHE.value()}")


def create_publisher(
    topic: str, cache: Optional[Cache] = None, deduplicate_by: Optional[str] = None
) -> Publisher:
    """
    Creates a new publisher with the applications default settings.
    Args:
        topic: the topic to publish to
    Returns:
        a new Consumer instance
    """
    cache = cache or create_cache()

    if PREFECT_MESSAGING_BROKER.value() == "memory":
        from . import memory

        return memory.MemoryPublisher(topic, cache, deduplicate_by=deduplicate_by)
    else:
        raise ValueError(
            f"Unknown message broker configured: {PREFECT_MESSAGING_BROKER.value()}"
        )


def create_consumer(topic: str, **kwargs) -> Consumer:
    """
    Creates a new consumer with the applications default settings.
    Args:
        topic: the topic to consume from
    Returns:
        a new Consumer instance
    """
    if PREFECT_MESSAGING_BROKER.value() == "memory":
        from . import memory

        return memory.MemoryConsumer(topic, **kwargs)
    else:
        raise ValueError(
            f"Unknown message broker configured: {PREFECT_MESSAGING_BROKER.value()}"
        )
