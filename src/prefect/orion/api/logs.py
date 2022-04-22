"""
Routes for interacting with log objects.
"""

from typing import List

import sqlalchemy as sa
from fastapi import Body, Depends, Response, status

import prefect.orion.api.dependencies as dependencies
import prefect.orion.models as models
import prefect.orion.schemas as schemas
from prefect.orion.utilities.server import OrionRouter

router = OrionRouter(prefix="/logs", tags=["Logs"])


@router.post("/")
async def create_logs(
    logs: List[schemas.actions.LogCreate],
    response: Response,
    session: sa.orm.Session = Depends(dependencies.get_session),
):
    """Create new logs from the provided schema."""
    await models.logs.create_logs(session=session, logs=logs)
    response.status_code = status.HTTP_201_CREATED


@router.post("/filter")
async def read_logs(
    limit: int = dependencies.LimitBody(),
    offset: int = Body(0, ge=0),
    logs: schemas.filters.LogFilter = None,
    sort: schemas.sorting.LogSort = Body(schemas.sorting.LogSort.TIMESTAMP_ASC),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> List[schemas.core.Log]:
    """
    Query for logs.
    """
    return await models.logs.read_logs(
        session=session, log_filter=logs, offset=offset, limit=limit, sort=sort
    )
