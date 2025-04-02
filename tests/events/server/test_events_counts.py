import datetime
import math
from datetime import timedelta
from typing import AsyncGenerator, Dict, List, Tuple
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from whenever import ZonedDateTime

from prefect.server.events.counting import PIVOT_DATETIME, Countable, TimeUnit
from prefect.server.events.filters import (
    EventFilter,
    EventOccurredFilter,
)
from prefect.server.events.schemas.events import EventCount, ReceivedEvent
from prefect.server.events.storage.database import (
    count_events,
    write_events,
)
from prefect.types._datetime import Date, DateTime, Duration, end_of_period, now

# Note: the counts in this module are sensitive to the number and shape of events
# we produce in conftest.py and may need to be adjusted if we make changes.


@pytest.fixture(scope="module")
def known_dates() -> Tuple[Date, ...]:
    dates = [
        datetime.date.today() - datetime.timedelta(days=days_ago)
        for days_ago in [5, 4, 3, 2, 1]
    ]
    return tuple(dates)


@pytest.fixture(scope="module")
def known_times(
    known_dates: Tuple[Date, ...],
) -> Tuple[datetime.datetime, datetime.datetime]:
    start, end = known_dates[0], known_dates[-1]
    return (
        ZonedDateTime(start.year, start.month, start.day, tz="UTC").py_datetime(),
        ZonedDateTime(
            end.year, end.month, end.day, 23, 59, 59, nanosecond=999999999, tz="UTC"
        ).py_datetime(),
    )


@pytest.fixture(scope="module")
def all_events(known_dates: Tuple[Date, ...]) -> List[ReceivedEvent]:
    event_options = [
        "things.happened",
        "things.happened",
        "things.happened",
        "things.didn't",
        "things.didn't",
        "other.stuff",
        "nope.not.this",
    ]

    resource_options: List[Dict[str, str]] = [
        {
            "prefect.resource.id": "foo.1",
            "prefect.resource.name": "Foo To You",
            "hello": "world",
        },
        {
            "prefect.resource.id": "foo.2",
            "prefect.resource.name": "Foo To You Two",
            "hello": "world",
        },
        {
            "prefect.resource.id": "foo.3",
            "goodbye": "moon",
        },
    ]
    related_options: List[List[Dict[str, str]]] = [
        [],
        [
            {
                "prefect.resource.id": "foo.1",
                "prefect.resource.role": "thing",
            },
            {
                "prefect.resource.id": "foo.2",
                "prefect.resource.role": "another-thing",
            },
            {
                "prefect.resource.id": "foo.3",
                "prefect.resource.role": "the-other-thing",
            },
            {
                "prefect.resource.id": "related.4",
                "prefect.resource.role": "that-other-thing",
                "goodbye": "moon",
            },
        ],
        [
            {
                "prefect.resource.id": "foo.1",
                "prefect.resource.role": "thing",
                "hello": "world",
                "another": "label",
            },
            {
                "prefect.resource.id": "foo.2",
                "prefect.resource.role": "another-thing",
                "hello": "world",
            },
            {
                "prefect.resource.id": "foo.3",
                "prefect.resource.role": "that-other-thing",
                "goodbye": "moon",
            },
            {
                "prefect.resource.id": "related.4",
                "prefect.resource.role": "that-other-thing",
                "goodbye": "moon",
            },
            {
                "prefect.resource.id": "related.5",
                "prefect.resource.role": "that-other-thing",
                "goodbye": "moon",
            },
        ],
    ]

    events: List[ReceivedEvent] = []
    for date in known_dates:
        for i in range(20):
            occurred = DateTime(
                date.year,
                date.month,
                date.day,
                hour=i,
                minute=i * 2,
                second=i * 2,
                tzinfo=ZoneInfo("UTC"),
            )

            related = list(related_options[i % len(related_options)])

            events.append(
                ReceivedEvent(
                    occurred=occurred,
                    event=event_options[i % len(event_options)],
                    resource=resource_options[i % len(resource_options)],
                    related=related,
                    payload={"hello": "world"},
                    id=uuid4(),
                    received=occurred + timedelta(seconds=0.5),
                )
            )
    return events


@pytest.fixture
async def events_query_session(
    all_events: List[ReceivedEvent],
    session: AsyncSession,
) -> AsyncGenerator[AsyncSession, None]:
    """Opens an appropriate session for the backend, seeds it with the
    test events, and returns it for use in tests"""
    await write_events(session, all_events)
    yield session


