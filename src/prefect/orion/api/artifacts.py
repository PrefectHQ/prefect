"""
Routes for interacting with artifact objects.
"""
from typing import List
from uuid import UUID

import pendulum
from fastapi import Body, Depends, HTTPException, Path, Response, status

import prefect.orion.api.dependencies as dependencies
from prefect.orion import models
from prefect.orion.database.dependencies import provide_database_interface
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.schemas import actions, core, filters, sorting
from prefect.orion.utilities.server import OrionRouter
from prefect.settings import PREFECT_EXPERIMENTAL_ENABLE_ARTIFACTS


def error_404_if_artifacts_not_enabled():
    if not PREFECT_EXPERIMENTAL_ENABLE_ARTIFACTS:
        raise HTTPException(status_code=404, detail="Artifacts are not enabled")


router = OrionRouter(
    prefix="/experimental/artifacts",
    tags=["Artifacts"],
    dependencies=[Depends(error_404_if_artifacts_not_enabled)],
)


@router.post("/")
async def create_artifact(
    artifact: actions.ArtifactCreate,
    response: Response = None,
    db: OrionDBInterface = Depends(provide_database_interface),
) -> core.Artifact:
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


@router.post("/filter")
async def read_artifacts(
    sort: sorting.ArtifactSort = Body(sorting.ArtifactSort.ID_DESC),
    limit: int = dependencies.LimitBody(),
    offset: int = Body(0, ge=0),
    artifacts: filters.ArtifactFilter = None,
    flow_runs: filters.FlowRunFilter = None,
    task_runs: filters.TaskRunFilter = None,
    db: OrionDBInterface = Depends(provide_database_interface),
) -> List[core.Artifact]:
    """
    Retrieve artifacts from the database.
    """
    async with db.session_context() as session:
        return await models.artifacts.read_artifacts(
            session=session,
            artifact_filter=artifacts,
            flow_run_filter=flow_runs,
            task_run_filter=task_runs,
            offset=offset,
            limit=limit,
            sort=sort,
        )
