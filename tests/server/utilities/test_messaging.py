import asyncio
from contextlib import asynccontextmanager
from typing import (
    AsyncContextManager,
    AsyncGenerator,
    Callable,
    Generator,
    List,
    Optional,
)
from unittest import mock
from unittest.mock import AsyncMock

import anyio
import pytest

from prefect.server.utilities.messaging import (
    Cache,
    Consumer,
    Message,
    Publisher,
    StopConsumer,
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


@pytest.fixture
def busted_broker():
    with temporary_settings(updates={PREFECT_MESSAGING_BROKER: "whodis"}):
        yield


@pytest.fixture
def busted_cache():
    with temporary_settings(updates={PREFECT_MESSAGING_CACHE: "whodis"}):
        yield


def test_unknown_broker_raises_for_creating_publisher(busted_broker):
    with pytest.raises(ValueError, match="Unknown message broker configured: whodis"):
        create_publisher("my-topic")


def test_unknown_broker_raises_for_creating_consumer(busted_broker):
    with pytest.raises(ValueError, match="Unknown message broker configured: whodis"):
        create_consumer("my-topic")


async def test_unknown_broker_raises_for_ephemeral_subscription(busted_broker):
    with pytest.raises(ValueError, match="Unknown message broker configured: whodis"):
        context = ephemeral_subscription("my-topic")
        await context.__aenter__()


def pytest_generate_tests(metafunc: pytest.Metafunc):
    if "broker_name" in metafunc.fixturenames:
        metafunc.parametrize("broker_name", ["memory"])
    if "cache_name" in metafunc.fixturenames:
        metafunc.parametrize("cache_name", ["memory"])


def test_unknown_cache_raises_for_creating_publisher(broker_name: str, busted_cache):
    with pytest.raises(ValueError, match="Unknown cache configured: whodis"):
        create_publisher("my-topic")


@pytest.fixture
def broker(broker_name: str) -> Generator[str, None, None]:
    with temporary_settings(updates={PREFECT_MESSAGING_BROKER: broker_name}):
        yield broker_name


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
def publisher(broker: str, cache: Cache) -> Publisher:
    return create_publisher("my-topic", cache=Cache)


@pytest.fixture
def consumer(broker: str, clear_topics: None) -> Consumer:
    return create_consumer("my-topic")


async def drain_one(consumer: Consumer) -> Optional[Message]:
    captured_messages: List[Message] = []

    async def handler(message: Message):
        captured_messages.append(message)
        raise StopConsumer(ack=True)

    with anyio.move_on_after(0.1):
        await consumer.run(handler)

    return captured_messages[0] if captured_messages else None


async def test_publishing_and_consuming_a_single_message(
    publisher: Publisher, consumer: Consumer
) -> None:
    captured_messages: List[Message] = []

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
    captured_messages: List[Message] = []

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
    captured_messages: List[Message] = []

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
    (message1, message2) = captured_messages
    assert message1 is message2

    remaining_message = await drain_one(consumer)
    assert not remaining_message


@pytest.fixture
def deduplicating_publisher(broker: str, cache: Cache) -> Publisher:
    return create_publisher("my-topic", cache, deduplicate_by="my-message-id")


async def test_publisher_will_avoid_sending_duplicate_messages_in_same_batch(
    deduplicating_publisher: Publisher, consumer: Consumer
):
    captured_messages: List[Message] = []

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
    captured_messages: List[Message] = []

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


@pytest.fixture
def break_topic() -> Callable[[], AsyncContextManager[AsyncMock]]:
    @asynccontextmanager
    async def break_topic(broker_name: str):
        publishing_mock = AsyncMock(side_effect=ValueError("oops"))

        if broker_name == "memory":
            with mock.patch(
                "prefect.server.utilities.messaging.memory.Topic.publish",
                publishing_mock,
            ):
                yield publishing_mock
        else:
            raise NotImplementedError("Implement broken publishing for this broker")

    return break_topic


async def test_break_topic_fixture_raises_for_unknown_broker(
    break_topic: Callable[[], AsyncContextManager[AsyncMock]],
):
    with pytest.raises(NotImplementedError, match="Implement broken publishing"):
        context = break_topic("whodis?")
        await context.__aenter__()


async def test_broken_topic_reraises(
    broker_name: str,
    publisher: Publisher,
    consumer: Consumer,
    break_topic: Callable[[], AsyncContextManager[AsyncMock]],
) -> None:
    with pytest.raises(ValueError, match="oops"):
        async with break_topic(broker_name):
            async with publisher as p:
                await p.publish_data(b"hello, world", {"howdy": "partner"})

    remaining_message = await drain_one(consumer)
    assert not remaining_message


async def test_publisher_will_forget_duplicate_messages_on_error(
    broker_name: str,
    deduplicating_publisher: Publisher,
    consumer: Consumer,
    break_topic: Callable[[], AsyncContextManager[AsyncMock]],
):
    with pytest.raises(ValueError, match="oops"):
        async with break_topic(broker_name):
            async with deduplicating_publisher as p:
                await p.publish_data(
                    b"hello, world", {"my-message-id": "A", "howdy": "partner"}
                )

    # with the topic broken, the message won't be published
    remaining_message = await drain_one(consumer)
    assert not remaining_message

    # but on a subsequent attempt, the message is published and not considered duplicate
    captured_messages: List[Message] = []

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
    captured_messages: List[Message] = []

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
    broker_name: str,
    deduplicating_publisher: Publisher,
    consumer: Consumer,
    break_topic: Callable[[], AsyncContextManager[AsyncMock]],
):
    with pytest.raises(ValueError, match="oops"):
        async with break_topic(broker_name):
            async with deduplicating_publisher as p:
                await p.publish_data(b"hello, world", {"howdy": "partner"})

    # with the topic broken, the message won't be published
    remaining_message = await drain_one(consumer)
    assert not remaining_message

    # but on a subsequent attempt, the message is published
    captured_messages: List[Message] = []

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
    captured_messages: List[Message] = []

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

    # TODO: is there a way we can test that ephemeral subscriptions really have cleaned
    # up after themselves after they have exited?  This will differ significantly by
    # each broker implementation, so it's hard to write a generic test.
