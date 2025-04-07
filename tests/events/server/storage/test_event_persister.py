import asyncio
import uuid
from datetime import timedelta
from typing import AsyncGenerator, Optional, Sequence
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
import sqlalchemy as sa
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.database import PrefectDBInterface, db_injector
from prefect.server.database.orm_models import ORMEventResource
from prefect.server.events.filters import EventFilter
from prefect.server.events.schemas.events import (
    ReceivedEvent,
    RelatedResource,
    Resource,
)
from prefect.server.events.services import event_persister
from prefect.server.events.services.event_persister import batch_delete
from prefect.server.events.storage.database import query_events, write_events
from prefect.server.utilities.messaging import CapturedMessage, Message, MessageHandler
from prefect.settings import PREFECT_EVENTS_RETENTION_PERIOD, temporary_settings
from prefect.types import DateTime
from prefect.types._datetime import now


@db_injector
async def get_event(db: PrefectDBInterface, id: UUID) -> Optional[ReceivedEvent]:
    async with await db.session() as session:
        result = await session.execute(sa.select(db.Event).where(db.Event.id == id))
        event = result.scalar_one_or_none()

        if not event:
            return None

        return ReceivedEvent.model_validate(event)


async def get_resources(
    session: AsyncSession, event_id_filter: Optional[UUID], db: PrefectDBInterface
) -> Sequence["ORMEventResource"]:
    query = sa.select(db.EventResource).order_by(db.EventResource.resource_id)
    if event_id_filter:
        query = query.where(db.EventResource.event_id == event_id_filter)
    result = await session.execute(query)
    return result.scalars().all()


async def get_event_count(session: AsyncSession) -> int:
    result = await session.execute(sa.text("SELECT COUNT(*) FROM events"))
    return result.scalar() or 0


@pytest.fixture
async def event_persister_handler() -> AsyncGenerator[MessageHandler, None]:
    async with event_persister.create_handler(batch_size=1) as handler:
        yield handler


@pytest.fixture
def event() -> ReceivedEvent:
    return ReceivedEvent(
        occurred=now("UTC"),
        event="hello",
        resource={"prefect.resource.id": "my.resource.id", "label-1": "value-1"},
        related=[
            {
                "prefect.resource.id": "related-1",
                "prefect.resource.role": "role-1",
                "label-1": "value-1",
                "label-2": "value-2",
            },
            {
                "prefect.resource.id": "related-2",
                "prefect.resource.role": "role-1",
                "label-1": "value-3",
                "label-2": "value-4",
            },
            {
                "prefect.resource.id": "related-3",
                "prefect.resource.role": "role-2",
                "label-1": "value-5",
                "label-2": "value-6",
            },
        ],
        payload={"hello": "world"},
        received=DateTime(2022, 2, 3, 4, 5, 6, 7).astimezone(ZoneInfo("UTC")),
        id=uuid4(),
        follows=UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
    )


@pytest.fixture
def event_with_many_related_resources() -> ReceivedEvent:
    return ReceivedEvent(
        occurred=now("UTC"),
        event="hello",
        resource=Resource(
            {"prefect.resource.id": "my.resource.id", "label-1": "value-1"}
        ),
        related=[
            RelatedResource(
                {
                    "prefect.resource.id": str(uuid.uuid4()),
                    "prefect.resource.role": "test.related",
                    "data": "test.data",
                }
            )
            for _ in range(99)
        ],
        payload={"hello": "world"},
        received=DateTime(2022, 2, 3, 4, 5, 6, 7).astimezone(ZoneInfo("UTC")),
        id=uuid4(),
        follows=UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
    )


@pytest.fixture
def message(event: ReceivedEvent) -> Message:
    return CapturedMessage(
        data=event.model_dump_json().encode(),
        attributes={},
    )


@pytest.fixture
def message_with_many_related_resources(
    event_with_many_related_resources: ReceivedEvent,
) -> Message:
    return CapturedMessage(
        data=event_with_many_related_resources.model_dump_json().encode(),
        attributes={},
    )


async def test_start_and_stop_service():
    service = event_persister.EventPersister()
    service_task = asyncio.create_task(service.start())
    service.started_event = asyncio.Event()

    await service.started_event.wait()
    assert service.consumer_task is not None

    await service.stop()
    assert service.consumer_task is None

    await service_task


