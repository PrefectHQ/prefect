from __future__ import annotations

import asyncio
import json
import socket
import time
import uuid
from contextlib import asynccontextmanager
from datetime import timedelta
from functools import partial
from types import TracebackType
from typing import (
    Annotated,
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Optional,
    Type,
    TypeVar,
    Union,
    cast,
)

import orjson
from pydantic import BeforeValidator, Field
from redis.asyncio import Redis
from redis.exceptions import ResponseError
from typing_extensions import Self

from prefect.logging import get_logger
from prefect.server.utilities.messaging import Cache as _Cache
from prefect.server.utilities.messaging import Consumer as _Consumer
from prefect.server.utilities.messaging import (
    Message,
    MessageHandler,
    StopConsumer,
)
from prefect.server.utilities.messaging import Publisher as _Publisher
from prefect.settings.base import PrefectBaseSettings, build_settings_config
from prefect_redis.client import get_async_redis_client

logger = get_logger(__name__)

M = TypeVar("M", bound=Message)


def _interpret_string_as_timedelta_seconds(value: timedelta | str) -> timedelta:
    """Interpret a string as a timedelta in seconds."""
    if isinstance(value, str):
        return timedelta(seconds=int(value))
    return value


TimeDelta = Annotated[
    Union[str, timedelta],
    BeforeValidator(_interpret_string_as_timedelta_seconds),
]


class RedisMessagingPublisherSettings(PrefectBaseSettings):
    """Settings for the Redis messaging publisher.

    No settings are required to be set by the user but any of the settings can be
    overridden by the user using environment variables.

    Example:
        ```
        PREFECT_REDIS_MESSAGING_PUBLISHER_BATCH_SIZE=10
        PREFECT_REDIS_MESSAGING_PUBLISHER_PUBLISH_EVERY=10
        PREFECT_REDIS_MESSAGING_PUBLISHER_DEDUPLICATE_BY=message_id
        ```
    """

    model_config = build_settings_config(
        (
            "redis",
            "messaging",
            "publisher",
        ),
    )
    batch_size: int = Field(default=5)
    publish_every: TimeDelta = Field(default=timedelta(seconds=10))
    deduplicate_by: Optional[str] = Field(default=None)


class RedisMessagingConsumerSettings(PrefectBaseSettings):
    """Settings for the Redis messaging consumer.

    No settings are required to be set by the user but any of the settings can be
    overridden by the user using environment variables.

    Example:
        ```
        PREFECT_REDIS_MESSAGING_CONSUMER_BLOCK=10
        PREFECT_REDIS_MESSAGING_CONSUMER_MIN_IDLE_TIME=10
        PREFECT_REDIS_MESSAGING_CONSUMER_MAX_RETRIES=3
        PREFECT_REDIS_MESSAGING_CONSUMER_TRIM_EVERY=60
        PREFECT_REDIS_MESSAGING_CONSUMER_TRIM_IDLE_THRESHOLD=300
        ```
    """

    model_config = build_settings_config(
        (
            "redis",
            "messaging",
            "consumer",
        ),
    )
    block: TimeDelta = Field(default=timedelta(seconds=1))
    min_idle_time: TimeDelta = Field(default=timedelta(seconds=5))
    max_retries: int = Field(default=3)
    trim_every: TimeDelta = Field(default=timedelta(seconds=60))
    trim_idle_threshold: TimeDelta = Field(default=timedelta(minutes=5))
    should_process_pending_messages: bool = Field(default=True)
    starting_message_id: str = Field(default="0")
    automatically_acknowledge: bool = Field(default=True)


MESSAGE_DEDUPLICATION_LOOKBACK = timedelta(minutes=5)


