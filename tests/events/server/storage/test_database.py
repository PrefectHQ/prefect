import datetime
from datetime import timezone
from typing import List
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.database import PrefectDBInterface
from prefect.server.events.filters import (
    EventFilter,
    EventIDFilter,
    EventOccurredFilter,
    EventResourceFilter,
)
from prefect.server.events.schemas.events import ReceivedEvent
from prefect.server.events.storage.database import (
    get_max_query_parameters,
    get_number_of_event_fields,
    get_number_of_resource_fields,
    read_events,
    write_events,
)
from prefect.types._datetime import DateTime, now


@pytest.fixture
def event() -> ReceivedEvent:
    return ReceivedEvent(
        occurred=now("UTC"),
        event="hello",
        resource={"prefect.resource.id": "my.resource.id"},
        related=[
            {"prefect.resource.id": "related-1", "prefect.resource.role": "role-1"},
            {"prefect.resource.id": "related-2", "prefect.resource.role": "role-1"},
            {"prefect.resource.id": "related-3", "prefect.resource.role": "role-2"},
        ],
        payload={"hello": "world"},
        received=DateTime(2022, 2, 3, 4, 5, 6, 7, timezone.utc),
        id=UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"),
    )


@pytest.fixture
def other_events() -> List[ReceivedEvent]:
    return [
        ReceivedEvent(
            occurred=now("UTC"),
            event="hello",
            resource={"prefect.resource.id": "my.resource.id"},
            related=[
                {
                    "prefect.resource.id": "related-1",
                    "prefect.resource.role": "role-1",
                },
                {
                    "prefect.resource.id": "related-2",
                    "prefect.resource.role": "role-1",
                },
                {
                    "prefect.resource.id": "related-3",
                    "prefect.resource.role": "role-2",
                },
            ],
            payload={"hello": "world"},
            received=DateTime(2022, 2, 3, 4, 5, 6, 7, timezone.utc),
            id=uuid4(),
        )
        for _ in range(1000)
    ]


class TestWriteEvents:
    async def test_write_event(self, session: AsyncSession, event: ReceivedEvent):
        # Write the event
        async with session as session:
            await write_events(session=session, events=[event])
            await session.commit()

        # Read it back
        async with session as session:
            events = await read_events(
                session=session,
                events_filter=EventFilter(
                    id=EventIDFilter(id=[event.id]),
                    occurred=EventOccurredFilter(
                        since=now("UTC") - datetime.timedelta(days=1)
                    ),
                ),
            )
            assert len(events) == 1
            assert events[0].id == event.id

    async def test_write_event_ignores_duplicates(
        self,
        session: AsyncSession,
        db: PrefectDBInterface,
        event: ReceivedEvent,
        other_events: List[ReceivedEvent],
    ):
        assert len(other_events) == 1000
        chunks = (other_events[:500], other_events[500:])

        for chunk in chunks:
            # Include the event twice in the middle of a batch of other events
            events = chunk[:250] + [event] + chunk[250:]
            assert len(events) == 501

            async with session as session:
                await write_events(session=session, events=events)
                await session.commit()

        # Confirm only one event and one set of event_resources was written.  This uses
        # the ORM directly to avoid JOINs, DISTINCTs, or .unique() that might be used
        # by the read_events function and distort the test.
        async with session as session:
            results = await session.execute(
                sa.select(db.Event).where(db.Event.id == event.id)
            )
            assert len(list(results)) == 1

            results = await session.execute(
                sa.select(db.EventResource).where(db.EventResource.event_id == event.id)
            )
            assert len(list(results)) == len(event.related) + 1

    async def test_write_events_writes_in_chunks(
        self,
        session: AsyncSession,
        db: PrefectDBInterface,
        event: ReceivedEvent,
        other_events: List[ReceivedEvent],
    ):
        total_events = len(other_events)
        total_resources = sum(len(e.involved_resources) for e in other_events)

        # Confirm that our test setup is actually testing what we think it it
        assert total_events == 1000
        assert total_resources == 4000

        total_parameters = (total_events * get_number_of_event_fields()) + (
            total_resources * get_number_of_resource_fields()
        )
        assert total_parameters > get_max_query_parameters()

        async with session as session:
            await write_events(session=session, events=other_events)
            await session.commit()

        events_to_check = other_events[0], other_events[250], other_events[-1]

        # Confirm only one event and one set of event_resources was written.  This uses
        # the ORM directly to avoid JOINs, DISTINCTs, or .unique() that might be used
        # by the read_postgres_events function and distort the test.
        async with session as session:
            for event in events_to_check:
                results = await session.execute(
                    sa.select(db.Event).where(db.Event.id == event.id)
                )
                assert len(list(results)) == 1

                results = await session.execute(
                    sa.select(db.EventResource).where(
                        db.EventResource.event_id == event.id
                    )
                )
                assert len(list(results)) == len(event.related) + 1


class TestReadEvents:
    @pytest.fixture
    async def event_1(self, session: AsyncSession) -> ReceivedEvent:
        event = ReceivedEvent(
            occurred=now("UTC"),
            event="hello",
            resource={"prefect.resource.id": "my.resource.id"},
            related=[
                {"prefect.resource.id": "related-1", "prefect.resource.role": "role-1"},
                {"prefect.resource.id": "related-2", "prefect.resource.role": "role-1"},
                {"prefect.resource.id": "related-3", "prefect.resource.role": "role-2"},
            ],
            payload={"hello": "world"},
            received=DateTime(2022, 2, 3, 4, 5, 6, 7, timezone.utc),
            id=UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"),
        )
        async with session as session:
            await write_events(session=session, events=[event])
            await session.commit()
        return event

    @pytest.fixture
    async def event_2(self, session: AsyncSession) -> ReceivedEvent:
        event = ReceivedEvent(
            occurred=now("UTC") - datetime.timedelta(days=2),
            event="hello",
            resource={"prefect.resource.id": "my.resource.id"},
            related=[
                {"prefect.resource.id": "related-1", "prefect.resource.role": "role-1"},
                {"prefect.resource.id": "related-2", "prefect.resource.role": "role-1"},
                {"prefect.resource.id": "related-3", "prefect.resource.role": "role-2"},
            ],
            payload={"hello": "world"},
            received=DateTime(2022, 2, 3, 4, 5, 6, 7, timezone.utc),
            id=uuid4(),
        )
        async with session as session:
            await write_events(session=session, events=[event])
            await session.commit()
        return event

    async def test_read_events(
        self, session: AsyncSession, event_1: ReceivedEvent, event_2: ReceivedEvent
    ):
        async with session as session:
            events = await read_events(
                session=session,
                events_filter=EventFilter(
                    occurred=EventOccurredFilter(
                        since=now("UTC") - datetime.timedelta(days=1)
                    ),
                ),
            )
            assert len(events) == 1
            assert events[0].id == event_1.id

        async with session as session:
            events = await read_events(
                session=session,
                events_filter=EventFilter(
                    occurred=EventOccurredFilter(
                        since=now("UTC") - datetime.timedelta(days=3),
                        until=now("UTC") - datetime.timedelta(days=1),
                    ),
                ),
            )
            assert len(events) == 1
            assert events[0].id == event_2.id

        # Read criteria should apply AND logic
        # Nothing should be returned for this resource
        async with session as session:
            events = await read_events(
                session=session,
                events_filter=EventFilter(
                    resource=EventResourceFilter(id=["prefect.garbage.foo"]),
                    occurred=EventOccurredFilter(
                        since=now("UTC") - datetime.timedelta(days=1)
                    ),
                ),
            )
            assert len(events) == 0
