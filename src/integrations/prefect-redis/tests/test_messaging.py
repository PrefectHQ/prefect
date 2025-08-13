import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from functools import partial
from typing import AsyncGenerator, Generator, Optional

import anyio
import pytest
from prefect_redis.messaging import (
    Cache,
    Consumer,
    Message,
    Publisher,
    RedisMessagingConsumerSettings,
    RedisMessagingPublisherSettings,
    StopConsumer,
    _cleanup_empty_consumer_groups,
    _trim_stream_to_lowest_delivered_id,
)
from redis.asyncio import Redis

from prefect.server.events import Event
from prefect.server.events.clients import PrefectServerEventsClient
from prefect.server.events.messaging import EventPublisher
from prefect.server.events.schemas.events import ReceivedEvent, Resource
from prefect.server.utilities.messaging import (
    create_cache,
    create_consumer,
    create_publisher,
    ephemeral_subscription,
)
from prefect.settings import (
    PREFECT_MESSAGING_BROKER,
    PREFECT_MESSAGING_CACHE,
    temporary_settings,
)


def pytest_generate_tests(metafunc: pytest.Metafunc):
    if "broker_module_name" in metafunc.fixturenames:
        metafunc.parametrize(
            "broker_module_name",
            ["prefect_redis.messaging"],
        )

    if "cache_name" in metafunc.fixturenames:
        metafunc.parametrize(
            "cache_name",
            ["prefect_redis.messaging"],
        )


@pytest.fixture
def broker(broker_module_name: str) -> Generator[str, None, None]:
    """Configure the broker for testing."""
    with temporary_settings(updates={PREFECT_MESSAGING_BROKER: broker_module_name}):
        yield broker_module_name


@pytest.fixture
def configured_cache(cache_name: str) -> Generator[str, None, None]:
    """Configure the cache for testing."""
    with temporary_settings(updates={PREFECT_MESSAGING_CACHE: cache_name}):
        yield cache_name


@pytest.fixture
async def cache(configured_cache: str) -> AsyncGenerator[Cache, None]:
    """Create a cache instance for testing."""
    cache = create_cache()
    await cache.clear_recently_seen_messages()
    yield cache
    await cache.clear_recently_seen_messages()


@pytest.fixture
async def publisher(broker: str, cache: Cache) -> Publisher:
    """Create a publisher instance for testing."""
    return create_publisher("message-tests", cache=cache)


@pytest.fixture
async def consumer(broker: str) -> Consumer:
    """Create a consumer instance for testing."""
    return create_consumer("message-tests")


@pytest.fixture
async def consumer_a(consumer: Consumer) -> Consumer:
    """Create a consumer instance for testing."""
    return consumer


@pytest.fixture
async def consumer_b(broker: str) -> Consumer:
    """Create a second consumer instance for testing."""
    return create_consumer("message-tests")


@pytest.fixture
def deduplicating_publisher(broker: str, cache: Cache) -> Publisher:
    """Create a publisher that deduplicates messages."""
    return create_publisher("message-tests", cache, deduplicate_by="my-message-id")


async def drain_one(consumer: Consumer) -> Optional[Message]:
    """Utility function to drain one message from a consumer."""
    captured_messages: list[Message] = []

    async def handler(message: Message):
        captured_messages.append(message)
        raise StopConsumer(ack=False)

    with anyio.move_on_after(1.0):  # Reasonable timeout for tests
        await consumer.run(handler)

    return captured_messages[0] if captured_messages else None


async def test_publishing_and_consuming_a_single_message(
    publisher: Publisher, consumer: Consumer
) -> None:
    """Test basic publish and consume functionality."""
    captured_messages: list[Message] = []

    async def handler(message: Message):
        captured_messages.append(message)
        raise StopConsumer(ack=True)

    consumer_task = asyncio.create_task(consumer.run(handler))

    try:
        async with publisher as p:
            await p.publish_data(b"hello, world", {"howdy": "partner"})
    finally:
        await consumer_task

    assert len(captured_messages) == 1
    message = captured_messages[0]
    assert message.data == "hello, world"
    assert message.attributes == {"howdy": "partner"}

    remaining_message = await drain_one(consumer)
    assert not remaining_message


