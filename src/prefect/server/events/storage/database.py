from typing import TYPE_CHECKING, Any, Dict, Generator, List, Optional, Sequence, Tuple

import pydantic
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from prefect.logging.loggers import get_logger
from prefect.server.database.dependencies import db_injector, provide_database_interface
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.events.counting import Countable, TimeUnit
from prefect.server.events.filters import EventFilter, EventOrder
from prefect.server.events.schemas.events import EventCount, ReceivedEvent
from prefect.server.events.storage import (
    INTERACTIVE_PAGE_SIZE,
    from_page_token,
    process_time_based_counts,
    to_page_token,
)
from prefect.server.utilities.database import get_dialect
from prefect.settings import PREFECT_API_DATABASE_CONNECTION_URL

if TYPE_CHECKING:
    from prefect.server.database.orm_models import ORMEvent

logger = get_logger(__name__)


@db_injector
def build_distinct_queries(
    db: PrefectDBInterface,
    events_filter: EventFilter,
) -> List[sa.Column["ORMEvent"]]:
    distinct_fields: List[str] = []
    if events_filter.resource and events_filter.resource.distinct:
        distinct_fields.append("resource_id")
    if distinct_fields:
        return [getattr(db.Event, field) for field in distinct_fields]
    return []


async def query_events(
    session: AsyncSession,
    filter: EventFilter,
    page_size: int = INTERACTIVE_PAGE_SIZE,
) -> Tuple[List[ReceivedEvent], int, Optional[str]]:
    assert isinstance(session, AsyncSession)
    count = await raw_count_events(session, filter)
    page = await read_events(session, filter, limit=page_size, offset=0)
    events = [ReceivedEvent.model_validate(e, from_attributes=True) for e in page]
    page_token = to_page_token(filter, count, page_size, 0)
    return events, count, page_token


async def query_next_page(
    session: AsyncSession,
    page_token: str,
) -> Tuple[List[ReceivedEvent], int, Optional[str]]:
    assert isinstance(session, AsyncSession)
    filter, count, page_size, offset = from_page_token(page_token)
    page = await read_events(session, filter, limit=page_size, offset=offset)
    events = [ReceivedEvent.model_validate(e, from_attributes=True) for e in page]
    next_token = to_page_token(filter, count, page_size, offset)
    return events, count, next_token


async def count_events(
    session: AsyncSession,
    filter: EventFilter,
    countable: Countable,
    time_unit: TimeUnit,
    time_interval: float,
) -> List[EventCount]:
    time_unit.validate_buckets(
        filter.occurred.since, filter.occurred.until, time_interval
    )
    results = await session.execute(
        countable.get_database_query(filter, time_unit, time_interval)
    )

    counts = pydantic.TypeAdapter(List[EventCount]).validate_python(
        results.mappings().all()
    )

    if countable in (Countable.day, Countable.time):
        counts = process_time_based_counts(filter, time_unit, time_interval, counts)

    return counts


@db_injector
async def raw_count_events(
    db: PrefectDBInterface,
    session: AsyncSession,
    events_filter: EventFilter,
) -> int:
    """
    Count events from the database with the given filter.

    Only returns the count and does not return any addition metadata. For additional
    metadata, use `count_events`.

    Args:
        session: a database session
        events_filter: filter criteria for events

    Returns:
        The count of events in the database that match the filter criteria.
    """
    # start with sa.func.count(), don't sa.select
    select_events_query = sa.select(sa.func.count()).select_from(db.Event)

    if distinct_fields := build_distinct_queries(events_filter):
        select_events_query = sa.select(
            sa.func.count(sa.distinct(*distinct_fields))
        ).select_from(db.Event)

    select_events_query_result = await session.execute(
        select_events_query.where(sa.and_(*events_filter.build_where_clauses()))
    )
    return select_events_query_result.scalar() or 0