async def test_handling_message_writes_event(
    frozen_time: DateTime,
    event_persister_handler: MessageHandler,
    message: Message,
    session: AsyncSession,
    event: ReceivedEvent,
):
    await event_persister_handler(message)

    stored_event = await get_event(event.id)
    assert stored_event
    assert stored_event == ReceivedEvent(
        occurred=stored_event.occurred,  # avoid microsecond differences
        event="hello",
        resource={"prefect.resource.id": "my.resource.id", "label-1": "value-1"},
        related=[
            {
                "prefect.resource.id": "related-1",
                "prefect.resource.role": "role-1",
                "label-1": "value-1",
                "label-2": "value-2",
            },
            {
                "prefect.resource.id": "related-2",
                "prefect.resource.role": "role-1",
                "label-1": "value-3",
                "label-2": "value-4",
            },
            {
                "prefect.resource.id": "related-3",
                "prefect.resource.role": "role-2",
                "label-1": "value-5",
                "label-2": "value-6",
            },
        ],
        payload={"hello": "world"},
        received=DateTime(2022, 2, 3, 4, 5, 6, 7).astimezone(ZoneInfo("UTC")),
        id=event.id,
        follows=UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
    )


async def test_handling_message_writes_event_resources(
    frozen_time: DateTime,
    db: PrefectDBInterface,
    event_persister_handler: MessageHandler,
    message: Message,
    session: AsyncSession,
    event: ReceivedEvent,
):
    await event_persister_handler(message)

    resources = await get_resources(session, event.id, db)
    primary, related_1, related_2, related_3 = resources

    for resource in resources:
        assert resource.occurred == event.occurred
        assert resource.event_id == event.id

    # Note: we're expecting the resource values to _not_ include the id and role, this
    # is to conserve space, since those are unpacked to columns for all resources

    assert primary.resource_id == "my.resource.id"
    assert primary.resource_role == ""
    assert primary.resource == {"label-1": "value-1"}

    assert related_1.resource_id == "related-1"
    assert related_1.resource_role == "role-1"
    assert related_1.resource == {"label-1": "value-1", "label-2": "value-2"}

    assert related_2.resource_id == "related-2"
    assert related_2.resource_role == "role-1"
    assert related_2.resource == {"label-1": "value-3", "label-2": "value-4"}

    assert related_3.resource_id == "related-3"
    assert related_3.resource_role == "role-2"
    assert related_3.resource == {"label-1": "value-5", "label-2": "value-6"}


async def test_handling_message_writes_event_resources_with_many_related_resources(
    frozen_time: DateTime,
    db: PrefectDBInterface,
    event_persister_handler: MessageHandler,
    message_with_many_related_resources: Message,
    session: AsyncSession,
    event_with_many_related_resources: ReceivedEvent,
):
    await event_persister_handler(message_with_many_related_resources)

    resources = await get_resources(session, event_with_many_related_resources.id, db)
    assert len(resources) == 100

    event = await get_event(event_with_many_related_resources.id)
    assert event
    assert event == event_with_many_related_resources


@pytest.fixture
def empty_message() -> Message:
    return CapturedMessage(
        data=None,
        attributes={},
    )


async def test_skips_empty_messages(
    event_persister_handler: MessageHandler,
    empty_message: Message,
    session: AsyncSession,
):
    before = await get_event_count(session)

    await event_persister_handler(empty_message)

    assert (await get_event_count(session)) == before


@pytest.fixture
def non_json_message() -> Message:
    return CapturedMessage(
        data=b"this ain't even JSON, y'all",
        attributes={},
    )


async def test_raises_for_non_json_messages(
    event_persister_handler: MessageHandler,
    non_json_message: Message,
    session: AsyncSession,
):
    before = await get_event_count(session)

    with pytest.raises(ValidationError):
        await event_persister_handler(non_json_message)

    assert (await get_event_count(session)) == before


@pytest.fixture
def non_event_message() -> Message:
    return CapturedMessage(
        data=b'{"something": "else"}',
        attributes={},
    )


