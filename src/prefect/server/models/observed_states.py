"""Discover states from retained flow and task run transitions."""

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.database import PrefectDBInterface, db_injector
from prefect.server.schemas.observed_states import ObservedState, ObservedStateSort


@db_injector
async def read_observed_states(
    db: PrefectDBInterface,
    session: AsyncSession,
    query: str | None = None,
    order_by: ObservedStateSort = ObservedStateSort.LAST_SEEN_DESC,
    limit: int = 200,
) -> list[ObservedState]:
    """Combine exact state pairs and timestamp bounds from retained run histories."""
    # Group each history before combining them: the union only contains distinct
    # pairs, rather than every retained transition. SQLite uses covering indexes.
    histories = sa.union_all(
        *(
            sa.select(
                state.type.label("state_type"),
                state.name.label("state_name"),
                sa.func.min(state.timestamp).label("first_seen"),
                sa.func.max(state.timestamp).label("last_seen"),
            ).group_by(state.type, state.name)
            for state in (db.FlowRunState, db.TaskRunState)
        )
    ).subquery()
    observed = (
        sa.select(
            sa.cast(histories.c.state_type, sa.String).label("state_type"),
            histories.c.state_name,
            sa.func.min(histories.c.first_seen).label("first_seen"),
            sa.func.max(histories.c.last_seen).label("last_seen"),
        )
        .group_by(histories.c.state_type, histories.c.state_name)
        # Prevent prefix predicates from being pushed into the full history scans.
        # OFFSET works on supported SQLite versions that predate MATERIALIZED CTEs.
        .offset(0)
        .subquery()
    )
    statement = sa.select(observed)
    if query and (prefix := query.strip()):
        statement = statement.where(
            sa.or_(
                observed.c.state_type.istartswith(prefix, autoescape=True),
                observed.c.state_name.istartswith(prefix, autoescape=True),
            )
        )
    ordering = [observed.c.state_type.asc(), observed.c.state_name.asc()]
    if order_by == ObservedStateSort.LAST_SEEN_DESC:
        ordering.insert(0, observed.c.last_seen.desc())
    result = await session.execute(statement.order_by(*ordering).limit(limit))
    return [ObservedState.model_validate(row) for row in result.mappings()]