async def test_stopping_consumer_without_acking(
    publisher: Publisher, consumer: Consumer
) -> None:
    """Test that messages remain in queue when not acknowledged."""
    captured_messages: list[Message] = []

    async def handler(message: Message):
        captured_messages.append(message)
        raise StopConsumer(ack=False)

    consumer_task = asyncio.create_task(consumer.run(handler))

    try:
        async with publisher as p:
            await p.publish_data(b"hello, world", {"howdy": "partner"})
    finally:
        await consumer_task

    assert len(captured_messages) == 1
    message = captured_messages[0]
    assert message.data == "hello, world"
    assert message.attributes == {"howdy": "partner"}

    # Create a test consumer with short min_idle_time for faster testing
    test_consumer = create_consumer(
        "message-tests", min_idle_time=timedelta(seconds=0.1)
    )

    # Wait for the message to become "idle" (longer than min_idle_time)
    await asyncio.sleep(0.2)

    # Message should still be available since we didn't ack
    remaining_message = await drain_one(test_consumer)
    assert remaining_message is not None, "Message should be available for reclaiming"
    assert remaining_message == message


async def test_erroring_handler_does_not_ack(
    publisher: Publisher, consumer: Consumer
) -> None:
    """Test that failed message processing doesn't acknowledge the message."""
    captured_messages: list[Message] = []

    async def handler(message: Message):
        captured_messages.append(message)
        if len(captured_messages) == 1:
            raise ValueError("oops")
        else:
            raise StopConsumer(ack=True)

    consumer_task = asyncio.create_task(consumer.run(handler))

    try:
        async with publisher as p:
            await p.publish_data(b"hello, world", {"howdy": "partner"})
    finally:
        await consumer_task

    assert len(captured_messages) == 2
    message1, message2 = captured_messages
    assert message1 == message2  # Same message redelivered

    remaining_message = await drain_one(consumer)
    assert not remaining_message  # Finally acknowledged


async def test_publisher_will_avoid_sending_duplicate_messages_in_same_batch(
    deduplicating_publisher: Publisher, consumer: Consumer
):
    """Test deduplication within the same batch of messages."""
    captured_messages: list[Message] = []

    async def handler(message: Message):
        captured_messages.append(message)
        raise StopConsumer(ack=True)

    consumer_task = asyncio.create_task(consumer.run(handler))

    try:
        async with deduplicating_publisher as p:
            await p.publish_data(
                b"hello, world", {"my-message-id": "A", "howdy": "partner"}
            )
            await p.publish_data(
                b"hello, world", {"my-message-id": "A", "doesn't": "matter"}
            )
    finally:
        await consumer_task

    assert len(captured_messages) == 1
    message = captured_messages[0]
    assert message.data == "hello, world"
    assert message.attributes == {"my-message-id": "A", "howdy": "partner"}

    remaining_message = await drain_one(consumer)
    assert not remaining_message


async def test_repeatedly_failed_message_is_moved_to_dead_letter_queue(
    redis: Redis,
    deduplicating_publisher: Publisher,
    consumer: Consumer,
):
    """Test that messages are moved to DLQ after repeated failures."""
    captured_messages: list[Message] = []

    async def handler(message: Message):
        captured_messages.append(message)
        raise ValueError("Simulated failure")

    consumer_task = asyncio.create_task(consumer.run(handler))

    try:
        async with deduplicating_publisher as p:
            await p.publish_data(
                b"hello, world", {"howdy": "partner", "my-message-id": "A"}
            )

        # Wait for message to appear in DLQ
        while True:
            dlq_size = await redis.scard(consumer.subscription.dlq_key)
            if dlq_size > 0:
                break
            await asyncio.sleep(0.1)

    finally:
        if not consumer_task.done():
            consumer_task.cancel()
            try:
                await consumer_task
            except (asyncio.CancelledError, Exception):
                pass

    # Message should have been moved to DLQ after multiple retries
    assert len(captured_messages) == 4  # Original attempt + 3 retries
    for message in captured_messages:
        assert message.data == "hello, world"
        assert message.attributes == {"howdy": "partner", "my-message-id": "A"}

    # Verify message is in Redis DLQ
    dlq_messages = await redis.smembers(consumer.subscription.dlq_key)
    assert len(dlq_messages) == 1

    dlq_message_id = dlq_messages.pop()
    dlq_data = await redis.hget(dlq_message_id, "data")
    dlq_message_data = json.loads(dlq_data)

    assert dlq_message_data["data"] == "hello, world"
    assert dlq_message_data["attributes"] == {"howdy": "partner", "my-message-id": "A"}
    assert dlq_message_data["retry_count"] > 3

    remaining_message = await drain_one(consumer)
    assert not remaining_message


