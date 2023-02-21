"""
Routes for interacting with Deployment objects.
"""

import datetime
from typing import List
from uuid import UUID

import jsonschema.exceptions
import pendulum
from fastapi import Body, Depends, HTTPException, Path, Response, status

import prefect.server.api.dependencies as dependencies
import prefect.server.models as models
import prefect.server.schemas as schemas
from prefect.server.api.workers import WorkerLookups
from prefect.server.database.dependencies import provide_database_interface
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.exceptions import MissingVariableError, ObjectNotFoundError
from prefect.server.models.workers import DEFAULT_AGENT_WORK_POOL_NAME
from prefect.server.utilities.schemas import DateTimeTZ
from prefect.server.utilities.server import PrefectRouter

router = PrefectRouter(prefix="/deployments", tags=["Deployments"])


@router.post("/")
async def create_deployment(
    deployment: schemas.actions.DeploymentCreate,
    response: Response,
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> schemas.responses.DeploymentResponse:
    """
    Gracefully creates a new deployment from the provided schema. If a deployment with
    the same name and flow_id already exists, the deployment is updated.

    If the deployment has an active schedule, flow runs will be scheduled.
    When upserting, any scheduled runs from the existing deployment will be deleted.
    """

    async with db.session_context(begin_transaction=True) as session:
        if (
            deployment.work_pool_name
            and deployment.work_pool_name != DEFAULT_AGENT_WORK_POOL_NAME
        ):
            # Make sure that deployment is valid before beginning creation process
            work_pool = await models.workers.read_work_pool_by_name(
                session=session, work_pool_name=deployment.work_pool_name
            )
            if work_pool is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f'Work pool "{deployment.work_pool_name}" not found.',
                )
            try:
                deployment.check_valid_configuration(work_pool.base_job_template)
            except (MissingVariableError, jsonschema.exceptions.ValidationError) as exc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Error creating deployment: {exc!r}",
                )

        # hydrate the input model into a full model
        deployment_dict = deployment.dict(exclude={"work_pool_name"})
        if deployment.work_pool_name and deployment.work_queue_name:
            # If a specific pool name/queue name combination was provided, get the
            # ID for that work pool queue.
            deployment_dict["work_queue_id"] = (
                await worker_lookups._get_work_queue_id_from_name(
                    session=session,
                    work_pool_name=deployment.work_pool_name,
                    work_queue_name=deployment.work_queue_name,
                    create_queue_if_not_found=True,
                )
            )
        elif deployment.work_pool_name:
            # If just a pool name was provided, get the ID for its default
            # work pool queue.
            deployment_dict["work_queue_id"] = (
                await worker_lookups._get_default_work_queue_id_from_work_pool_name(
                    session=session,
                    work_pool_name=deployment.work_pool_name,
                )
            )
        elif deployment.work_queue_name:
            # If just a queue name was provided, ensure that the queue exists and
            # get its ID.
            work_queue = await models.work_queues._ensure_work_queue_exists(
                session=session, name=deployment.work_queue_name
            )
            deployment_dict["work_queue_id"] = work_queue.id

        deployment = schemas.core.Deployment(**deployment_dict)
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
                    detail=(
                        "Error creating deployment. Could not find infrastructure"
                        f" block with id: {deployment.infrastructure_document_id}. This"
                        " usually occurs when applying a deployment specification that"
                        " was built against a different Prefect database / workspace."
                    ),
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
                    detail=(
                        "Error creating deployment. Could not find storage block with"
                        f" id: {deployment.storage_document_id}. This usually occurs"
                        " when applying a deployment specification that was built"
                        " against a different Prefect database / workspace."
                    ),
                )

        now = pendulum.now()
        model = await models.deployments.create_deployment(
            session=session, deployment=deployment
        )

        if model.created >= now:
            response.status_code = status.HTTP_201_CREATED

        return schemas.responses.DeploymentResponse.from_orm(model)


@router.patch("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_deployment(
    deployment: schemas.actions.DeploymentUpdate,
    deployment_id: str = Path(..., description="The deployment id", alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
):
    async with db.session_context(begin_transaction=True) as session:
        if deployment.work_pool_name:
            # Make sure that deployment is valid before beginning creation process
            work_pool = await models.workers.read_work_pool_by_name(
                session=session, work_pool_name=deployment.work_pool_name
            )
            try:
                deployment.check_valid_configuration(work_pool.base_job_template)
            except (MissingVariableError, jsonschema.exceptions.ValidationError) as exc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Error creating deployment: {exc!r}",
                )

        result = await models.deployments.update_deployment(
            session=session, deployment_id=deployment_id, deployment=deployment
        )
    if not result:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Deployment not found.")