def datetime_from_date(
    date: Date, hour: int = 0, minute: int = 0, second: int = 0, microsecond: int = 0
) -> datetime.datetime:
    return ZonedDateTime(
        date.year,
        date.month,
        date.day,
        hour=hour,
        minute=minute,
        second=second,
        nanosecond=microsecond * 1000,
        tz="UTC",
    ).py_datetime()


async def test_counting_by_day_legacy(
    events_query_session: AsyncSession,
    known_dates: Tuple[Date, ...],
    known_times: Tuple[DateTime, DateTime],
):
    counts = await count_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=EventOccurredFilter(
                since=known_times[0],
                until=known_times[1],
            ),
        ),
        countable=Countable.day,
        time_unit=TimeUnit.day,
        time_interval=1.0,
    )

    assert counts == [
        EventCount(
            value="0",
            label=f"{known_dates[0].isoformat()}T00:00:00+00:00",
            count=20,
            start_time=datetime_from_date(known_dates[0]),
            end_time=datetime_from_date(known_dates[0], 23, 59, 59, 999999),
        ),
        EventCount(
            value="1",
            label=f"{known_dates[1].isoformat()}T00:00:00+00:00",
            count=20,
            start_time=datetime_from_date(known_dates[1]),
            end_time=datetime_from_date(known_dates[1], 23, 59, 59, 999999),
        ),
        EventCount(
            value="2",
            label=f"{known_dates[2].isoformat()}T00:00:00+00:00",
            count=20,
            start_time=datetime_from_date(known_dates[2]),
            end_time=datetime_from_date(known_dates[2], 23, 59, 59, 999999),
        ),
        EventCount(
            value="3",
            label=f"{known_dates[3].isoformat()}T00:00:00+00:00",
            count=20,
            start_time=datetime_from_date(known_dates[3]),
            end_time=datetime_from_date(known_dates[3], 23, 59, 59, 999999),
        ),
        EventCount(
            value="4",
            label=f"{known_dates[4].isoformat()}T00:00:00+00:00",
            count=20,
            start_time=datetime_from_date(known_dates[4]),
            end_time=datetime_from_date(known_dates[4], 23, 59, 59, 999999),
        ),
    ]


async def test_counting_by_time_no_future_events_backfilled(
    events_query_session: AsyncSession,
    known_dates: Tuple[Date, ...],
    known_times: Tuple[DateTime, DateTime],
):
    counts = await count_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=EventOccurredFilter(
                since=known_times[0],
                until=known_times[1] + datetime.timedelta(days=1),
            ),
        ),
        countable=Countable.day,
        time_unit=TimeUnit.day,
        time_interval=1.0,
    )

    assert counts == [
        EventCount(
            value="0",
            label=f"{known_dates[0].isoformat()}T00:00:00+00:00",
            count=20,
            start_time=datetime_from_date(known_dates[0]),
            end_time=datetime_from_date(known_dates[0], 23, 59, 59, 999999),
        ),
        EventCount(
            value="1",
            label=f"{known_dates[1].isoformat()}T00:00:00+00:00",
            count=20,
            start_time=datetime_from_date(known_dates[1]),
            end_time=datetime_from_date(known_dates[1], 23, 59, 59, 999999),
        ),
        EventCount(
            value="2",
            label=f"{known_dates[2].isoformat()}T00:00:00+00:00",
            count=20,
            start_time=datetime_from_date(known_dates[2]),
            end_time=datetime_from_date(known_dates[2], 23, 59, 59, 999999),
        ),
        EventCount(
            value="3",
            label=f"{known_dates[3].isoformat()}T00:00:00+00:00",
            count=20,
            start_time=datetime_from_date(known_dates[3]),
            end_time=datetime_from_date(known_dates[3], 23, 59, 59, 999999),
        ),
        EventCount(
            value="4",
            label=f"{known_dates[4].isoformat()}T00:00:00+00:00",
            count=20,
            start_time=datetime_from_date(known_dates[4]),
            end_time=datetime_from_date(known_dates[4], 23, 59, 59, 999999),
        ),
        EventCount(
            value="5",
            label=f"{(known_dates[4] + datetime.timedelta(days=1)).isoformat()}T00:00:00+00:00",
            count=0,
            start_time=datetime_from_date(known_dates[4] + datetime.timedelta(days=1)),
            end_time=datetime_from_date(
                known_dates[4] + datetime.timedelta(days=1), 23, 59, 59, 999999
            ),
        ),
    ]


