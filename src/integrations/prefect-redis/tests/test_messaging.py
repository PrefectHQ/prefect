import asyncio
import json
from contextlib import asynccontextmanager
from typing import (
    AsyncGenerator,
    Generator,
    Optional,
)

import anyio
import pytest
from prefect_redis.client import get_async_redis_client
from prefect_redis.messaging import (
    Cache,
    Consumer,
    Message,
    Publisher,
    RedisStreamsMessage,
    StopConsumer,
)
from redis.asyncio import Redis

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


@pytest.fixture(scope="session", autouse=True)
def isolate_redis_for_xdist(worker_id):
    # Assign a unique DB per xdist worker
    if not worker_id or "gw" not in worker_id:
        db_num = 1
    else:
        db_num = 2 + int(worker_id.replace("gw", ""))

    # Update settings so that get_async_redis_client()
    # creates clients connected to this db_num
    with temporary_settings(
        updates={"PREFECT_REDIS_DB": str(db_num)},
    ):
        yield


@pytest.fixture
async def async_redis_client() -> AsyncGenerator[Redis, None]:
    # Create a new Redis client using the current settings (including db_num)
    redis = get_async_redis_client()
    try:
        yield redis
    finally:
        await redis.aclose()


@pytest.fixture(autouse=True)
async def reset_redis(async_redis_client: Redis):
    await async_redis_client.flushall()


@pytest.fixture(autouse=True)
def events_configuration():
    pass  # TODO - do we need this?


@pytest.fixture(autouse=True)
def clear_topics(events_configuration: None):
    pass  # TODO - do we need this?


@pytest.fixture
def busted_cache_module():
    with temporary_settings(updates={PREFECT_MESSAGING_CACHE: "whodis"}):
        yield


@pytest.fixture
def busted_broker_module():
    with temporary_settings(updates={PREFECT_MESSAGING_BROKER: "whodis"}):
        yield


def test_unknown_broker_raises_for_creating_publisher(busted_broker_module):
    with pytest.raises(ImportError, match="whodis"):
        create_publisher("my-topic")


def test_unknown_broker_raises_for_creating_consumer(busted_broker_module):
    with pytest.raises(ImportError, match="whodis"):
        create_consumer("my-topic")


async def test_unknown_broker_raises_for_ephemeral_subscription(busted_broker_module):
    with pytest.raises(ImportError, match="whodis"):
        context = ephemeral_subscription("my-topic")
        await context.__aenter__()


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


def test_unknown_cache_raises_for_creating_publisher(
    broker_module_name: str, busted_cache_module
):
    with pytest.raises(ImportError, match="whodis"):
        create_publisher("my-topic")


@pytest.fixture
def broker(broker_module_name: str) -> Generator[str, None, None]:
    with temporary_settings(updates={PREFECT_MESSAGING_BROKER: broker_module_name}):
        yield broker_module_name


@pytest.fixture
def configured_cache(cache_name: str) -> Generator[str, None, None]:
    with temporary_settings(updates={PREFECT_MESSAGING_CACHE: cache_name}):
        yield cache_name


@pytest.fixture
async def cache(configured_cache: str) -> AsyncGenerator[Cache, None]:
    cache = create_cache()
    await cache.clear_recently_seen_messages()
    yield cache
    await cache.clear_recently_seen_messages()


@pytest.fixture
async def publisher(broker: str, cache: Cache) -> Publisher:
    return create_publisher("my-topic", cache=Cache)


@pytest.fixture
async def consumer(broker: str, clear_topics: None) -> Consumer:
    return create_consumer("my-topic", should_process_pending_messages=True)


async def drain_one(consumer: Consumer) -> Optional[Message]:
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
    (message,) = captured_messages
    assert message.data == b"hello, world"
    assert message.attributes == {"howdy": "partner"}

    remaining_message = await drain_one(consumer)
    assert not remaining_message


async def test_stopping_consumer_without_acking(
    publisher: Publisher, consumer: Consumer
) -> None:
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
    (message,) = captured_messages
    assert message.data == b"hello, world"
    assert message.attributes == {"howdy": "partner"}

    remaining_message = await drain_one(consumer)
    assert remaining_message == message


async def test_erroring_handler_does_not_ack(
    publisher: Publisher, consumer: Consumer
) -> None:
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
    print(
        captured_messages, captured_messages[0].__dict__, captured_messages[1].__dict__
    )
    (message1, message2) = captured_messages
    assert message1 == message2

    remaining_message = await drain_one(consumer)
    assert not remaining_message


@pytest.fixture
def deduplicating_publisher(broker: str, cache: Cache) -> Publisher:
    return create_publisher("my-topic", cache, deduplicate_by="my-message-id")


async def test_publisher_will_avoid_sending_duplicate_messages_in_same_batch(
    deduplicating_publisher: Publisher, consumer: Consumer
):
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
    (message,) = captured_messages
    assert message.data == b"hello, world"
    assert message.attributes == {"my-message-id": "A", "howdy": "partner"}

    remaining_message = await drain_one(consumer)
    assert not remaining_message


async def test_publisher_will_avoid_sending_duplicate_messages_in_different_batches(
    deduplicating_publisher: Publisher, consumer: Consumer
):
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

        async with deduplicating_publisher as p:
            await p.publish_data(
                b"hello, world", {"my-message-id": "A", "doesn't": "matter"}
            )
    finally:
        await consumer_task

    assert len(captured_messages) == 1
    (message,) = captured_messages
    assert message.data == b"hello, world"
    assert message.attributes == {"my-message-id": "A", "howdy": "partner"}

    remaining_message = await drain_one(consumer)
    assert not remaining_message


