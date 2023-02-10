"""
Routes for interacting with log objects.
"""

from typing import List

from fastapi import Body, Depends, status

import prefect.server.api.dependencies as dependencies
import prefect.server.models as models
import prefect.server.schemas as schemas
from prefect.server.database.dependencies import provide_database_interface
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.utilities.server import PrefectRouter

router = PrefectRouter(prefix="/logs", tags=["Logs"])


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_logs(
    logs: List[schemas.actions.LogCreate],
    db: PrefectDBInterface = Depends(provide_database_interface),
):
    """Create new logs from the provided schema."""
    for batch in models.logs.split_logs_into_batches(logs):
        async with db.session_context(begin_transaction=True) as session:
            await models.logs.create_logs(session=session, logs=batch)


@router.post("/filter")
async def read_logs(
    limit: int = dependencies.LimitBody(),
    offset: int = Body(0, ge=0),
    logs: schemas.filters.LogFilter = None,
    sort: schemas.sorting.LogSort = Body(schemas.sorting.LogSort.TIMESTAMP_ASC),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> List[schemas.core.Log]:
    """
    Query for logs.
    """
    async with db.session_context() as session:
        return await models.logs.read_logs(
            session=session, log_filter=logs, offset=offset, limit=limit, sort=sort
        )