async def test_counting_by_time_per_hour(
    events_query_session: AsyncSession,
    known_dates: Tuple[Date, ...],
    known_times: Tuple[DateTime, DateTime],
):
    counts = await count_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=EventOccurredFilter(
                since=known_times[0],
                until=known_times[1],
            ),
        ),
        countable=Countable.time,
        time_unit=TimeUnit.hour,
        time_interval=1.0,
    )

    expected = {}
    for date in known_dates:
        for i in range(20):
            start_time = datetime_from_date(date, hour=i)
            index = int(
                (start_time - datetime_from_date(known_dates[0])).total_seconds() / 3600
            )
            expected[index] = EventCount(
                value=str(index),
                label=start_time.isoformat(),
                count=1,
                start_time=start_time,
                end_time=datetime_from_date(date, i, 59, 59, 999999),
            )

    # When counting events by time we backfill missing data so that the result
    # contains all of the possible spans in the given time period. `expected`
    # is only those spans that actually have events in them. So here we assert
    # about the length of the result and then assert that the result contains
    # all of the expected spans and assert that the count is 0 for the others.

    assert len(counts) == math.ceil(
        (known_times[1] - known_times[0]).total_seconds() / 3600
    )
    assert len(expected) == 100

    for i, count in enumerate(counts):
        assert isinstance(count, EventCount)
        if i in expected:
            assert count == expected[i]
        else:
            assert count.count == 0


async def test_counting_by_time_per_minute(
    events_query_session: AsyncSession,
    known_dates: Tuple[Date, ...],
    known_times: Tuple[DateTime, DateTime],
):
    counts = await count_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=EventOccurredFilter(
                since=known_times[0],
                until=known_times[0] + timedelta(minutes=600),
            ),
        ),
        countable=Countable.time,
        time_unit=TimeUnit.minute,
        time_interval=1.0,
    )

    expected = {}
    for date in known_dates:
        for i in range(20):
            start_time = datetime_from_date(date, hour=i, minute=i * 2)
            index = int(
                (start_time - datetime_from_date(known_dates[0])).total_seconds() / 60
            )
            expected[index] = EventCount(
                value=str(index),
                label=start_time.isoformat(),
                count=1,
                start_time=start_time,
                end_time=datetime_from_date(date, i, i * 2, 59, 999999),
            )

    # When counting events by time we backfill missing data so that the result
    # contains all of the possible spans in the given time period. `expected`
    # is only those spans that actually have events in them. So here we assert
    # about the length of the result and then assert that the result contains
    # all of the expected spans and assert that the count is 0 for the others.

    assert len(counts) == 600
    assert len(expected) == 100

    for i, count in enumerate(counts):
        assert isinstance(count, EventCount)
        if i in expected:
            assert count == expected[i]
        else:
            assert count.count == 0


async def test_counting_by_time_per_second(
    events_query_session: AsyncSession,
    known_dates: Tuple[Date, ...],
    known_times: Tuple[DateTime, DateTime],
):
    counts = await count_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=EventOccurredFilter(
                since=known_times[0],
                until=known_times[0] + datetime.timedelta(seconds=600),
            ),
        ),
        countable=Countable.time,
        time_unit=TimeUnit.second,
        time_interval=1.0,
    )

    expected = {}
    for date in known_dates:
        for i in range(20):
            start_time = datetime_from_date(date, hour=i, minute=i * 2, second=i * 2)
            index = int(
                (start_time - datetime_from_date(known_dates[0])).total_seconds()
            )
            expected[index] = EventCount(
                value=str(index),
                label=start_time.isoformat(),
                count=1,
                start_time=start_time,
                end_time=datetime_from_date(date, i, i * 2, i * 2, 999999),
            )

    # When counting events by time we backfill missing data so that the result
    # contains all of the possible spans in the given time period. `expected`
    # is only those spans that actually have events in them. So here we assert
    # about the length of the result and then assert that the result contains
    # all of the expected spans and assert that the count is 0 for the others.

    assert len(counts) == 600
    assert len(expected) == 100

    for i, count in enumerate(counts):
        assert isinstance(count, EventCount)
        if i in expected:
            assert count == expected[i]
        else:
            assert count.count == 0


