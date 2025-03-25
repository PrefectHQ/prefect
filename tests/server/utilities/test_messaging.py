import asyncio
import importlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import (
    AsyncContextManager,
    AsyncGenerator,
    Callable,
    Generator,
    Optional,
)

import anyio
import pytest

from prefect.server.events.clients import PrefectServerEventsClient
from prefect.server.events.messaging import EventPublisher
from prefect.server.events.schemas.events import Event, ReceivedEvent, Resource
from prefect.server.utilities.messaging import (
    BrokerModule,
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
from prefect.server.utilities.messaging.memory import (
    Consumer as MemoryConsumer,
)
from prefect.server.utilities.messaging.memory import (
    MemoryMessage,
)
from prefect.settings import (
    PREFECT_MESSAGING_BROKER,
    PREFECT_MESSAGING_CACHE,
    temporary_settings,
)


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
            [
                "prefect.server.utilities.messaging.memory",
            ],
        )

    if "cache_name" in metafunc.fixturenames:
        metafunc.parametrize(
            "cache_name",
            [
                "prefect.server.utilities.messaging.memory",
            ],
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
    return create_consumer("my-topic", concurrency=1)


async def drain_one(consumer: Consumer) -> Optional[Message]:
    captured_messages: list[Message] = []

    async def handler(message: Message):
        captured_messages.append(message)
        raise StopConsumer(ack=True)

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


@pytest.fixture
def break_topic(
    broker_module_name: str,
) -> Callable[[], AsyncContextManager[None]]:
    module: BrokerModule = importlib.import_module(broker_module_name)
    return module.break_topic


async def test_broken_topic_reraises(
    publisher: Publisher,
    consumer: Consumer,
    break_topic: Callable[[], AsyncContextManager[None]],
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
    break_topic: Callable[[], AsyncContextManager[None]],
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
    break_topic: Callable[[], AsyncContextManager[None]],
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

    # TODO: is there a way we can test that ephemeral subscriptions really have cleaned
    # up after themselves after they have exited?  This will differ significantly by
    # each broker implementation, so it's hard to write a generic test.


async def test_repeatedly_failed_message_is_moved_to_dead_letter_queue(
    deduplicating_publisher: Publisher,
    consumer: MemoryConsumer,
    tmp_path: Path,
):
    captured_messages: list[Message] = []

    async def handler(message: Message):
        captured_messages.append(message)
        raise ValueError("Simulated failure")

    consumer.subscription.dead_letter_queue_path = tmp_path / "dlq"

    consumer_task = asyncio.create_task(consumer.run(handler))

    async with deduplicating_publisher as p:
        await p.publish_data(
            b"hello, world", {"howdy": "partner", "my-message-id": "A"}
        )

    while not list(consumer.subscription.dead_letter_queue_path.glob("*")):
        await asyncio.sleep(0.1)

    try:
        consumer_task.cancel()
        await consumer_task
    except asyncio.CancelledError:
        pass

    # Message should have been moved to DLQ after multiple retries
    assert len(captured_messages) == 4  # Original attempt + 3 retries
    for message in captured_messages:
        assert message.data == b"hello, world"
        assert message.attributes == {"howdy": "partner", "my-message-id": "A"}

    # Verify message is in DLQ
    assert len(list(consumer.subscription.dead_letter_queue_path.glob("*"))) == 1
    dlq_message_file = next(
        iter(consumer.subscription.dead_letter_queue_path.glob("*"))
    )
    dlq_message = MemoryMessage(**json.loads(dlq_message_file.read_text()))
    assert dlq_message.data == "hello, world"
    assert dlq_message.attributes == {"howdy": "partner", "my-message-id": "A"}
    assert dlq_message.retry_count > 3

    remaining_message = await drain_one(consumer)
    assert not remaining_message


async def test_can_be_used_as_event_publisher(broker: str, cache: Cache):
    """Test that a memory broker can be used as an event publisher"""
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


@pytest.mark.usefixtures("broker", "clear_topics")
@pytest.mark.parametrize("concurrency,num_messages", [(2, 4), (4, 8)])
async def test_concurrent_consumers_process_messages(
    publisher: Publisher, concurrency: int, num_messages: int
) -> None:
    """Test that messages are fairly distributed across concurrent consumers"""
    concurrent_consumer = create_consumer("my-topic", concurrency=concurrency)
    processed_messages: list[Message] = []
    processed_by_consumer: dict[int, list[Message]] = {
        i + 1: [] for i in range(concurrency)
    }
    consumer_seen = 0
    processing_order: list[int] = []

    async def handler(message: Message):
        nonlocal consumer_seen
        # Track which consumer got the message
        consumer_id = consumer_seen % concurrency + 1
        consumer_seen += 1
        processed_by_consumer[consumer_id].append(message)
        processed_messages.append(message)
        processing_order.append(consumer_id)

        # First consumer is slow but should still get its fair share
        if consumer_id == 1:
            await asyncio.sleep(0.1)

        if len(processed_messages) >= num_messages:
            raise StopConsumer(ack=True)

    consumer_task = asyncio.create_task(concurrent_consumer.run(handler))

    try:
        async with publisher as p:
            # Send multiple messages
            for i in range(num_messages):
                await p.publish_data(f"message-{i}".encode(), {"index": str(i)})
    finally:
        await consumer_task

    # Verify total messages processed
    assert len(processed_messages) == num_messages

    # Verify all consumers processed equal number of messages
    messages_per_consumer = num_messages // concurrency
    for consumer_id in range(1, concurrency + 1):
        assert len(processed_by_consumer[consumer_id]) == messages_per_consumer, (
            f"Consumer {consumer_id} should process exactly {messages_per_consumer} messages"
        )

    # Verify messages were processed in round-robin order
    expected_order = [(i % concurrency) + 1 for i in range(num_messages)]
    assert processing_order == expected_order, (
        "Messages should be distributed in round-robin fashion"
    )

    # Verify each consumer got the correct messages
    for consumer_id in range(1, concurrency + 1):
        expected_indices = list(range(consumer_id - 1, num_messages, concurrency))
        actual_indices = [
            int(msg.attributes["index"]) for msg in processed_by_consumer[consumer_id]
        ]
        assert actual_indices == expected_indices, (
            f"Consumer {consumer_id} should process messages {expected_indices}"
        )