async def test_raises_for_non_events(
    event_persister_handler: MessageHandler,
    non_event_message: Message,
    session: AsyncSession,
):
    before = await get_event_count(session)

    with pytest.raises(ValidationError):
        await event_persister_handler(non_event_message)

    assert (await get_event_count(session)) == before


async def test_sends_remaining_messages(
    event: ReceivedEvent,
    session: AsyncSession,
):
    async with event_persister.create_handler(
        batch_size=4,
        flush_every=timedelta(days=100),
    ) as handler:
        for _ in range(10):
            event.id = uuid4()
            message = CapturedMessage(
                data=event.model_dump_json().encode(),
                attributes={},
            )
            await handler(message)

    # The two remaining messages should get flushed when the service stops
    assert (await get_event_count(session)) == 10


async def test_flushes_messages_periodically(
    event: ReceivedEvent,
    session: AsyncSession,
):
    async with event_persister.create_handler(
        batch_size=5,
        flush_every=timedelta(seconds=0.001),
    ) as handler:
        for _ in range(9):
            event.id = uuid4()
            message = CapturedMessage(
                data=event.model_dump_json().encode(),
                attributes={},
            )
            await handler(message)

        await asyncio.sleep(0.1)  # this is 100x the time necessary

        # no matter how many batches this ended up being distributed over due to the
        # periodic flushes, we should definitely have flushed all of the records by here
        assert (await get_event_count(session)) == 9


async def test_trims_messages_periodically(
    event: ReceivedEvent, session: AsyncSession, db: PrefectDBInterface
):
    inserted_timestamps = []
    # Create entries with slightly different insert times. Since the event_resources are filtered based on the
    # "updated" column, where sqlite itself sets the timestamp, we need to actually delay the inserts.
    for _ in range(3):
        timestamp = now("UTC")
        await write_events(
            session, [event.model_copy(update={"id": uuid4(), "occurred": timestamp})]
        )
        await session.commit()  # Each commit ensures a new transaction timestamp for PostgreSQL's now() function
        inserted_timestamps.append(timestamp)
        await asyncio.sleep(0.6)  # The whole insert should be 600ms * 3 = about 1.8s

    # Half the entries are older than this, half are younger
    cutoff_date = inserted_timestamps[int(len(inserted_timestamps) / 2)] - timedelta(
        milliseconds=300
    )

    initial_events, event_count, _ = await query_events(session, filter=EventFilter())
    assert event_count == 3
    assert len(initial_events) == 3
    assert any(event.occurred < cutoff_date for event in initial_events)
    assert any(event.occurred >= cutoff_date for event in initial_events)

    initial_resources = list(await get_resources(session, None, db))
    assert len(initial_resources) == 12
    assert any(resource.occurred < cutoff_date for resource in initial_resources)
    assert any(resource.occurred >= cutoff_date for resource in initial_resources)

    # Prefect assumes a timedelta for the retention period, here we dynamically compute this to match the cutoff we want
    retention_period = now("UTC") - cutoff_date
    with temporary_settings({PREFECT_EVENTS_RETENTION_PERIOD: retention_period}):
        async with event_persister.create_handler(
            flush_every=timedelta(seconds=0.001),
            trim_every=timedelta(seconds=0.001),
        ):
            await asyncio.sleep(0.1)  # this is 100x the time necessary

    remaining_events, event_count, _ = await query_events(session, filter=EventFilter())
    assert event_count == 2
    assert len(remaining_events) == 2
    assert all(event.occurred >= cutoff_date for event in remaining_events)

    remaining_resources = await get_resources(session, None, db)
    assert len(remaining_resources) == 8
    assert all(resource.occurred >= cutoff_date for resource in remaining_resources)


async def test_batch_delete(
    event: ReceivedEvent, session: AsyncSession, db: PrefectDBInterface
):
    await write_events(
        session, [event.model_copy(update={"id": uuid4()}) for _ in range(10)]
    )

    number_deleted = await batch_delete(
        session, db.Event, db.Event.occurred <= now("UTC"), batch_size=3
    )

    assert number_deleted == 10
    queried_events, event_count, _ = await query_events(session, filter=EventFilter())
    assert event_count == 0
    assert len(queried_events) == 0
