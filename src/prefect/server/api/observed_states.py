"""Routes for discovering observed state types and names."""

from typing import Annotated

from fastapi import Depends, Query

from prefect.server import models
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.schemas.observed_states import ObservedState, ObservedStateSort
from prefect.server.utilities.server import PrefectRouter

router: PrefectRouter = PrefectRouter(
    prefix="/observed-states", tags=["Observed States"]
)


@router.get("")
async def read_observed_states(
    db: Annotated[PrefectDBInterface, Depends(provide_database_interface)],
    query: Annotated[str | None, Query(max_length=100)] = None,
    order_by: ObservedStateSort = ObservedStateSort.LAST_SEEN_DESC,
    limit: Annotated[int, Query(ge=1, le=200)] = 200,
) -> list[ObservedState]:
    """Discover exact state names and types from retained run transitions.

    Search by case-insensitive name or type prefix. Timestamps describe retained
    history; deleting runs can change them or remove a state from the results.
    """
    async with db.session_context() as session:
        return await models.observed_states.read_observed_states(
            session=session, query=query, order_by=order_by, limit=limit
        )
