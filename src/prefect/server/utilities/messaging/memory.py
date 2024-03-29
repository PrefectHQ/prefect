import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from typing import (
    Any,
    AsyncGenerator,
    Dict,
    List,
    MutableMapping,
    Optional,
    TypeVar,
    Union,
)

from cachetools import TTLCache
from typing_extensions import Self

from prefect.logging import get_logger
from prefect.server.utilities.messaging import Cache as _Cache
from prefect.server.utilities.messaging import Consumer as _Consumer
from prefect.server.utilities.messaging import Message, MessageHandler, StopConsumer
from prefect.server.utilities.messaging import Publisher as _Publisher

logger = get_logger(__name__)


@dataclass
class MemoryMessage:
    data: Union[bytes, str]
    attributes: Dict[str, Any]


class Subscription:
    topic: "Topic"
    _queue: asyncio.Queue
    _retry: asyncio.Queue

    def __init__(self, topic: "Topic") -> None:
        self.topic = topic
        self._queue = asyncio.Queue()
        self._retry = asyncio.Queue()

    async def deliver(self, message: MemoryMessage) -> None:
        await self._queue.put(message)

    async def retry(self, message: MemoryMessage) -> None:
        await self._retry.put(message)

    async def get(self) -> MemoryMessage:
        if self._retry.qsize() > 0:
            return await self._retry.get()
        return await self._queue.get()


class Topic:
    _topics: Dict[str, "Topic"] = {}

    name: str
    _subscriptions: List[Subscription]

    def __init__(self, name: str) -> None:
        self.name = name
        self._subscriptions = []

    @classmethod
    def by_name(cls, name: str) -> Self:
        try:
            return cls._topics[name]
        except KeyError:
            topic = cls(name)
            cls._topics[name] = topic
            return topic

    @classmethod
    def clear_all(cls):
        for topic in cls._topics.values():
            topic.clear()
        cls._topics = {}

    def subscribe(self) -> Subscription:
        subscription = Subscription(self)
        self._subscriptions.append(subscription)
        return subscription

    def unsubscribe(self, subscription: Subscription) -> None:
        self._subscriptions.remove(subscription)

    def clear(self):
        for subscription in self._subscriptions:
            self.unsubscribe(subscription)
        self._subscriptions = []

    async def publish(self, message: MemoryMessage) -> None:
        for subscription in self._subscriptions:
            await subscription.deliver(message)


@asynccontextmanager
async def break_topic():
    from unittest import mock

    publishing_mock = mock.AsyncMock(side_effect=ValueError("oops"))

    with mock.patch(
        "prefect.server.utilities.messaging.memory.Topic.publish",
        publishing_mock,
    ):
        yield


M = TypeVar("M", bound=Message)


class Cache(_Cache):
    _recently_seen_messages: MutableMapping[str, bool] = TTLCache(
        maxsize=1000,
        ttl=timedelta(minutes=5).total_seconds(),
    )

    async def clear_recently_seen_messages(self) -> None:
        self._recently_seen_messages.clear()

    async def without_duplicates(self, attribute: str, messages: List[M]) -> List[M]:
        messages_with_attribute = []
        messages_without_attribute = []

        for m in messages:
            if m.attributes is None or attribute not in m.attributes:
                logger.warning(
                    "Message is missing deduplication attribute %r",
                    attribute,
                    extra={"event_message": m},
                )
                messages_without_attribute.append(m)
                continue

            if self._recently_seen_messages.get(m.attributes[attribute]):
                continue

            self._recently_seen_messages[m.attributes[attribute]] = True
            messages_with_attribute.append(m)

        return messages_with_attribute + messages_without_attribute

    async def forget_duplicates(self, attribute: str, messages: List[M]) -> None:
        for m in messages:
            if m.attributes is None or attribute not in m.attributes:
                logger.warning(
                    "Message is missing deduplication attribute %r",
                    attribute,
                    extra={"event_message": m},
                )
                continue
            self._recently_seen_messages.pop(m.attributes[attribute], None)


class Publisher(_Publisher):
    def __init__(self, topic: str, cache: Cache, deduplicate_by: Optional[str] = None):
        self.topic = Topic.by_name(topic)
        self.deduplicate_by = deduplicate_by
        self._cache = cache

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return None

    async def publish_data(self, data: bytes, attributes: Dict[str, str]):
        to_publish = [MemoryMessage(data, attributes)]
        if self.deduplicate_by:
            to_publish = await self._cache.without_duplicates(
                self.deduplicate_by, to_publish
            )

        try:
            for message in to_publish:
                await self.topic.publish(message)
        except Exception:
            if self.deduplicate_by:
                await self._cache.forget_duplicates(self.deduplicate_by, to_publish)
            raise


class Consumer(_Consumer):
    def __init__(self, topic: str, subscription: Optional[Subscription] = None):
        self.topic = Topic.by_name(topic)
        if not subscription:
            subscription = self.topic.subscribe()
        assert subscription.topic is self.topic
        self.subscription = subscription

    async def run(self, handler: MessageHandler) -> None:
        while True:
            message = await self.subscription.get()
            try:
                await handler(message)
            except StopConsumer as e:
                if not e.ack:
                    await self.subscription.retry(message)
                return
            except Exception:
                await self.subscription.retry(message)


@asynccontextmanager
async def ephemeral_subscription(topic: str) -> AsyncGenerator[Dict[str, Any], None]:
    subscription = Topic.by_name(topic).subscribe()
    try:
        yield {"topic": topic, "subscription": subscription}
    finally:
        Topic.by_name(topic).unsubscribe(subscription)