@asynccontextmanager
async def break_topic():
    from unittest import mock

    publishing_mock = mock.AsyncMock(side_effect=ValueError("oops"))

    # Patch Redis xadd method so that publishing raises ValueError
    with mock.patch("redis.asyncio.client.Redis.xadd", publishing_mock):
        yield


async def test_broken_topic_reraises(
    publisher: Publisher,
    consumer: Consumer,
) -> None:
    with pytest.raises(ValueError, match="oops"):
        async with break_topic():
            async with publisher as p:
                await p.publish_data(b"hello, world", {"howdy": "partner"})

    remaining_message = await drain_one(consumer)
    assert not remaining_message


async def test_publisher_will_forget_duplicate_messages_on_error(
    deduplicating_publisher: Publisher,
    consumer: Consumer,
):
    with pytest.raises(ValueError, match="oops"):
        async with break_topic():
            async with deduplicating_publisher as p:
                await p.publish_data(
                    b"hello, world", {"my-message-id": "A", "howdy": "partner"}
                )

    # with the topic broken, the message won't be published
    remaining_message = await drain_one(consumer)
    assert not remaining_message

    # but on a subsequent attempt, the message is published and not considered duplicate
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
    finally:
        await consumer_task

    assert len(captured_messages) == 1
    (message,) = captured_messages
    assert message.data == b"hello, world"
    assert message.attributes == {"my-message-id": "A", "howdy": "partner"}

    remaining_message = await drain_one(consumer)
    assert not remaining_message


async def test_publisher_does_not_interfere_with_duplicate_messages_without_id(
    deduplicating_publisher: Publisher, consumer: Consumer
):
    captured_messages: list[Message] = []

    async def handler(message: Message):
        captured_messages.append(message)
        if len(captured_messages) == 2:
            raise StopConsumer(ack=True)

    consumer_task = asyncio.create_task(consumer.run(handler))

    try:
        async with deduplicating_publisher as p:
            await p.publish_data(b"hello, world", {"howdy": "partner"})
            await p.publish_data(b"hello, world", {"howdy": "partner"})
    finally:
        await consumer_task

    assert len(captured_messages) == 2
    (message1, message2) = captured_messages

    assert message1 is not message2

    assert message1.data == b"hello, world"
    assert message1.attributes == {"howdy": "partner"}

    assert message2.data == b"hello, world"
    assert message2.attributes == {"howdy": "partner"}

    remaining_message = await drain_one(consumer)
    assert not remaining_message


async def test_publisher_does_not_interfere_with_duplicate_messages_without_id_on_error(
    deduplicating_publisher: Publisher,
    consumer: Consumer,
):
    with pytest.raises(ValueError, match="oops"):
        async with break_topic():
            async with deduplicating_publisher as p:
                await p.publish_data(b"hello, world", {"howdy": "partner"})

    # with the topic broken, the message won't be published
    remaining_message = await drain_one(consumer)
    assert not remaining_message

    # but on a subsequent attempt, the message is published
    captured_messages: list[Message] = []

    async def handler(message: Message):
        captured_messages.append(message)
        raise StopConsumer(ack=True)

    consumer_task = asyncio.create_task(consumer.run(handler))

    try:
        async with deduplicating_publisher as p:
            await p.publish_data(b"hello, world", {"howdy": "partner"})
    finally:
        await consumer_task

    assert len(captured_messages) == 1
    (message,) = captured_messages

    assert message.data == b"hello, world"
    assert message.attributes == {"howdy": "partner"}

    remaining_message = await drain_one(consumer)
    assert not remaining_message


async def test_ephemeral_subscription(broker: str, publisher: Publisher):
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
        (message,) = captured_messages
        assert message.data == b"hello, world"
        assert message.attributes == {"howdy": "partner"}

        remaining_message = await drain_one(consumer)
        assert not remaining_message


#     # TODO: is there a way we can test that ephemeral subscriptions really have cleaned
#     # up after themselves after they have exited?  This will differ significantly by
#     # each broker implementation, so it's hard to write a generic test.


async def test_repeatedly_failed_message_is_moved_to_dead_letter_queue(
    deduplicating_publisher: Publisher,
    consumer: Consumer,
):
    captured_messages: list[Message] = []

    async def handler(message: Message):
        captured_messages.append(message)
        raise ValueError("Simulated failure")

    consumer_task = asyncio.create_task(consumer.run(handler))

    async with Redis(host="localhost", port=6379, db=0) as redis:
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
            # Ensure consumer task is always cleaned up
            if not consumer_task.done():
                consumer_task.cancel()
                try:
                    await consumer_task
                except (asyncio.CancelledError, Exception):
                    pass

        # Message should have been moved to DLQ after multiple retries
        assert len(captured_messages) == 4  # Original attempt + 3 retries
        for message in captured_messages:
            assert message.data == b"hello, world"
            assert message.attributes == {"howdy": "partner", "my-message-id": "A"}

        # Verify message is in Redis DLQ
        dlq_messages = await redis.smembers(consumer.subscription.dlq_key)
        assert len(dlq_messages) == 1

        dlq_message_id = dlq_messages.pop()
        dlq_data = await redis.hget(dlq_message_id, "data")
        dlq_message_data = json.loads(dlq_data)

        dlq_message = RedisStreamsMessage(
            data=dlq_message_data["data"],
            attributes=dlq_message_data["attributes"],
            acker=None,
        )

        assert dlq_message.data == "hello, world"
        assert dlq_message.attributes == {"howdy": "partner", "my-message-id": "A"}
        assert (
            dlq_message_data["retry_count"] > 3
        )  # Check retry_count from the raw data

        remaining_message = await drain_one(consumer)
        assert not remaining_message