class Cache(_Cache):
    def __init__(self, topic: str = "messaging-cache"):
        self.topic = topic
        self._client: Redis = get_async_redis_client()

    async def clear_recently_seen_messages(self) -> None:
        return

    async def without_duplicates(self, attribute: str, messages: list[M]) -> list[M]:
        messages_with_attribute: list[M] = []
        messages_without_attribute: list[M] = []
        async with self._client.pipeline() as p:
            for m in messages:
                if m.attributes is None or attribute not in m.attributes:
                    logger.warning(
                        "Message is missing deduplication attribute %r",
                        attribute,
                        extra={"event_message": m},
                    )
                    messages_without_attribute.append(m)
                    continue
                p.set(
                    f"message:{self.topic}:{m.attributes[attribute]}",
                    "1",
                    nx=True,
                    ex=MESSAGE_DEDUPLICATION_LOOKBACK,
                )
                messages_with_attribute.append(m)
            results: list[Optional[bool]] = await p.execute()

        return [
            m for i, m in enumerate(messages_with_attribute) if results[i]
        ] + messages_without_attribute

    async def forget_duplicates(self, attribute: str, messages: list[M]) -> None:
        async with self._client.pipeline() as p:
            for m in messages:
                if m.attributes is None or attribute not in m.attributes:
                    logger.warning(
                        "Message is missing deduplication attribute %r",
                        attribute,
                        extra={"event_message": m},
                    )
                    continue
                p.delete(f"message:{self.topic}:{m.attributes[attribute]}")
            await p.execute()


class RedisStreamsMessage:
    """
    A message sent to a Redis stream.
    """

    def __init__(
        self,
        data: Union[bytes, str],
        attributes: dict[str, Any],
        acker: Union[Callable[[], Awaitable[None]], None] = None,
    ) -> None:
        self.data = data.decode() if isinstance(data, bytes) else data
        self.attributes = attributes
        self.acker = acker

    def __eq__(self, other: Any) -> bool:
        return self.data == other.data and self.attributes == other.attributes

    async def acknowledge(self) -> None:
        assert self.acker is not None
        await self.acker()


class Subscription:
    """
    A subscription-like object for Redis. We mimic the memory subscription interface
    so that we can set max_retries and handle dead letter queue storage in Redis.
    """

    def __init__(self, max_retries: int = 3, dlq_key: str = "dlq"):
        self.max_retries = max_retries
        self.dlq_key = dlq_key


class Publisher(_Publisher):
    def __init__(
        self,
        topic: str,
        cache: _Cache,
        deduplicate_by: Optional[str] = None,
        batch_size: Optional[int] = None,
        publish_every: Optional[timedelta] = None,
    ):
        settings = RedisMessagingPublisherSettings()

        self.stream = topic  # Use topic as stream name
        self.cache = cache
        self.deduplicate_by = (
            deduplicate_by if deduplicate_by is not None else settings.deduplicate_by
        )
        self.batch_size = batch_size if batch_size is not None else settings.batch_size
        self.publish_every = (
            publish_every if publish_every is not None else settings.publish_every
        )
        self._periodic_task: Optional[asyncio.Task[None]] = None

    async def __aenter__(self) -> Self:
        self._client = get_async_redis_client()
        self._batch: list[RedisStreamsMessage] = []

        if self.publish_every is not None:
            interval = self.publish_every.total_seconds()

            async def _publish_periodically() -> None:
                while True:
                    await asyncio.sleep(interval)
                    await asyncio.shield(self._publish_current_batch())

            self._periodic_task = asyncio.create_task(_publish_periodically())

        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        if not hasattr(self, "_batch"):
            raise RuntimeError("Use this publisher as an async context manager")

        try:
            if self._periodic_task:
                self._periodic_task.cancel()
            await self._publish_current_batch()
        except Exception:
            if self.deduplicate_by:
                await self.cache.forget_duplicates(self.deduplicate_by, self._batch)
            raise

    async def publish_data(self, data: bytes, attributes: dict[str, Any]):
        if not hasattr(self, "_batch"):
            raise RuntimeError("Use this publisher as an async context manager")

        self._batch.append(RedisStreamsMessage(data=data, attributes=attributes))
        if len(self._batch) >= self.batch_size:
            await asyncio.shield(self._publish_current_batch())

    async def _publish_current_batch(self) -> None:
        if not self._batch:
            return

        if self.deduplicate_by:
            to_publish = await self.cache.without_duplicates(
                self.deduplicate_by, self._batch
            )
        else:
            to_publish = list(self._batch)

        self._batch.clear()

        try:
            for message in to_publish:
                await self._client.xadd(
                    self.stream,
                    {
                        "data": message.data,
                        "attributes": orjson.dumps(message.attributes),
                    },
                )
        except Exception:
            if self.deduplicate_by:
                await self.cache.forget_duplicates(self.deduplicate_by, to_publish)
            raise