async def test_counting_by_time_large_interval(
    events_query_session: AsyncSession,
    known_dates: Tuple[Date, ...],
    known_times: Tuple[DateTime, DateTime],
):
    since = datetime_from_date(known_dates[0], 20, 18, 23)
    until = datetime_from_date(known_dates[1], 4, 18, 23)
    counts = await count_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=EventOccurredFilter(
                since=since,
                until=until,
            ),
        ),
        countable=Countable.time,
        time_unit=TimeUnit.second,
        time_interval=1800.0,
    )

    expected = {
        8: EventCount(
            value="8",
            label=datetime_from_date(known_dates[1], 0, 0, 0).isoformat(),
            count=1,
            start_time=datetime_from_date(known_dates[1], 0, 0, 0),
            end_time=datetime_from_date(known_dates[1], 0, 29, 59, 999999),
        ),
        10: EventCount(
            value="10",
            label=datetime_from_date(known_dates[1], 1, 0, 0).isoformat(),
            count=1,
            start_time=datetime_from_date(known_dates[1], 1, 0, 0),
            end_time=datetime_from_date(known_dates[1], 1, 29, 59, 999999),
        ),
        12: EventCount(
            value="12",
            label=datetime_from_date(known_dates[1], 2, 0, 0).isoformat(),
            count=1,
            start_time=datetime_from_date(known_dates[1], 2, 0, 0),
            end_time=datetime_from_date(known_dates[1], 2, 29, 59, 999999),
        ),
        14: EventCount(
            value="14",
            label=datetime_from_date(known_dates[1], 3, 0, 0).isoformat(),
            count=1,
            start_time=datetime_from_date(known_dates[1], 3, 0, 0),
            end_time=datetime_from_date(known_dates[1], 3, 29, 59, 999999),
        ),
        16: EventCount(
            value="16",
            label=datetime_from_date(known_dates[1], 4, 0, 0).isoformat(),
            count=1,
            start_time=datetime_from_date(known_dates[1], 4, 0, 0),
            end_time=datetime_from_date(known_dates[1], 4, 29, 59, 999999),
        ),
    }

    # When counting events by time we backfill missing data so that the result
    # contains all of the possible spans in the given time period. `expected`
    # is only those spans that actually have events in them. So here we assert
    # about the length of the result and then assert that the result contains
    # all of the expected spans and assert that the count is 0 for the others.

    assert len(counts) == (until - since).total_seconds() / 1800 + 1
    assert len(expected) == 5

    for i, count in enumerate(counts):
        assert isinstance(count, EventCount)
        if i in expected:
            assert count == expected[i]
        else:
            assert count.count == 0


async def test_buckets_are_stable(
    events_query_session: AsyncSession,
    known_dates: Tuple[Date, ...],
):
    since = datetime_from_date(known_dates[0], 0, 18, 23)
    until = datetime_from_date(known_dates[0], 0, 48, 23)

    first = await count_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=EventOccurredFilter(
                since=since,
                until=until,
            ),
        ),
        countable=Countable.time,
        time_unit=TimeUnit.second,
        time_interval=2.5,
    )

    second = await count_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=EventOccurredFilter(
                since=since + timedelta(seconds=9),
                until=until + timedelta(seconds=9),
            ),
        ),
        countable=Countable.time,
        time_unit=TimeUnit.second,
        time_interval=2.5,
    )

    # The `value` of each `EventCount` is the index of that bucket within the
    # given API response. So while the start/end times of the counts in `first`
    # and `second` should align, the `value` will be different.
    #
    # Also since `second` starts 9 seconds later than `first`, the first 3
    # buckets in `first` will not appear in `second` and the last 3 buckets in
    # `second` will not appear in `first`.

    assert len(first) == len(second)

    for i, count in enumerate(first[3:]):
        assert int(second[i].value) == int(count.value) - 3
        assert second[i].count == count.count
        assert second[i].label == count.label
        assert second[i].start_time == count.start_time
        assert second[i].end_time == count.end_time


