from __future__ import annotations

import asyncio
import copy
import threading
from collections import defaultdict
from collections.abc import AsyncGenerator, Iterable, Mapping, MutableMapping
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from datetime import timedelta
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Any, Optional, TypeVar, Union
from uuid import uuid4

import anyio
from cachetools import TTLCache
from exceptiongroup import BaseExceptionGroup  # novermin
from pydantic_core import to_json
from typing_extensions import Self

from prefect.logging import get_logger
from prefect.server.utilities.messaging import Cache as _Cache
from prefect.server.utilities.messaging import Consumer as _Consumer
from prefect.server.utilities.messaging import Message, MessageHandler, StopConsumer
from prefect.server.utilities.messaging import Publisher as _Publisher
from prefect.settings.context import get_current_settings

if TYPE_CHECKING:
    import logging

logger: "logging.Logger" = get_logger(__name__)

# Simple global counters by topic with thread-safe access
_metrics_lock: threading.Lock | None = None
METRICS: dict[str, dict[str, int]] = defaultdict(
    lambda: {
        "published": 0,
        "retried": 0,
        "consumed": 0,
    }
)


async def log_metrics_periodically(interval: float = 2.0) -> None:
    if _metrics_lock is None:
        return
    while True:
        await asyncio.sleep(interval)
        with _metrics_lock:
            for topic, data in METRICS.items():
                if data["published"] == 0:
                    continue
                depth = data["published"] - data["consumed"]
                logger.debug(
                    "Topic=%r | published=%d consumed=%d retried=%d depth=%d",
                    topic,
                    data["published"],
                    data["consumed"],
                    data["retried"],
                    depth,
                )


async def update_metric(topic: str, key: str, amount: int = 1) -> None:
    global _metrics_lock
    if _metrics_lock is None:
        _metrics_lock = threading.Lock()
    with _metrics_lock:
        METRICS[topic][key] += amount


@dataclass
class MemoryMessage:
    data: Union[bytes, str]
    attributes: Mapping[str, Any]
    retry_count: int = 0


class Subscription:
    """
    A subscription to a topic.

    Messages are delivered to the subscription's queue and retried up to a
    maximum number of times. If a message cannot be delivered after the maximum
    number of retries it is moved to the dead letter queue.

    The dead letter queue is a directory of JSON files containing the serialized
    message.

    Messages remain in the dead letter queue until they are removed manually.

    Attributes:
        topic: The topic that the subscription receives messages from.
        max_retries: The maximum number of times a message will be retried for
            this subscription.
        dead_letter_queue_path: The path to the dead letter queue folder.
    """

    def __init__(
        self,
        topic: "Topic",
        max_retries: int = 3,
        dead_letter_queue_path: Path | str | None = None,
    ) -> None:
        self.topic = topic
        self.max_retries = max_retries
        self.dead_letter_queue_path: Path = (
            Path(dead_letter_queue_path)
            if dead_letter_queue_path
            else get_current_settings().home / "dlq"
        )
        self._queue: asyncio.Queue[MemoryMessage] = asyncio.Queue()
        self._retry: asyncio.Queue[MemoryMessage] = asyncio.Queue()

    async def deliver(self, message: MemoryMessage) -> None:
        """
        Deliver a message to the subscription's queue.

        Args:
            message: The message to deliver.
        """
        await self._queue.put(message)
        await update_metric(self.topic.name, "published")
        logger.debug(
            "Delivered message to topic=%r queue_size=%d retry_queue_size=%d",
            self.topic.name,
            self._queue.qsize(),
            self._retry.qsize(),
        )

    async def retry(self, message: MemoryMessage) -> None:
        """
        Place a message back on the retry queue.

        If the message has retried more than the maximum number of times it is
        moved to the dead letter queue.

        Args:
            message: The message to retry.
        """
        message.retry_count += 1
        if message.retry_count > self.max_retries:
            logger.warning(
                "Message failed after %d retries and will be moved to the dead letter queue",
                message.retry_count,
                extra={"event_message": message},
            )
            await self.send_to_dead_letter_queue(message)
        else:
            await self._retry.put(message)
            await update_metric(self.topic.name, "retried")
            logger.debug(
                "Retried message on topic=%r retry_count=%d queue_size=%d retry_queue_size=%d",
                self.topic.name,
                message.retry_count,
                self._queue.qsize(),
                self._retry.qsize(),
            )

    async def get(self) -> MemoryMessage:
        """
        Get a message from the subscription's queue.
        """
        if not self._retry.empty():
            return await self._retry.get()
        return await self._queue.get()

    async def send_to_dead_letter_queue(self, message: MemoryMessage) -> None:
        """
        Send a message to the dead letter queue.

        The dead letter queue is a directory of JSON files containing the
        serialized messages.

        Args:
            message: The message to send to the dead letter queue.
        """
        self.dead_letter_queue_path.mkdir(parents=True, exist_ok=True)
        try:
            await anyio.Path(self.dead_letter_queue_path / uuid4().hex).write_bytes(
                to_json(asdict(message))
            )
        except Exception as e:
            logger.warning("Failed to write message to dead letter queue", exc_info=e)