async def test_ephemeral_subscription(broker: str, publisher: Publisher):
    """Test ephemeral subscription lifecycle."""
    captured_messages: list[Message] = []

    async def handler(message: Message):
        captured_messages.append(message)
        raise StopConsumer(ack=True)

    async with ephemeral_subscription("message-tests") as consumer_kwargs:
        consumer = create_consumer(**consumer_kwargs)
        consumer_task = asyncio.create_task(consumer.run(handler))

        try:
            async with publisher as p:
                await p.publish_data(b"hello, world", {"howdy": "partner"})
        finally:
            await consumer_task

        assert len(captured_messages) == 1
        message = captured_messages[0]
        assert message.data == "hello, world"
        assert message.attributes == {"howdy": "partner"}

        remaining_message = await drain_one(consumer)
        assert not remaining_message


async def test_verify_ephemeral_cleanup(redis: Redis, broker: str):
    """Verify that ephemeral subscriptions clean up after themselves."""
    async with ephemeral_subscription("message-tests") as consumer_kwargs:
        group_name = consumer_kwargs["group"]
        # Verify group exists
        groups = await redis.xinfo_groups("message-tests")
        assert any(g["name"] == group_name for g in groups)

    # Verify group is cleaned up
    groups = await redis.xinfo_groups("message-tests")
    assert not any(g["name"] == group_name for g in groups)


@pytest.mark.parametrize("batch_size", [1, 5])
async def test_publisher_respects_batch_size(
    publisher: Publisher, consumer: Consumer, batch_size: int
):
    """Test that publisher respects the configured batch size."""
    messages = [(f"message-{i}".encode(), {"id": str(i)}) for i in range(10)]
    captured_messages: list[Message] = []

    async def handler(message: Message):
        captured_messages.append(message)
        if len(captured_messages) == len(messages):
            raise StopConsumer(ack=True)

    consumer_task = asyncio.create_task(consumer.run(handler))

    try:
        async with Publisher(
            "message-tests", cache=create_cache(), batch_size=batch_size
        ) as p:
            for data, attributes in messages:
                await p.publish_data(data, attributes)
    finally:
        await consumer_task

    assert len(captured_messages) == len(messages)
    for i, message in enumerate(captured_messages):
        assert message.data == f"message-{i}"
        assert message.attributes == {"id": str(i)}


async def test_trimming_streams(
    redis: Redis, publisher: Publisher, consumer_a: Consumer, consumer_b: Consumer
) -> None:
    """Test that streams are trimmed after messages are processed."""
    # Given the consumers an aggressive trimming frequency for the tests
    consumer_a.trim_every = timedelta(seconds=0)
    consumer_b.trim_every = timedelta(seconds=0)

    # Make sure we're starting with a clean slate
    assert await redis.xlen("message-tests") == 0

    # Publish a known number of messages to the stream
    TO_SEND = 113
    async with publisher as p:
        for i in range(TO_SEND):
            await p.publish_data(b"hello, world!", {"sequence": f"{i + 1}"})

    assert await redis.xlen("message-tests") == TO_SEND

    # ...then run two consumers that will each see some of the messages, capturing the
    # ones they've seen along the way
    seen_messages = {
        "A": set(),
        "B": set(),
    }

    async def handler(consumer_name: str, message: Message):
        sequence = int(message.attributes["sequence"])
        seen_messages[consumer_name].add(sequence)
        total_seen = sum(len(seen) for seen in seen_messages.values())
        if total_seen == TO_SEND:
            raise StopConsumer(ack=True)

    consumer_tasks = [
        asyncio.create_task(consumer_a.run(partial(handler, "A"))),
        asyncio.create_task(consumer_b.run(partial(handler, "B"))),
    ]
    for task in asyncio.as_completed(consumer_tasks):
        await task
        for task in consumer_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        break

    # ...then confirm that they have each seen some of the messages
    assert seen_messages["A"] | seen_messages["B"]
    assert seen_messages["A"], "Each consumer should have seen some messages"
    assert seen_messages["B"], "Each consumer should have seen some messages"

    # ...confirm that the stream has been trimmed at least partially
    assert await redis.xlen("message-tests") < TO_SEND


