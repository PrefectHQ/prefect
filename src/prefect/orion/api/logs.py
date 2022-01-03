"""
Routes for interacting with log objects.
"""

from typing import List

import sqlalchemy as sa
from fastapi import Depends, Response, Body
from starlette import status

from prefect import settings
from prefect.orion import models, schemas
from prefect.orion.api import dependencies
from prefect.orion.utilities.server import OrionRouter

router = OrionRouter(prefix="/logs", tags=["Logs"])


@router.post("/")
async def create_logs(
    logs: schemas.actions.LogsCreate,
    response: Response,
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.core.LogsCreated:
    """Create new logs from the provided schema."""
    logs = schemas.core.Logs(logs=[log.dict() for log in logs.logs])
    created = await models.logs.create_logs(session=session, logs=logs)
    response.status_code = status.HTTP_201_CREATED
    return schemas.core.LogsCreated(created=created)


@router.post("/filter")
async def read_logs(
    limit: int = Body(
        settings.orion.api.default_limit, ge=0, le=settings.orion.api.default_limit
    ),
    offset: int = Body(0, ge=0),
    logs: schemas.filters.LogFilter = None,
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.core.Logs:
    """
    Query for flows.
    """
    logs = await models.logs.read_logs(
        session=session,
        log_filter=logs,
        offset=offset,
        limit=limit,
    )
    return schemas.core.Logs(logs=logs)
