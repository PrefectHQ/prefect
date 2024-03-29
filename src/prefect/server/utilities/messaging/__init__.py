import abc
from contextlib import asynccontextmanager
import importlib
from typing import (
    Any,
    AsyncContextManager,
    AsyncGenerator,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    Type,
    TypeVar,
    Union,
    runtime_checkable,
)
from typing_extensions import Self

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


@runtime_checkable
class CacheModule(Protocol):
    Cache: Type[Cache]


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
    Publisher: Type[Publisher]
    Consumer: Type[Consumer]
    ephemeral_subscription: Callable[[str], AsyncGenerator[Dict[str, Any], None]]

    # Used for testing: a context manager that breaks the topic in a way that raises
    # a ValueError("oops") when attempting to publish a message.
    break_topic: Callable[[], AsyncContextManager[None]]


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
async def ephemeral_subscription(topic: str) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Creates an ephemeral subscription to the given source, removing it when the context
    exits.
    """
    module = importlib.import_module(PREFECT_MESSAGING_BROKER.value())
    assert isinstance(module, BrokerModule)
    async with module.ephemeral_subscription(topic) as consumer_create_kwargs:
        yield consumer_create_kwargs


def create_consumer(topic: str, **kwargs) -> Consumer:
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