@router.get("/name/{flow_name}/{deployment_name}")
async def read_deployment_by_name(
    flow_name: str = Path(..., description="The name of the flow"),
    deployment_name: str = Path(..., description="The name of the deployment"),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> schemas.responses.DeploymentResponse:
    """
    Get a deployment using the name of the flow and the deployment.
    """
    async with db.session_context() as session:
        deployment = await models.deployments.read_deployment_by_name(
            session=session, name=deployment_name, flow_name=flow_name
        )
        if not deployment:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail="Deployment not found"
            )
        return schemas.responses.DeploymentResponse.from_orm(deployment)


@router.get("/{id}")
async def read_deployment(
    deployment_id: UUID = Path(..., description="The deployment id", alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> schemas.responses.DeploymentResponse:
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
        return schemas.responses.DeploymentResponse.from_orm(deployment)


@router.post("/filter")
async def read_deployments(
    limit: int = dependencies.LimitBody(),
    offset: int = Body(0, ge=0),
    flows: schemas.filters.FlowFilter = None,
    flow_runs: schemas.filters.FlowRunFilter = None,
    task_runs: schemas.filters.TaskRunFilter = None,
    deployments: schemas.filters.DeploymentFilter = None,
    work_pools: schemas.filters.WorkPoolFilter = None,
    work_pool_queues: schemas.filters.WorkQueueFilter = None,
    sort: schemas.sorting.DeploymentSort = Body(
        schemas.sorting.DeploymentSort.NAME_ASC
    ),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> List[schemas.responses.DeploymentResponse]:
    """
    Query for deployments.
    """
    async with db.session_context() as session:
        response = await models.deployments.read_deployments(
            session=session,
            offset=offset,
            sort=sort,
            limit=limit,
            flow_filter=flows,
            flow_run_filter=flow_runs,
            task_run_filter=task_runs,
            deployment_filter=deployments,
            work_pool_filter=work_pools,
            work_queue_filter=work_pool_queues,
        )
        return [
            schemas.responses.DeploymentResponse.from_orm(orm_deployment=deployment)
            for deployment in response
        ]


@router.post("/count")
async def count_deployments(
    flows: schemas.filters.FlowFilter = None,
    flow_runs: schemas.filters.FlowRunFilter = None,
    task_runs: schemas.filters.TaskRunFilter = None,
    deployments: schemas.filters.DeploymentFilter = None,
    work_pools: schemas.filters.WorkPoolFilter = None,
    work_pool_queues: schemas.filters.WorkQueueFilter = None,
    db: PrefectDBInterface = Depends(provide_database_interface),
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
            work_pool_filter=work_pools,
            work_queue_filter=work_pool_queues,
        )


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deployment(
    deployment_id: UUID = Path(..., description="The deployment id", alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
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
        description=(
            "Runs will be scheduled until at least this long after the `start_time`"
        ),
    ),
    min_runs: int = Body(None, description="The minimum number of runs to schedule"),
    max_runs: int = Body(None, description="The maximum number of runs to schedule"),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    """
    Schedule runs for a deployment. For backfills, provide start/end times in the past.

    This function will generate the minimum number of runs that satisfy the min
    and max times, and the min and max counts. Specifically, the following order
    will be respected.

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
    db: PrefectDBInterface = Depends(provide_database_interface),
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
    db: PrefectDBInterface = Depends(provide_database_interface),
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
    db: PrefectDBInterface = Depends(provide_database_interface),
    response: Response = None,
) -> schemas.responses.FlowRunResponse:
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
            work_queue_id=deployment.work_queue_id,
        )

        if not flow_run.state:
            flow_run.state = schemas.states.Pending()

        now = pendulum.now("UTC")
        model = await models.flow_runs.create_flow_run(
            session=session, flow_run=flow_run
        )
        if model.created >= now:
            response.status_code = status.HTTP_201_CREATED
        return schemas.responses.FlowRunResponse.from_orm(model)


# DEPRECATED
@router.get("/{id}/work_queue_check", deprecated=True)
async def work_queue_check_for_deployment(
    deployment_id: UUID = Path(..., description="The deployment id", alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
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
