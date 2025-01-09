import abc
from contextlib import asynccontextmanager, AbstractAsyncContextManager
from dataclasses import dataclass
import importlib
from typing import Any, Callable, Optional, Protocol, TypeVar, Union, runtime_checkable
from collections.abc import AsyncGenerator, Awaitable, Iterable, Mapping

from prefect.settings import PREFECT_MESSAGING_CACHE, PREFECT_MESSAGING_BROKER
from prefect.logging import get_logger

logger = get_logger(__name__)


M = TypeVar("M", bound="Message", covariant=True)


class Message(Protocol):
    """
    A protocol representing a message sent to a message broker.
    """

    @property
    def data(self) -> Union[str, bytes]:
        ...

    @property
    def attributes(self) -> Mapping[str, Any]:
        ...


class Cache(abc.ABC):
    @abc.abstractmethod
    async def clear_recently_seen_messages(self) -> None:
        ...

    @abc.abstractmethod
    async def without_duplicates(
        self, attribute: str, messages: Iterable[M]
    ) -> list[M]:
        ...

    @abc.abstractmethod
    async def forget_duplicates(
        self, attribute: str, messages: Iterable[Message]
    ) -> None:
        ...


class Publisher(AbstractAsyncContextManager["Publisher"], abc.ABC):
    def __init__(
        self,
        topic: str,
        cache: Optional[Cache] = None,
        deduplicate_by: Optional[str] = None,
    ) -> None:
        ...

    @abc.abstractmethod
    async def publish_data(self, data: bytes, attributes: Mapping[str, str]) -> None:
        ...


@dataclass
class CapturedMessage:
    data: bytes
    attributes: Mapping[str, str]


class CapturingPublisher(Publisher):
    messages: list[CapturedMessage] = []
    deduplicate_by: Optional[str]

    def __init__(
        self,
        topic: str,
        cache: Optional[Cache] = None,
        deduplicate_by: Optional[str] = None,
    ) -> None:
        self.topic = topic
        self.cache = cache or create_cache()
        self.deduplicate_by = deduplicate_by

    async def __aexit__(self, *args: Any) -> None:
        pass

    async def publish_data(self, data: bytes, attributes: Mapping[str, str]):
        to_publish = [CapturedMessage(data, attributes)]

        if self.deduplicate_by:
            to_publish = await self.cache.without_duplicates(
                self.deduplicate_by, to_publish
            )

        self.messages.extend(to_publish)


MessageHandler = Callable[[Message], Awaitable[None]]


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

    def __init__(self, topic: str, **kwargs: Any) -> None:
        self.topic = topic

    @abc.abstractmethod
    async def run(self, handler: MessageHandler) -> None:
        """Runs the consumer (indefinitely)"""
        ...


@runtime_checkable
class CacheModule(Protocol):
    Cache: type[Cache]


def create_cache() -> Cache:
    """
    Creates a new cache with the applications default settings.

    Returns:
        a new Cache instance
    """
    module = importlib.import_module(PREFECT_MESSAGING_CACHE.value())
    assert isinstance(module, CacheModule)

    return module.Cache()


@runtime_checkable
class BrokerModule(Protocol):
    Publisher: type[Publisher]
    Consumer: type[Consumer]
    ephemeral_subscription: Callable[
        [str], AbstractAsyncContextManager[Mapping[str, Any]]
    ]

    # Used for testing: a context manager that breaks the topic in a way that raises
    # a ValueError("oops") when attempting to publish a message.
    break_topic: Callable[[], AbstractAsyncContextManager[None]]


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

    module = importlib.import_module(PREFECT_MESSAGING_BROKER.value())
    assert isinstance(module, BrokerModule)
    return module.Publisher(topic, cache, deduplicate_by=deduplicate_by)


@asynccontextmanager
async def ephemeral_subscription(topic: str) -> AsyncGenerator[Mapping[str, Any], Any]:
    """
    Creates an ephemeral subscription to the given source, removing it when the context
    exits.
    """
    module = importlib.import_module(PREFECT_MESSAGING_BROKER.value())
    assert isinstance(module, BrokerModule)
    async with module.ephemeral_subscription(topic) as consumer_create_kwargs:
        yield consumer_create_kwargs


def create_consumer(topic: str, **kwargs: Any) -> Consumer:
    """
    Creates a new consumer with the applications default settings.
    Args:
        topic: the topic to consume from
    Returns:
        a new Consumer instance
    """
    module = importlib.import_module(PREFECT_MESSAGING_BROKER.value())
    assert isinstance(module, BrokerModule)
    return module.Consumer(topic, **kwargs)
