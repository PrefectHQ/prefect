"""
Routes for interacting with Deployment objects.
"""

import datetime
from typing import List
from uuid import UUID

import pendulum
from fastapi import Body, Depends, HTTPException, Path, Response, status

import prefect.orion.api.dependencies as dependencies
import prefect.orion.models as models
import prefect.orion.schemas as schemas
from prefect.orion.database.dependencies import provide_database_interface
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.exceptions import ObjectNotFoundError
from prefect.orion.utilities.schemas import DateTimeTZ
from prefect.orion.utilities.server import OrionRouter

router = OrionRouter(prefix="/deployments", tags=["Deployments"])


@router.post("/")
async def create_deployment(
    deployment: schemas.actions.DeploymentCreate,
    response: Response,
    db: OrionDBInterface = Depends(provide_database_interface),
) -> schemas.core.Deployment:
    """
    Gracefully creates a new deployment from the provided schema. If a deployment with
    the same name and flow_id already exists, the deployment is updated.

    If the deployment has an active schedule, flow runs will be scheduled.
    When upserting, any scheduled runs from the existing deployment will be deleted.
    """

    # hydrate the input model into a full model
    deployment = schemas.core.Deployment(**deployment.dict())

    async with db.session_context(begin_transaction=True) as session:
        # check to see if relevant blocks exist, allowing us throw a useful error message
        # for debugging
        if deployment.infrastructure_document_id is not None:
            infrastructure_block = (
                await models.block_documents.read_block_document_by_id(
                    session=session,
                    block_document_id=deployment.infrastructure_document_id,
                )
            )
            if not infrastructure_block:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Error creating deployment. Could not find infrastructure block with id: {deployment.infrastructure_document_id}. This usually occurs when applying a deployment specification that was built against a different Prefect database / workspace.",
                )

        if deployment.storage_document_id is not None:
            infrastructure_block = (
                await models.block_documents.read_block_document_by_id(
                    session=session,
                    block_document_id=deployment.storage_document_id,
                )
            )
            if not infrastructure_block:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Error creating deployment. Could not find storage block with id: {deployment.storage_document_id}. This usually occurs when applying a deployment specification that was built against a different Prefect database / workspace.",
                )

        now = pendulum.now()
        model = await models.deployments.create_deployment(
            session=session, deployment=deployment
        )

    if model.created >= now:
        response.status_code = status.HTTP_201_CREATED

    return model


@router.patch("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_deployment(
    deployment: schemas.actions.DeploymentUpdate,
    deployment_id: str = Path(..., description="The deployment id", alias="id"),
    db: OrionDBInterface = Depends(provide_database_interface),
):
    async with db.session_context(begin_transaction=True) as session:
        result = await models.deployments.update_deployment(
            session=session, deployment_id=deployment_id, deployment=deployment
        )
    if not result:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Deployment not found.")


