import asyncio
import json
from typing import AsyncGenerator, Generator, Optional

import anyio
import pytest
from prefect_redis.client import get_async_redis_client
from prefect_redis.messaging import (
    Cache,
    Consumer,
    Message,
    Publisher,
    StopConsumer,
)

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
    cache = create_cache("my-topic")
    await cache.clear_recently_seen_messages()
    yield cache
    await cache.clear_recently_seen_messages()


@pytest.fixture
async def publisher(broker: str, cache: Cache) -> Publisher:
    """Create a publisher instance for testing."""
    return create_publisher("my-topic", cache=cache)


@pytest.fixture
async def consumer(broker: str) -> Consumer:
    """Create a consumer instance for testing."""
    return create_consumer("my-topic")


@pytest.fixture
def deduplicating_publisher(broker: str, cache: Cache) -> Publisher:
    """Create a publisher that deduplicates messages."""
    return create_publisher("my-topic", cache, deduplicate_by="my-message-id")


async def drain_one(consumer: Consumer) -> Optional[Message]:
    """Utility function to drain one message from a consumer."""
    captured_messages: list[Message] = []

    async def handler(message: Message):
        captured_messages.append(message)
        raise StopConsumer(ack=False)

    with anyio.move_on_after(0.1):
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

    # Message should still be available since we didn't ack
    remaining_message = await drain_one(consumer)
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
    deduplicating_publisher: Publisher,
    consumer: Consumer,
):
    """Test that messages are moved to DLQ after repeated failures."""
    captured_messages: list[Message] = []

    async def handler(message: Message):
        captured_messages.append(message)
        raise ValueError("Simulated failure")

    consumer_task = asyncio.create_task(consumer.run(handler))

    redis = get_async_redis_client()
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

    async with ephemeral_subscription("my-topic") as consumer_kwargs:
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


async def test_verify_ephemeral_cleanup(broker: str):
    """Verify that ephemeral subscriptions clean up after themselves."""
    redis = get_async_redis_client()

    async with ephemeral_subscription("my-topic") as consumer_kwargs:
        group_name = consumer_kwargs["group"]
        # Verify group exists
        groups = await redis.xinfo_groups("my-topic")
        assert any(g["name"] == group_name for g in groups)

    # Verify group is cleaned up
    groups = await redis.xinfo_groups("my-topic")
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
            "my-topic", cache=create_cache("my-topic"), batch_size=batch_size
        ) as p:
            for data, attributes in messages:
                await p.publish_data(data, attributes)
    finally:
        await consumer_task

    assert len(captured_messages) == len(messages)
    for i, message in enumerate(captured_messages):
        assert message.data == f"message-{i}"
        assert message.attributes == {"id": str(i)}
