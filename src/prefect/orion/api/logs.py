"""
Routes for interacting with log objects.
"""

from typing import List

import sqlalchemy as sa
from fastapi import Depends, Response
from starlette import status

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
