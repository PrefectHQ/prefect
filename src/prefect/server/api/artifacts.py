"""
Routes for interacting with artifact objects.
"""

from typing import List
from uuid import UUID

from fastapi import Body, Depends, HTTPException, Path, Response, status

import prefect.server.api.dependencies as dependencies
from prefect.server import models
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.schemas import actions, core, filters, sorting
from prefect.server.utilities.server import PrefectRouter
from prefect.types._datetime import now

router: PrefectRouter = PrefectRouter(
    prefix="/artifacts",
    tags=["Artifacts"],
)


@router.post("/")
async def create_artifact(
    artifact: actions.ArtifactCreate,
    response: Response,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> core.Artifact:
    """
    Create an artifact.

    For more information, see https://docs.prefect.io/v3/develop/artifacts.
    """
    artifact = core.Artifact(**artifact.model_dump())

    right_now = now("UTC")

    async with db.session_context(begin_transaction=True) as session:
        model = await models.artifacts.create_artifact(
            session=session,
            artifact=artifact,
        )

    if model.created >= right_now:
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


@router.get("/{key}/latest")
async def read_latest_artifact(
    key: str = Path(
        ...,
        description="The key of the artifact to retrieve.",
    ),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> core.Artifact:
    """
    Retrieve the latest artifact from the artifact table.
    """
    async with db.session_context() as session:
        artifact = await models.artifacts.read_latest_artifact(session=session, key=key)

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
    flows: filters.FlowFilter = None,
    deployments: filters.DeploymentFilter = None,
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
            flow_filter=flows,
            deployment_filter=deployments,
            offset=offset,
            limit=limit,
            sort=sort,
        )


@router.post("/latest/filter")
async def read_latest_artifacts(
    sort: sorting.ArtifactCollectionSort = Body(sorting.ArtifactCollectionSort.ID_DESC),
    limit: int = dependencies.LimitBody(),
    offset: int = Body(0, ge=0),
    artifacts: filters.ArtifactCollectionFilter = None,
    flow_runs: filters.FlowRunFilter = None,
    task_runs: filters.TaskRunFilter = None,
    flows: filters.FlowFilter = None,
    deployments: filters.DeploymentFilter = None,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> List[core.ArtifactCollection]:
    """
    Retrieve artifacts from the database.
    """
    async with db.session_context() as session:
        return await models.artifacts.read_latest_artifacts(
            session=session,
            artifact_filter=artifacts,
            flow_run_filter=flow_runs,
            task_run_filter=task_runs,
            flow_filter=flows,
            deployment_filter=deployments,
            offset=offset,
            limit=limit,
            sort=sort,
        )


@router.post("/count")
async def count_artifacts(
    artifacts: filters.ArtifactFilter = None,
    flow_runs: filters.FlowRunFilter = None,
    task_runs: filters.TaskRunFilter = None,
    flows: filters.FlowFilter = None,
    deployments: filters.DeploymentFilter = None,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> int:
    """
    Count artifacts from the database.
    """
    async with db.session_context() as session:
        return await models.artifacts.count_artifacts(
            session=session,
            artifact_filter=artifacts,
            flow_run_filter=flow_runs,
            task_run_filter=task_runs,
            flow_filter=flows,
            deployment_filter=deployments,
        )


@router.post("/latest/count")
async def count_latest_artifacts(
    artifacts: filters.ArtifactCollectionFilter = None,
    flow_runs: filters.FlowRunFilter = None,
    task_runs: filters.TaskRunFilter = None,
    flows: filters.FlowFilter = None,
    deployments: filters.DeploymentFilter = None,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> int:
    """
    Count artifacts from the database.
    """
    async with db.session_context() as session:
        return await models.artifacts.count_latest_artifacts(
            session=session,
            artifact_filter=artifacts,
            flow_run_filter=flow_runs,
            task_run_filter=task_runs,
            flow_filter=flows,
            deployment_filter=deployments,
        )


@router.patch("/{id}", status_code=204)
async def update_artifact(
    artifact: actions.ArtifactUpdate,
    artifact_id: UUID = Path(
        ..., description="The ID of the artifact to update.", alias="id"
    ),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
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
) -> None:
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
