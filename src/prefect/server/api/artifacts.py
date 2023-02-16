"""
Routes for interacting with artifact objects.
"""
from typing import List
from uuid import UUID

import pendulum
from fastapi import Body, Depends, HTTPException, Path, Response, status

import prefect.server.api.dependencies as dependencies
from prefect.server import models
from prefect.server.database.dependencies import provide_database_interface
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.schemas import actions, core, filters, sorting
from prefect.server.utilities.server import PrefectRouter
from prefect.settings import PREFECT_EXPERIMENTAL_ENABLE_ARTIFACTS


def error_404_if_artifacts_not_enabled():
    if not PREFECT_EXPERIMENTAL_ENABLE_ARTIFACTS.value():
        raise HTTPException(status_code=404, detail="Artifacts are not enabled")


router = PrefectRouter(
    prefix="/experimental/artifacts",
    tags=["Artifacts"],
    dependencies=[Depends(error_404_if_artifacts_not_enabled)],
)


@router.post("/")
async def create_artifact(
    artifact: actions.ArtifactCreate,
    response: Response = None,
    db: PrefectDBInterface = Depends(provide_database_interface),
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
    db: PrefectDBInterface = Depends(provide_database_interface),
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
    db: PrefectDBInterface = Depends(provide_database_interface),
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


@router.patch("/{id}", status_code=204)
async def update_artifact(
    artifact: actions.ArtifactUpdate,
    artifact_id: UUID = Path(
        ..., description="The ID of the artifact to update.", alias="id"
    ),
    db: PrefectDBInterface = Depends(provide_database_interface),
):
    """
    Update an artifact in the database.
    """
    async with db.session_context(begin_transaction=True) as session:
        result = await models.artifacts.update_artifact(
            session=session,
            artifact_id=artifact_id,
            artifact=artifact,
        )
    if not result:
        raise HTTPException(status_code=404, detail="Artifact not found.")


@router.delete("/{id}", status_code=204)
async def delete_artifact(
    artifact_id: UUID = Path(
        ..., description="The ID of the artifact to delete.", alias="id"
    ),
    db: PrefectDBInterface = Depends(provide_database_interface),
):
    """
    Delete an artifact from the database.
    """
    async with db.session_context(begin_transaction=True) as session:
        result = await models.artifacts.delete_artifact(
            session=session,
            artifact_id=artifact_id,
        )
    if not result:
        raise HTTPException(status_code=404, detail="Artifact not found.")
