from typing import Any, Dict, Generator, List, Sequence

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.events.filters import EventFilter, EventOrder
from prefect.logging.loggers import get_logger
from prefect.server.database.dependencies import db_injector, provide_database_interface
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.database.orm_models import ORMEvent
from prefect.server.events.schemas.events import ReceivedEvent
from prefect.server.utilities.database import get_dialect
from prefect.settings import PREFECT_API_DATABASE_CONNECTION_URL

logger = get_logger(__name__)


@db_injector
def build_distinct_queries(
    db: PrefectDBInterface,
    events_filter: EventFilter,
) -> List[sa.Column[ORMEvent]]:
    distinct_fields: List[str] = []
    if events_filter.resource and events_filter.resource.distinct:
        distinct_fields.append("resource_id")
    if distinct_fields:
        return [getattr(db.Event, field) for field in distinct_fields]
    return []


@db_injector
async def read_events(
    db: PrefectDBInterface,
    session: AsyncSession,
    events_filter: EventFilter,
    limit: int | None = None,
    offset: int | None = None,
) -> Sequence[ORMEvent]:
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
        aliased_table = sa.aliased(db.Event, subquery)

        # Create the final query from the subquery, filtering to get only rows with row_number = 1
        select_events_query = sa.select(aliased_table).where(subquery.c.row_number == 1)

        # Order by the occurred timestamp
        select_events_query = select_events_query.order_by(order(subquery.c.occurred))

    else:
        # If no distinct fields are provided, create a query for all events
        select_events_query = sa.select(db.Event).where(
            sa.and_(*events_filter.build_where_clauses(db))
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


@db_injector
async def write_events(
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
    if dialect == "postgresql":
        return 32_767
    else:
        return 999


# Events require a fixed number of parameters per event,...
NUMBER_OF_EVENT_FIELDS = provide_database_interface().Event.__table__.columns.__len__()

# ...plus a variable number of parameters per resource...
NUMBER_OF_RESOURCE_FIELDS = (
    provide_database_interface().EventResource.__table__.columns.__len__()
)


def _in_safe_batches(
    events: List[ReceivedEvent],
) -> Generator[List[ReceivedEvent], None, None]:
    batch = []
    parameters_used = 0
    max_query_parameters = get_max_query_parameters()

    for event in events:
        these_parameters = NUMBER_OF_EVENT_FIELDS + (
            len(event.involved_resources) * NUMBER_OF_RESOURCE_FIELDS
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