class Topic:
    _topics: dict[str, "Topic"] = {}

    name: str
    _subscriptions: list[Subscription]

    def __init__(self, name: str) -> None:
        self.name = name
        self._subscriptions = []

    @classmethod
    def by_name(cls, name: str) -> "Topic":
        try:
            return cls._topics[name]
        except KeyError:
            topic = cls(name)
            cls._topics[name] = topic
            return topic

    @classmethod
    def clear_all(cls) -> None:
        for topic in cls._topics.values():
            topic.clear()
        cls._topics = {}

    def subscribe(self, **subscription_kwargs: Any) -> Subscription:
        subscription = Subscription(self, **subscription_kwargs)
        self._subscriptions.append(subscription)
        return subscription

    def unsubscribe(self, subscription: Subscription) -> None:
        self._subscriptions.remove(subscription)

    def clear(self) -> None:
        for subscription in self._subscriptions:
            self.unsubscribe(subscription)
        self._subscriptions = []

    async def publish(self, message: MemoryMessage) -> None:
        for subscription in self._subscriptions:
            # Ensure that each subscription gets its own copy of the message
            await subscription.deliver(copy.deepcopy(message))


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

    async def without_duplicates(
        self, attribute: str, messages: Iterable[M]
    ) -> list[M]:
        messages_with_attribute: list[M] = []
        messages_without_attribute: list[M] = []

        for m in messages:
            if not m.attributes or attribute not in m.attributes:
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

    async def forget_duplicates(self, attribute: str, messages: Iterable[M]) -> None:
        for m in messages:
            if not m.attributes or attribute not in m.attributes:
                logger.warning(
                    "Message is missing deduplication attribute %r",
                    attribute,
                    extra={"event_message": m},
                )
                continue
            self._recently_seen_messages.pop(m.attributes[attribute], None)


class Publisher(_Publisher):
    def __init__(self, topic: str, cache: Cache, deduplicate_by: Optional[str] = None):
        self.topic: Topic = Topic.by_name(topic)
        self.deduplicate_by = deduplicate_by
        self._cache = cache

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        return None

    async def publish_data(self, data: bytes, attributes: Mapping[str, str]) -> None:
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
    def __init__(
        self,
        topic: str,
        subscription: Optional[Subscription] = None,
        concurrency: int = 2,
    ):
        self.topic: Topic = Topic.by_name(topic)
        if not subscription:
            subscription = self.topic.subscribe()
        assert subscription.topic is self.topic
        self.subscription = subscription
        self.concurrency = concurrency

    async def run(self, handler: MessageHandler) -> None:
        try:
            async with anyio.create_task_group() as tg:
                for _ in range(self.concurrency):
                    tg.start_soon(self._consume_loop, handler)
        except BaseExceptionGroup as group:  # novermin
            if all(isinstance(exc, StopConsumer) for exc in group.exceptions):
                logger.debug("StopConsumer received")
                return  # Exit cleanly when all tasks stop
            # Re-raise if any non-StopConsumer exceptions
            raise group

    async def _consume_loop(self, handler: MessageHandler) -> None:
        while True:
            message = await self.subscription.get()
            try:
                await handler(message)
                await update_metric(self.topic.name, "consumed")
            except StopConsumer as e:
                if not e.ack:
                    await self.subscription.retry(message)
                raise  # Propagate to task group
            except Exception:
                logger.exception("Failed in consume_loop")
                await self.subscription.retry(message)


@asynccontextmanager
async def ephemeral_subscription(topic: str) -> AsyncGenerator[Mapping[str, Any], None]:
    subscription = Topic.by_name(topic).subscribe()
    try:
        yield {"topic": topic, "subscription": subscription}
    finally:
        Topic.by_name(topic).unsubscribe(subscription)