class Consumer(_Consumer):
    """
    Consumer implementation for Redis Streams with DLQ support.
    """

    def __init__(
        self,
        topic: str,
        name: Optional[str] = None,
        group: Optional[str] = None,
        block: Optional[timedelta] = None,
        min_idle_time: Optional[timedelta] = None,
        should_process_pending_messages: Optional[bool] = None,
        starting_message_id: Optional[str] = None,
        automatically_acknowledge: Optional[bool] = None,
        max_retries: Optional[int] = None,
        trim_every: Optional[timedelta] = None,
    ):
        settings = RedisMessagingConsumerSettings()

        self.name = name or topic
        self.stream = topic  # Use topic as stream name
        self.group = group or topic  # Use topic as default group name
        self.block = block if block is not None else settings.block
        self.min_idle_time = (
            min_idle_time if min_idle_time is not None else settings.min_idle_time
        )
        self.should_process_pending_messages = (
            should_process_pending_messages
            if should_process_pending_messages is not None
            else settings.should_process_pending_messages
        )
        self.starting_message_id = (
            starting_message_id
            if starting_message_id is not None
            else settings.starting_message_id
        )
        self.automatically_acknowledge = (
            automatically_acknowledge
            if automatically_acknowledge is not None
            else settings.automatically_acknowledge
        )
        self.trim_every = trim_every if trim_every is not None else settings.trim_every

        self.subscription = Subscription(
            max_retries=max_retries if max_retries is not None else settings.max_retries
        )
        self._retry_counts: dict[str, int] = {}

        self._last_trimmed: Optional[float] = None

    async def _ensure_stream_and_group(self, redis_client: Redis) -> None:
        """Ensure the stream and consumer group exist."""
        try:
            # Create consumer group and stream if they don't exist
            await redis_client.xgroup_create(
                self.stream, self.group, id=self.starting_message_id, mkstream=True
            )
        except ResponseError as e:
            if "BUSYGROUP Consumer Group name already exists" not in str(e):
                raise
            logger.debug("Consumer group already exists: %s", e)

    async def process_pending_messages(
        self,
        handler: MessageHandler,
        redis_client: Redis,
        message_batch_size: int,
        start_id: str = "0-0",
    ):
        acker = partial(redis_client.xack, self.stream, self.group)

        while True:
            result = await redis_client.xautoclaim(
                name=self.stream,
                groupname=self.group,
                consumername=self.name,
                min_idle_time=int(self.min_idle_time.total_seconds() * 1000),
                start_id=start_id,
                count=message_batch_size,
            )
            next_start_id, claimed_messages = result[0], result[1]

            if not claimed_messages:
                break

            for message_id, message in claimed_messages:
                await self._handle_message(message_id, message, handler, acker)

            start_id = next_start_id

    async def run(self, handler: MessageHandler) -> None:
        redis_client: Redis = get_async_redis_client()

        # Ensure stream and group exist before processing messages
        await self._ensure_stream_and_group(redis_client)

        # Process messages
        while True:
            if self.should_process_pending_messages:
                try:
                    await self.process_pending_messages(
                        handler,
                        redis_client,
                        1,  # Use batch size of 1 for now
                    )
                except StopConsumer:
                    return

            # Read new messages
            try:
                stream_entries = await redis_client.xreadgroup(
                    groupname=self.group,
                    consumername=self.name,
                    streams={self.stream: ">"},
                    count=1,  # Use batch size of 1 for now
                    block=int(self.block.total_seconds() * 1000),
                )
            except ResponseError as e:
                logger.error(f"Failed to read from stream: {e}")
                raise

            if not stream_entries:
                await self._trim_stream_if_necessary()
                continue

            acker = partial(redis_client.xack, self.stream, self.group)

            for _, messages in stream_entries:
                for message_id, message in messages:
                    try:
                        await self._handle_message(message_id, message, handler, acker)
                    except StopConsumer:
                        return

    async def _handle_message(
        self,
        message_id: bytes,
        message: dict[str, Any],
        handler: MessageHandler,
        acker: Callable[..., Awaitable[int]],
    ):
        redis_stream_message = RedisStreamsMessage(
            data=message["data"],
            attributes=orjson.loads(message["attributes"]),
            acker=cast(Callable[[], Awaitable[None]], partial(acker, message_id)),
        )
        msg_id_str = (
            message_id.decode() if isinstance(message_id, bytes) else message_id
        )

        try:
            await handler(redis_stream_message)
            if self.automatically_acknowledge:
                await redis_stream_message.acknowledge()
        except StopConsumer as e:
            if not e.ack:
                await self._on_message_failure(redis_stream_message, msg_id_str)
            else:
                if self.automatically_acknowledge:
                    await redis_stream_message.acknowledge()
            raise
        except Exception:
            await self._on_message_failure(redis_stream_message, msg_id_str)
        finally:
            await self._trim_stream_if_necessary()

    async def _on_message_failure(self, msg: RedisStreamsMessage, msg_id_str: str):
        current_count = self._retry_counts.get(msg_id_str, 0) + 1
        self._retry_counts[msg_id_str] = current_count

        if current_count > self.subscription.max_retries:
            # Move to DLQ
            await self._send_to_dlq(msg, current_count)
            # Acknowledge so it's no longer pending
            await msg.acknowledge()
        else:
            # Leave it pending. xautoclaim will re-claim it next time.
            pass

    async def _send_to_dlq(self, msg: RedisStreamsMessage, retry_count: int):
        """Store failed messages in Redis instead of filesystem"""
        redis_client: Redis = get_async_redis_client()

        # Convert data to a string if bytes
        data_str = msg.data.decode() if isinstance(msg.data, bytes) else msg.data
        dlq_message = {
            "data": data_str,
            "attributes": msg.attributes,
            "retry_count": retry_count,
            "timestamp": str(asyncio.get_event_loop().time()),
            "message_id": str(uuid.uuid4().hex),
        }

        # Store in Redis as a hash
        message_id = f"dlq:{uuid.uuid4().hex}"
        await redis_client.hset(message_id, mapping={"data": json.dumps(dlq_message)})
        # Add to a Redis set for easy retrieval
        await redis_client.sadd(self.subscription.dlq_key, message_id)

    async def _trim_stream_if_necessary(self) -> None:
        now = time.monotonic()
        if self._last_trimmed is None:
            self._last_trimmed = now

        if now - self._last_trimmed > self.trim_every.total_seconds():
            await _trim_stream_to_lowest_delivered_id(self.stream)
            await _cleanup_empty_consumer_groups(self.stream)
            self._last_trimmed = now