async def test_can_be_used_as_event_publisher(broker: str, cache: Cache):
    """Test that a Redis publisher can be used with an events client."""
    async with ephemeral_subscription("events") as consumer_kwargs:
        consumer = create_consumer(**consumer_kwargs)

        captured_events: list[ReceivedEvent] = []

        async def handler(message: Message):
            event = ReceivedEvent.model_validate_json(message.data)
            captured_events.append(event)
            if len(captured_events) == 1:
                raise StopConsumer(ack=True)

        consumer_task = asyncio.create_task(consumer.run(handler))

        async with PrefectServerEventsClient() as client:
            assert isinstance(client._publisher, EventPublisher)
            assert isinstance(client._publisher._publisher, Publisher)
            emitted_event = await client.emit(
                Event(
                    id=uuid.uuid4(),
                    occurred=datetime.now(tz=timezone.utc),
                    event="testing",
                    resource=Resource({"prefect.resource.id": "testing"}),
                )
            )
        await consumer_task

    assert captured_events == [emitted_event]


class TestRedisMessagingSettings:
    """Test the Redis messaging settings."""

    def test_publisher_settings(self):
        """Test Redis publisher settings."""
        settings = RedisMessagingPublisherSettings()
        assert settings.batch_size == 5
        assert settings.publish_every == timedelta(seconds=10)
        assert settings.deduplicate_by is None

    def test_consumer_settings(self):
        """Test Redis consumer settings."""
        settings = RedisMessagingConsumerSettings()
        assert settings.block == timedelta(seconds=1)
        assert settings.min_idle_time == timedelta(seconds=5)
        assert settings.max_retries == 3
        assert settings.trim_every == timedelta(seconds=60)
        assert settings.should_process_pending_messages is True
        assert settings.starting_message_id == "0"
        assert settings.automatically_acknowledge is True

    def test_publisher_settings_can_be_overridden(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that Redis publisher settings can be overridden."""
        monkeypatch.setenv("PREFECT_REDIS_MESSAGING_PUBLISHER_BATCH_SIZE", "10")
        settings = RedisMessagingPublisherSettings()
        assert settings.batch_size == 10

    def test_consumer_settings_can_be_overridden(self, monkeypatch: pytest.MonkeyPatch):
        """Test that Redis consumer settings can be overridden."""
        monkeypatch.setenv("PREFECT_REDIS_MESSAGING_CONSUMER_BLOCK", "10")
        settings = RedisMessagingConsumerSettings()
        assert settings.block == timedelta(seconds=10)


async def test_trimming_with_no_delivered_messages(redis: Redis):
    """Test that stream trimming handles the case where no messages have been delivered."""

    stream_name = "test-trim-stream"

    # Create a stream with some messages
    await redis.xadd(stream_name, {"data": "test1"})
    await redis.xadd(stream_name, {"data": "test2"})

    # Create consumer groups that haven't consumed anything (last-delivered-id = "0-0")
    await redis.xgroup_create(stream_name, "group1", id="0", mkstream=True)
    await redis.xgroup_create(stream_name, "group2", id="0", mkstream=True)

    # This should not raise a ValueError due to min() on empty sequence
    await _trim_stream_to_lowest_delivered_id(stream_name)

    # Stream should remain unchanged since no messages were delivered
    length = await redis.xlen(stream_name)
    assert length == 2


async def test_trimming_skips_idle_consumer_groups(
    redis: Redis, monkeypatch: pytest.MonkeyPatch
):
    """Test that stream trimming skips consumer groups with all consumers idle beyond threshold."""

    stream_name = "test-trim-idle-stream"

    # Create a stream with 10 messages
    message_ids = []
    for i in range(10):
        msg_id = await redis.xadd(stream_name, {"data": f"test{i}"})
        message_ids.append(msg_id)

    # Create two consumer groups
    await redis.xgroup_create(stream_name, "active-group", id="0")
    await redis.xgroup_create(stream_name, "stuck-group", id="0")

    # Active group consumes all messages
    messages = await redis.xreadgroup(
        groupname="active-group",
        consumername="consumer-1",
        streams={stream_name: ">"},
        count=10,
    )
    for stream, msgs in messages:
        for msg_id, data in msgs:
            await redis.xack(stream_name, "active-group", msg_id)

    # Stuck group only consumes first 3 messages
    messages = await redis.xreadgroup(
        groupname="stuck-group",
        consumername="consumer-2",
        streams={stream_name: ">"},
        count=3,
    )
    stuck_last_id = None
    for stream, msgs in messages:
        for msg_id, data in msgs:
            await redis.xack(stream_name, "stuck-group", msg_id)
            stuck_last_id = msg_id

    # Wait to make consumers idle (need to wait longer than the threshold)
    await asyncio.sleep(1.5)

    # Set a very short idle threshold for testing (1 second)
    # The setting expects seconds as an integer
    monkeypatch.setenv("PREFECT_REDIS_MESSAGING_CONSUMER_TRIM_IDLE_THRESHOLD", "1")

    # Create a new active consumer to allow trimming
    # This simulates an active consumer that keeps processing
    await redis.xreadgroup(
        groupname="active-group",
        consumername="consumer-3",  # New consumer with fresh idle time
        streams={stream_name: ">"},
        count=1,
    )

    # Trim the stream - should skip the stuck group but use the active group
    await _trim_stream_to_lowest_delivered_id(stream_name)

    # Check results
    stream_info = await redis.xinfo_stream(stream_name)
    first_entry_id = (
        stream_info["first-entry"][0] if stream_info["first-entry"] else None
    )

    # The stream should be trimmed past the stuck group's position
    assert first_entry_id is not None
    assert first_entry_id > stuck_last_id

    # Should have trimmed most messages (keeping only the last one or few)
    assert (
        stream_info["length"] <= 2
    )  # Redis might keep 1-2 messages due to trimming behavior


async def test_cleanup_empty_consumer_groups(redis: Redis):
    """Test that empty consumer groups are cleaned up."""

    stream_name = "test-cleanup-stream"

    # Create a stream with a message
    await redis.xadd(stream_name, {"data": "test"})

    # Create multiple consumer groups
    await redis.xgroup_create(stream_name, "ephemeral-active-group", id="0")
    await redis.xgroup_create(stream_name, "ephemeral-empty-group-1", id="0")
    await redis.xgroup_create(stream_name, "ephemeral-empty-group-2", id="0")

    # Add a consumer to the active group
    await redis.xreadgroup(
        groupname="ephemeral-active-group",
        consumername="consumer-1",
        streams={stream_name: ">"},
        count=1,
    )

    # Verify all groups exist
    groups_before = await redis.xinfo_groups(stream_name)
    assert len(groups_before) == 3
    group_names_before = {g["name"] for g in groups_before}
    assert group_names_before == {
        "ephemeral-active-group",
        "ephemeral-empty-group-1",
        "ephemeral-empty-group-2",
    }

    # Run cleanup
    await _cleanup_empty_consumer_groups(stream_name)

    # Verify only the active group remains
    groups_after = await redis.xinfo_groups(stream_name)
    assert len(groups_after) == 1
    assert groups_after[0]["name"] == "ephemeral-active-group"