@router.get("/name/{flow_name}/{deployment_name}")
async def read_deployment_by_name(
    flow_name: str = Path(..., description="The name of the flow"),
    deployment_name: str = Path(..., description="The name of the deployment"),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> schemas.core.Deployment:
    """
    Get a deployment using the name of the flow and the deployment.
    """
    async with db.session_context() as session:
        deployment = await models.deployments.read_deployment_by_name(
            session=session, name=deployment_name, flow_name=flow_name
        )
    if not deployment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Deployment not found")
    return deployment


@router.get("/{id}")
async def read_deployment(
    deployment_id: UUID = Path(..., description="The deployment id", alias="id"),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> schemas.core.Deployment:
    """
    Get a deployment by id.
    """
    async with db.session_context() as session:
        deployment = await models.deployments.read_deployment(
            session=session, deployment_id=deployment_id
        )
    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found"
        )
    return deployment


@router.post("/filter")
async def read_deployments(
    limit: int = dependencies.LimitBody(),
    offset: int = Body(0, ge=0),
    flows: schemas.filters.FlowFilter = None,
    flow_runs: schemas.filters.FlowRunFilter = None,
    task_runs: schemas.filters.TaskRunFilter = None,
    deployments: schemas.filters.DeploymentFilter = None,
    worker_pools: schemas.filters.WorkerPoolFilter = None,
    worker_pool_queues: schemas.filters.WorkerPoolQueueFilter = None,
    sort: schemas.sorting.DeploymentSort = Body(
        schemas.sorting.DeploymentSort.NAME_ASC
    ),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> List[schemas.core.Deployment]:
    """
    Query for deployments.
    """
    async with db.session_context() as session:
        return await models.deployments.read_deployments(
            session=session,
            offset=offset,
            sort=sort,
            limit=limit,
            flow_filter=flows,
            flow_run_filter=flow_runs,
            task_run_filter=task_runs,
            deployment_filter=deployments,
            worker_pool_filter=worker_pools,
            worker_pool_queue_filter=worker_pool_queues,
        )


@router.post("/count")
async def count_deployments(
    flows: schemas.filters.FlowFilter = None,
    flow_runs: schemas.filters.FlowRunFilter = None,
    task_runs: schemas.filters.TaskRunFilter = None,
    deployments: schemas.filters.DeploymentFilter = None,
    worker_pools: schemas.filters.WorkerPoolFilter = None,
    worker_pool_queues: schemas.filters.WorkerPoolQueueFilter = None,
    db: OrionDBInterface = Depends(provide_database_interface),
) -> int:
    """
    Count deployments.
    """
    async with db.session_context() as session:
        return await models.deployments.count_deployments(
            session=session,
            flow_filter=flows,
            flow_run_filter=flow_runs,
            task_run_filter=task_runs,
            deployment_filter=deployments,
            worker_pool_filter=worker_pools,
            worker_pool_queue_filter=worker_pool_queues,
        )


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deployment(
    deployment_id: UUID = Path(..., description="The deployment id", alias="id"),
    db: OrionDBInterface = Depends(provide_database_interface),
):
    """
    Delete a deployment by id.
    """
    async with db.session_context(begin_transaction=True) as session:
        result = await models.deployments.delete_deployment(
            session=session, deployment_id=deployment_id
        )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found"
        )


@router.post("/{id}/schedule")
async def schedule_deployment(
    deployment_id: UUID = Path(..., description="The deployment id", alias="id"),
    start_time: DateTimeTZ = Body(None, description="The earliest date to schedule"),
    end_time: DateTimeTZ = Body(None, description="The latest date to schedule"),
    min_time: datetime.timedelta = Body(
        None,
        description="Runs will be scheduled until at least this long after the `start_time`",
    ),
    min_runs: int = Body(None, description="The minimum number of runs to schedule"),
    max_runs: int = Body(None, description="The maximum number of runs to schedule"),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> None:
    """
    Schedule runs for a deployment. For backfills, provide start/end times in the past.

    This function will generate the minimum number of runs that satisfy the min
    and max times, and the min and max counts. Specifically, the following order
    will be respected:

        - Runs will be generated starting on or after the `start_time`
        - No more than `max_runs` runs will be generated
        - No runs will be generated after `end_time` is reached
        - At least `min_runs` runs will be generated
        - Runs will be generated until at least `start_time + min_time` is reached
    """
    async with db.session_context(begin_transaction=True) as session:
        await models.deployments.schedule_runs(
            session=session,
            deployment_id=deployment_id,
            start_time=start_time,
            min_time=min_time,
            end_time=end_time,
            min_runs=min_runs,
            max_runs=max_runs,
        )


@router.post("/{id}/set_schedule_active")
async def set_schedule_active(
    deployment_id: UUID = Path(..., description="The deployment id", alias="id"),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> None:
    """
    Set a deployment schedule to active. Runs will be scheduled immediately.
    """
    async with db.session_context(begin_transaction=True) as session:
        deployment = await models.deployments.read_deployment(
            session=session, deployment_id=deployment_id
        )
        if not deployment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found"
            )
        deployment.is_schedule_active = True


@router.post("/{id}/set_schedule_inactive")
async def set_schedule_inactive(
    deployment_id: UUID = Path(..., description="The deployment id", alias="id"),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> None:
    """
    Set a deployment schedule to inactive. Any auto-scheduled runs still in a Scheduled
    state will be deleted.
    """
    async with db.session_context(begin_transaction=False) as session:
        deployment = await models.deployments.read_deployment(
            session=session, deployment_id=deployment_id
        )
        if not deployment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found"
            )
        deployment.is_schedule_active = False
        # commit here to make the inactive schedule "visible" to the scheduler service
        await session.commit()

        # delete any auto scheduled runs
        await models.deployments._delete_scheduled_runs(
            session=session,
            deployment_id=deployment_id,
            db=db,
            auto_scheduled_only=True,
        )

        await session.commit()


@router.post("/{id}/create_flow_run")
async def create_flow_run_from_deployment(
    flow_run: schemas.actions.DeploymentFlowRunCreate,
    deployment_id: UUID = Path(..., description="The deployment id", alias="id"),
    db: OrionDBInterface = Depends(provide_database_interface),
    response: Response = None,
) -> schemas.core.FlowRun:
    """
    Create a flow run from a deployment.

    Any parameters not provided will be inferred from the deployment's parameters.
    If tags are not provided, the deployment's tags will be used.

    If no state is provided, the flow run will be created in a PENDING state.
    """
    async with db.session_context(begin_transaction=True) as session:
        # get relevant info from the deployment
        deployment = await models.deployments.read_deployment(
            session=session, deployment_id=deployment_id
        )

        if not deployment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found"
            )

        parameters = deployment.parameters
        parameters.update(flow_run.parameters or {})

        # hydrate the input model into a full flow run / state model
        flow_run = schemas.core.FlowRun(
            **flow_run.dict(
                exclude={
                    "parameters",
                    "tags",
                    "infrastructure_document_id",
                }
            ),
            flow_id=deployment.flow_id,
            deployment_id=deployment.id,
            parameters=parameters,
            tags=set(deployment.tags).union(flow_run.tags),
            infrastructure_document_id=(
                flow_run.infrastructure_document_id
                or deployment.infrastructure_document_id
            ),
            work_queue_name=deployment.work_queue_name,
            worker_pool_queue_id=deployment.worker_pool_queue_id,
        )

        if not flow_run.state:
            flow_run.state = schemas.states.Pending()

        now = pendulum.now("UTC")
        model = await models.flow_runs.create_flow_run(
            session=session, flow_run=flow_run
        )
        if model.created >= now:
            response.status_code = status.HTTP_201_CREATED
        return model


# DEPRECATED
@router.get("/{id}/work_queue_check", deprecated=True)
async def work_queue_check_for_deployment(
    deployment_id: UUID = Path(..., description="The deployment id", alias="id"),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> List[schemas.core.WorkQueue]:
    """
    Get list of work-queues that are able to pick up the specified deployment.

    This endpoint is intended to be used by the UI to provide users warnings
    about deployments that are unable to be executed because there are no work
    queues that will pick up their runs, based on existing filter criteria. It
    may be deprecated in the future because there is not a strict relationship
    between work queues and deployments.
    """
    try:
        async with db.session_context() as session:
            work_queues = await models.deployments.check_work_queues_for_deployment(
                session=session, deployment_id=deployment_id
            )
    except ObjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found"
        )
    return work_queues