@asynccontextmanager
async def ephemeral_subscription(
    topic: str, source: Optional[str] = None, group: Optional[str] = None
) -> AsyncGenerator[dict[str, Any], None]:
    source = source or topic
    group_name = group or f"ephemeral-{socket.gethostname()}-{uuid.uuid4().hex}"
    redis_client: Redis = get_async_redis_client()

    await redis_client.xgroup_create(source, group_name, id="0", mkstream=True)

    try:
        # Return only the arguments that the Consumer expects.
        yield {"topic": topic, "name": topic, "group": group_name}
    finally:
        await redis_client.xgroup_destroy(source, group_name)


@asynccontextmanager
async def break_topic():
    from unittest import mock

    publishing_mock = mock.AsyncMock(side_effect=ValueError("oops"))

    with mock.patch(
        "redis.asyncio.client.Redis.xadd",
        publishing_mock,
    ):
        yield


async def _trim_stream_to_lowest_delivered_id(stream_name: str) -> None:
    """
    Trims a Redis stream by removing all messages that have been delivered to and
    acknowledged by all consumer groups.

    This function finds the lowest last-delivered-id across all consumer groups and
    trims the stream up to that point, as we know all consumers have processed those
    messages.

    Consumer groups with all consumers idle beyond the configured threshold are
    excluded from the trimming calculation to prevent inactive groups from blocking
    stream trimming.

    Args:
        stream_name: The name of the Redis stream to trim
    """
    redis_client: Redis = get_async_redis_client()
    settings = RedisMessagingConsumerSettings()
    idle_threshold_ms = int(settings.trim_idle_threshold.total_seconds() * 1000)

    # Get information about all consumer groups for this stream
    groups = await redis_client.xinfo_groups(stream_name)
    if not groups:
        logger.debug(f"No consumer groups found for stream {stream_name}")
        return

    # Find the lowest last-delivered-id across all active groups
    group_ids = []
    for group in groups:
        if group["last-delivered-id"] == "0-0":
            # Skip groups that haven't consumed anything
            continue

        # Check if this group has any active (non-idle) consumers
        try:
            consumers = await redis_client.xinfo_consumers(stream_name, group["name"])
            if consumers and all(
                consumer["idle"] > idle_threshold_ms for consumer in consumers
            ):
                # All consumers in this group are idle beyond threshold
                logger.debug(
                    f"Skipping idle consumer group '{group['name']}' "
                    f"(all {len(consumers)} consumers idle > {idle_threshold_ms}ms)"
                )
                continue
        except Exception as e:
            # If we can't check consumer idle times, include the group to be safe
            logger.debug(f"Unable to check consumers for group '{group['name']}': {e}")

        group_ids.append(group["last-delivered-id"])

    if not group_ids:
        logger.debug(f"No active consumer groups found for stream {stream_name}")
        return

    lowest_id = min(group_ids)

    if lowest_id == "0-0":
        logger.debug(f"No messages have been delivered in stream {stream_name}")
        return

    # Trim the stream up to (but not including) the lowest ID
    # XTRIM with MINID removes all entries with IDs strictly lower than the given ID
    await redis_client.xtrim(stream_name, minid=lowest_id, approximate=False)


async def _cleanup_empty_consumer_groups(stream_name: str) -> None:
    """
    Removes consumer groups that have no active consumers.

    Consumer groups with no consumers are considered abandoned and can safely be
    deleted to prevent them from blocking stream trimming operations.

    Args:
        stream_name: The name of the Redis stream to clean up groups for
    """
    redis_client: Redis = get_async_redis_client()

    try:
        groups = await redis_client.xinfo_groups(stream_name)
    except Exception as e:
        logger.debug(f"Unable to get consumer groups for stream {stream_name}: {e}")
        return

    for group in groups:
        try:
            consumers = await redis_client.xinfo_consumers(stream_name, group["name"])
            if not consumers and group["name"].startswith("ephemeral"):
                # No consumers in this group - it's abandoned
                logger.debug(f"Deleting empty consumer group '{group['name']}'")
                await redis_client.xgroup_destroy(stream_name, group["name"])
        except Exception as e:
            # If we can't check or delete, just continue
            logger.debug(f"Unable to cleanup group '{group['name']}': {e}")