async def test_counting_by_time_per_day(
    events_query_session: AsyncSession,
    known_dates: Tuple[Date, ...],
    known_times: Tuple[DateTime, DateTime],
):
    counts = await count_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=EventOccurredFilter(
                since=known_times[0],
                until=known_times[1],
            ),
        ),
        countable=Countable.time,
        time_unit=TimeUnit.day,
        time_interval=1.0,
    )

    assert counts == [
        EventCount(
            value="0",
            label=f"{known_dates[0].isoformat()}T00:00:00+00:00",
            count=20,
            start_time=datetime_from_date(known_dates[0]),
            end_time=datetime_from_date(known_dates[0], 23, 59, 59, 999999),
        ),
        EventCount(
            value="1",
            label=f"{known_dates[1].isoformat()}T00:00:00+00:00",
            count=20,
            start_time=datetime_from_date(known_dates[1]),
            end_time=datetime_from_date(known_dates[1], 23, 59, 59, 999999),
        ),
        EventCount(
            value="2",
            label=f"{known_dates[2].isoformat()}T00:00:00+00:00",
            count=20,
            start_time=datetime_from_date(known_dates[2]),
            end_time=datetime_from_date(known_dates[2], 23, 59, 59, 999999),
        ),
        EventCount(
            value="3",
            label=f"{known_dates[3].isoformat()}T00:00:00+00:00",
            count=20,
            start_time=datetime_from_date(known_dates[3]),
            end_time=datetime_from_date(known_dates[3], 23, 59, 59, 999999),
        ),
        EventCount(
            value="4",
            label=f"{known_dates[4].isoformat()}T00:00:00+00:00",
            count=20,
            start_time=datetime_from_date(known_dates[4]),
            end_time=datetime_from_date(known_dates[4], 23, 59, 59, 999999),
        ),
    ]


async def test_counting_by_time_per_two_days(
    events_query_session: AsyncSession,
    known_dates: Tuple[Date, ...],
    known_times: Tuple[DateTime, DateTime],
):
    counts = await count_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=EventOccurredFilter(
                since=known_times[0],
                until=known_times[1],
            ),
        ),
        countable=Countable.time,
        time_unit=TimeUnit.day,
        time_interval=2.0,
    )

    # Since we compute the count buckets based on a fixed anchor point this
    # this test will either have the first bucket with 40 events and the last
    # bucket with 20 or the last the first bucket will have 20 events and the
    # last 40 depending on which day it runs.

    two_days = Duration(days=2)
    first_span_index = math.floor(
        (datetime_from_date(known_dates[0]) - PIVOT_DATETIME) / two_days
    )
    starting_span = PIVOT_DATETIME + two_days * first_span_index

    if known_dates[0] == starting_span.date():
        expected = [
            EventCount(
                value="0",
                label=datetime_from_date(known_dates[0]).isoformat(),
                count=40,
                start_time=datetime_from_date(known_dates[0]),
                end_time=datetime_from_date(known_dates[1], 23, 59, 59, 999999),
            ),
            EventCount(
                value="1",
                label=datetime_from_date(known_dates[2]).isoformat(),
                count=40,
                start_time=datetime_from_date(known_dates[2]),
                end_time=datetime_from_date(known_dates[3], 23, 59, 59, 999999),
            ),
            EventCount(
                value="2",
                label=datetime_from_date(known_dates[4]).isoformat(),
                count=20,
                start_time=datetime_from_date(known_dates[4]),
                end_time=datetime_from_date(
                    known_dates[4] + timedelta(days=1), 23, 59, 59, 999999
                ),
            ),
        ]
    else:
        expected = [
            EventCount(
                value="0",
                label=datetime_from_date(
                    known_dates[0] - datetime.timedelta(days=1)
                ).isoformat(),
                count=20,
                start_time=datetime_from_date(
                    known_dates[0] - datetime.timedelta(days=1)
                ),
                end_time=datetime_from_date(known_dates[0], 23, 59, 59, 999999),
            ),
            EventCount(
                value="1",
                label=datetime_from_date(known_dates[1]).isoformat(),
                count=40,
                start_time=datetime_from_date(known_dates[1]),
                end_time=datetime_from_date(known_dates[2], 23, 59, 59, 999999),
            ),
            EventCount(
                value="2",
                label=datetime_from_date(known_dates[3]).isoformat(),
                count=40,
                start_time=datetime_from_date(known_dates[3]),
                end_time=datetime_from_date(known_dates[4], 23, 59, 59, 999999),
            ),
        ]

    assert counts == expected