@db_injector
async def read_events(
    db: PrefectDBInterface,
    session: AsyncSession,
    events_filter: EventFilter,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> Sequence["ORMEvent"]:
    """
    Read events from the Postgres database.

    Args:
        session: a Postgres events session.
        filter: filter criteria for events.
        limit: limit for the query.
        offset: offset for the query.

    Returns:
        A list of events ORM objects.
    """
    # Always order by occurred timestamp, with placeholder for order direction
    order = sa.desc if events_filter.order == EventOrder.DESC else sa.asc

    # Check if distinct fields are provided
    if distinct_fields := build_distinct_queries(events_filter):
        # Define window function
        window_function = (
            sa.func.row_number()
            .over(partition_by=distinct_fields, order_by=order(db.Event.occurred))
            .label("row_number")
        )
        # Create a subquery with the window function
        subquery = (
            sa.select(db.Event, window_function)
            .where(
                sa.and_(
                    *events_filter.build_where_clauses()
                )  # Ensure the same filters are applied here
            )
            .subquery()
        )

        # Alias the subquery for easier column references
        aliased_table = aliased(db.Event, subquery)

        # Create the final query from the subquery, filtering to get only rows with row_number = 1
        select_events_query = sa.select(aliased_table).where(subquery.c.row_number == 1)

        # Order by the occurred timestamp
        select_events_query = select_events_query.order_by(order(subquery.c.occurred))

    else:
        # If no distinct fields are provided, create a query for all events
        select_events_query = sa.select(db.Event).where(
            sa.and_(*events_filter.build_where_clauses())
        )
        # Order by the occurred timestamp
        select_events_query = select_events_query.order_by(order(db.Event.occurred))

    if limit is not None:
        limit = max(0, min(limit, events_filter.logical_limit))
        select_events_query = select_events_query.limit(limit=limit)
    if offset is not None:
        select_events_query = select_events_query.offset(offset=offset)

    logger.debug("Running PostgreSQL query: %s", select_events_query)

    select_events_query_result = await session.execute(select_events_query)
    return select_events_query_result.scalars().unique().all()


async def write_events(session: AsyncSession, events: List[ReceivedEvent]) -> None:
    """
    Write events to the database.

    Args:
        session: a database session
        events: the events to insert
    """
    if events:
        dialect = get_dialect(PREFECT_API_DATABASE_CONNECTION_URL.value())
        if dialect.name == "postgresql":
            await _write_postgres_events(session, events)
        else:
            await _write_sqlite_events(session, events)


@db_injector
async def _write_sqlite_events(
    db: PrefectDBInterface, session: AsyncSession, events: List[ReceivedEvent]
) -> None:
    """
    Write events to the SQLite database.

    SQLite does not support the `RETURNING` clause with SQLAlchemy < 2, so we need to
    check for existing events before inserting them.

    Args:
        session: a SQLite events session
        events: the events to insert
    """
    for batch in _in_safe_batches(events):
        event_ids = {event.id for event in batch}
        result = await session.scalars(
            sa.select(db.Event.id).where(db.Event.id.in_(event_ids))
        )
        existing_event_ids = list(result.all())
        events_to_insert = [
            event for event in batch if event.id not in existing_event_ids
        ]
        event_rows = [event.as_database_row() for event in events_to_insert]
        await session.execute(db.insert(db.Event).values(event_rows))

        resource_rows: List[Dict[str, Any]] = []
        for event in events_to_insert:
            resource_rows.extend(event.as_database_resource_rows())

        if not resource_rows:
            continue

        await session.execute(db.insert(db.EventResource).values(resource_rows))


@db_injector
async def _write_postgres_events(
    db: PrefectDBInterface, session: AsyncSession, events: List[ReceivedEvent]
) -> None:
    """
    Write events to the Postgres database.

    Args:
        session: a Postgres events session
        events: the events to insert
    """
    for batch in _in_safe_batches(events):
        event_rows = [event.as_database_row() for event in batch]
        result = await session.scalars(
            db.insert(db.Event)
            .on_conflict_do_nothing()
            .returning(db.Event.id)
            .values(event_rows)
        )
        inserted_event_ids = set(result.all())

        resource_rows: List[Dict[str, Any]] = []
        for event in batch:
            if event.id not in inserted_event_ids:
                # if the event wasn't inserted, this means the event was a duplicate, so
                # we will skip adding its related resources, as they would have been
                # inserted already
                continue
            resource_rows.extend(event.as_database_resource_rows())

        if not resource_rows:
            continue

        await session.execute(db.insert(db.EventResource).values(resource_rows))


def get_max_query_parameters() -> int:
    dialect = get_dialect(PREFECT_API_DATABASE_CONNECTION_URL.value())
    if dialect.name == "postgresql":
        return 32_767
    else:
        return 999


# Events require a fixed number of parameters per event,...
def get_number_of_event_fields():
    return provide_database_interface().Event.__table__.columns.__len__()


# ...plus a variable number of parameters per resource...
def get_number_of_resource_fields():
    return provide_database_interface().EventResource.__table__.columns.__len__()


def _in_safe_batches(
    events: List[ReceivedEvent],
) -> Generator[List[ReceivedEvent], None, None]:
    batch = []
    parameters_used = 0
    max_query_parameters = get_max_query_parameters()
    number_of_event_fields = get_number_of_event_fields()
    number_of_resource_fields = get_number_of_resource_fields()

    for event in events:
        these_parameters = number_of_event_fields + (
            len(event.involved_resources) * number_of_resource_fields
        )
        if parameters_used + these_parameters < max_query_parameters:
            batch.append(event)
            parameters_used += these_parameters
        else:
            yield batch
            batch = [event]
            parameters_used = 0

    if batch:
        yield batch
