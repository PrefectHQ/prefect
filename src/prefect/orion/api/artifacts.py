"""
Routes for interacting with artifact objects.
"""

from uuid import UUID

import pendulum
from fastapi import Depends, HTTPException, Path, Response, status

from prefect.logging import get_logger
from prefect.orion import models
from prefect.orion.database.dependencies import provide_database_interface
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.schemas import actions, core
from prefect.orion.utilities.server import OrionRouter

logger = get_logger("orion.api")

router = OrionRouter(prefix="/artifacts", tags=["Artifacts"])


@router.post("/")
async def create_artifact(
    artifact: actions.ArtifactCreate,
    response: Response = None,
    db: OrionDBInterface = Depends(provide_database_interface),
) -> core.Artifact:
    """
    Create an artifact. If an artifact with the same artifact_id and key
    already exists, the existing artifact will be returned.
    """
    artifact = core.Artifact(**artifact.dict())

    now = pendulum.now("UTC")

    async with db.session_context(begin_transaction=True) as session:
        model = await models.artifacts.create_artifact(
            session=session,
            artifact=artifact,
        )

    if model.created >= now:
        response.status_code = status.HTTP_201_CREATED
    return model


@router.get("/{id}")
async def read_artifact(
    artifact_id: UUID = Path(
        ..., description="The ID of the artifact to retrieve.", alias="id"
    ),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> core.Artifact:
    """
    Retrieve an artifact from the database.
    """
    async with db.session_context() as session:
        artifact = await models.artifacts.read_artifact(
            session=session, artifact_id=artifact_id
        )

    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return artifact