async def test_counting_by_time_per_week(
    events_query_session: AsyncSession,
    known_dates: Tuple[Date, ...],
    known_times: Tuple[DateTime, DateTime],
):
    counts = await count_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=EventOccurredFilter(
                since=known_times[0],
                until=known_times[1],
            ),
        ),
        countable=Countable.time,
        time_unit=TimeUnit.week,
        time_interval=1.0,
    )

    # Since we compute weeks based on the week starting on Monday it's possible
    # for this test to either encounter a single week or two weeks depending
    # on what day of the week it's run.
    counts_by_week: dict[datetime.datetime, int] = {}
    for date in known_dates:
        start_day = datetime.datetime(
            year=date.year, month=date.month, day=date.day, tzinfo=ZoneInfo("UTC")
        )
        # go to the start of the week
        start_day = start_day - datetime.timedelta(days=start_day.weekday())
        if start_day not in counts_by_week:
            counts_by_week[start_day] = 0
        counts_by_week[start_day] += 20  # We generate 20 events per known date

    expected: list[EventCount] = []
    for i, (date, count) in enumerate(counts_by_week.items()):
        expected.append(
            EventCount(
                value=str(i),
                label=date.isoformat(),
                count=count,
                start_time=date,
                end_time=end_of_period(date, "week"),
            )
        )

    assert counts == expected


async def test_counting_by_event(
    events_query_session: AsyncSession,
    known_times: Tuple[DateTime, DateTime],
    known_dates: List[Date],
):
    counts = await count_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=EventOccurredFilter(
                since=known_times[0],
                until=known_times[1],
            ),
        ),
        countable=Countable.event,
        time_unit=TimeUnit.day,
        time_interval=1.0,
    )

    assert counts == [
        EventCount(
            value="things.happened",
            label="things.happened",
            count=45,
            start_time=datetime_from_date(known_dates[0], hour=0, minute=0, second=0),
            end_time=datetime_from_date(known_dates[4], hour=16, minute=32, second=32),
        ),
        EventCount(
            value="things.didn't",
            label="things.didn't",
            count=30,
            start_time=datetime_from_date(known_dates[0], hour=3, minute=6, second=6),
            end_time=datetime_from_date(known_dates[4], hour=18, minute=36, second=36),
        ),
        EventCount(
            value="other.stuff",
            label="other.stuff",
            count=15,
            start_time=datetime_from_date(known_dates[0], hour=5, minute=10, second=10),
            end_time=datetime_from_date(known_dates[4], hour=19, minute=38, second=38),
        ),
        EventCount(
            value="nope.not.this",
            label="nope.not.this",
            count=10,
            start_time=datetime_from_date(known_dates[0], hour=6, minute=12, second=12),
            end_time=datetime_from_date(known_dates[4], hour=13, minute=26, second=26),
        ),
    ]


async def test_counting_by_resource(
    events_query_session: AsyncSession,
    known_times: Tuple[DateTime, DateTime],
    known_dates: List[Date],
):
    counts = await count_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=EventOccurredFilter(
                since=known_times[0],
                until=known_times[1],
            ),
        ),
        countable=Countable.resource,
        time_unit=TimeUnit.day,
        time_interval=1.0,
    )

    assert counts == [
        EventCount(
            value="foo.1",
            label="Foo To You",
            count=35,
            start_time=datetime_from_date(known_dates[0]),
            end_time=datetime_from_date(known_dates[4], hour=18, minute=36, second=36),
        ),
        EventCount(
            value="foo.2",
            label="Foo To You Two",
            count=35,
            start_time=datetime_from_date(known_dates[0], hour=1, minute=2, second=2),
            end_time=datetime_from_date(known_dates[4], hour=19, minute=38, second=38),
        ),
        EventCount(
            value="foo.3",
            label="foo.3",
            count=30,
            start_time=datetime_from_date(known_dates[0], hour=2, minute=4, second=4),
            end_time=datetime_from_date(known_dates[4], hour=17, minute=34, second=34),
        ),
    ]


async def test_counting_by_time_must_interval_be_larger_than_one_hundredth(
    events_query_session: AsyncSession,
    known_dates: Tuple[Date, ...],
    known_times: Tuple[DateTime, DateTime],
):
    with pytest.raises(ValueError, match=r"0\.01"):
        await count_events(
            session=events_query_session,
            filter=EventFilter(
                occurred=EventOccurredFilter(
                    since=known_times[0],
                    until=known_times[1],
                ),
            ),
            countable=Countable.time,
            time_unit=TimeUnit.second,
            time_interval=0.009,
        )


async def test_counting_by_time_must_result_in_reasonable_number_of_buckets(
    events_query_session: AsyncSession,
):
    with pytest.raises(ValueError, match=r"would create 60480001 buckets"):
        await count_events(
            session=events_query_session,
            filter=EventFilter(
                occurred=EventOccurredFilter(
                    since=now("UTC") - datetime.timedelta(days=7),
                    until=now("UTC"),
                ),
            ),
            countable=Countable.time,
            time_unit=TimeUnit.second,
            time_interval=0.01,
        )
