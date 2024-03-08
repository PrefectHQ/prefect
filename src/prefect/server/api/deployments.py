"""
Routes for interacting with Deployment objects.
"""

import datetime
from typing import List
from uuid import UUID

import jsonschema.exceptions
import pendulum
from prefect._vendor.fastapi import Body, Depends, HTTPException, Path, Response, status

import prefect.server.api.dependencies as dependencies
import prefect.server.models as models
import prefect.server.schemas as schemas
from prefect._internal.compatibility.experimental import experiment_enabled
from prefect.server.api.validation import validate_job_variables_for_flow_run
from prefect.server.api.workers import WorkerLookups
from prefect.server.database.dependencies import provide_database_interface
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.exceptions import MissingVariableError, ObjectNotFoundError
from prefect.server.models.workers import DEFAULT_AGENT_WORK_POOL_NAME
from prefect.server.utilities.schemas import DateTimeTZ
from prefect.server.utilities.server import PrefectRouter
from prefect.settings import PREFECT_EXPERIMENTAL_ENABLE_FLOW_RUN_INFRA_OVERRIDES
from prefect.utilities.schema_tools.hydration import (
    HydrationContext,
    HydrationError,
    hydrate,
)
from prefect.utilities.schema_tools.validation import (
    CircularSchemaRefError,
    ValidationError,
    validate,
)

router = PrefectRouter(prefix="/deployments", tags=["Deployments"])


def _multiple_schedules_error(deployment_id) -> HTTPException:
    return HTTPException(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=(
            "Error updating deployment: "
            f"Deployment {deployment_id!r} has multiple schedules. "
            "Please use the UI or update your client to adjust this "
            "deployment's schedules.",
        ),
    )


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

    data = deployment.dict(exclude_unset=True)

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
            deployment_dict[
                "work_queue_id"
            ] = await worker_lookups._get_work_queue_id_from_name(
                session=session,
                work_pool_name=deployment.work_pool_name,
                work_queue_name=deployment.work_queue_name,
                create_queue_if_not_found=True,
            )
        elif deployment.work_pool_name:
            # If just a pool name was provided, get the ID for its default
            # work pool queue.
            deployment_dict[
                "work_queue_id"
            ] = await worker_lookups._get_default_work_queue_id_from_work_pool_name(
                session=session,
                work_pool_name=deployment.work_pool_name,
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

        # Ensure that `paused` and `is_schedule_active` are consistent.
        if "paused" in data:
            deployment.is_schedule_active = not data["paused"]
        elif "is_schedule_active" in data:
            deployment.paused = not data["is_schedule_active"]

        now = pendulum.now("UTC")
        model = await models.deployments.create_deployment(
            session=session, deployment=deployment
        )

        if model.created >= now:
            response.status_code = status.HTTP_201_CREATED

        return schemas.responses.DeploymentResponse.from_orm(model)


@router.patch("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_deployment(
    deployment: schemas.actions.DeploymentUpdate,
    deployment_id: UUID = Path(..., description="The deployment id", alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
):
    async with db.session_context(begin_transaction=True) as session:
        existing_deployment = await models.deployments.read_deployment(
            session=session, deployment_id=deployment_id
        )
        if not existing_deployment:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail="Deployment not found."
            )

        # We need to make sure that when a user PATCHes a deployment with
        # `schedule` and `is_schedule_active` fields, that we populate the
        # `schedules` field so that the one-to-many relationship is updated.
        # This is support for legacy clients that don't know about the
        # `schedules` field.

        update_data = deployment.dict(exclude_unset=True)

        if "schedule" in update_data or "is_schedule_active" in update_data:
            if len(existing_deployment.schedules) > 1:
                raise _multiple_schedules_error(deployment_id)

            schedule = (
                update_data["schedule"]
                if "schedule" in update_data
                else existing_deployment.schedule
            )
            active = (
                update_data["is_schedule_active"]
                if "is_schedule_active" in update_data
                else existing_deployment.is_schedule_active
            )

            if schedule is not None:
                deployment.schedules = [
                    schemas.actions.DeploymentScheduleCreate(
                        schedule=schedule, active=active
                    )
                ]
            elif schedule is None:
                deployment.schedules = []

        # Ensure that `paused` and `is_schedule_active` are consistent.
        if "paused" in update_data:
            deployment.is_schedule_active = not update_data["paused"]
        elif "is_schedule_active" in update_data:
            deployment.paused = not update_data["is_schedule_active"]

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

        if deployment.parameters is not None:
            if experiment_enabled("enhanced_deployment_parameters"):
                try:
                    dehydrated_params = deployment.parameters
                    ctx = await HydrationContext.build(
                        session=session,
                        raise_on_error=True,
                    )
                    parameters = hydrate(dehydrated_params, ctx)
                    deployment.parameters = parameters
                except HydrationError as exc:
                    raise HTTPException(
                        status.HTTP_400_BAD_REQUEST,
                        detail=f"Error hydrating deployment parameters: {exc}",
                    )
            else:
                parameters = deployment.parameters
        else:
            parameters = existing_deployment.parameters

        enforce_parameter_schema = (
            deployment.enforce_parameter_schema
            if deployment.enforce_parameter_schema is not None
            else existing_deployment.enforce_parameter_schema
        )
        if enforce_parameter_schema:
            # ensure that the new parameters conform to the existing schema
            if not isinstance(existing_deployment.parameter_openapi_schema, dict):
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail=(
                        "Error updating deployment: Cannot update parameters because"
                        " parameter schema enforcement is enabled and the deployment"
                        " does not have a valid parameter schema."
                    ),
                )
            try:
                validate(
                    parameters,
                    existing_deployment.parameter_openapi_schema,
                    raise_on_error=True,
                    ignore_required=True,
                )
            except ValidationError as exc:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail=f"Error updating deployment: {exc}",
                )
            except CircularSchemaRefError:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Invalid schema: Unable to validate schema with circular references.",
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


@router.post("/get_scheduled_flow_runs")
async def get_scheduled_flow_runs_for_deployments(
    deployment_ids: List[UUID] = Body(
        default=..., description="The deployment IDs to get scheduled runs for"
    ),
    scheduled_before: DateTimeTZ = Body(
        None, description="The maximum time to look for scheduled flow runs"
    ),
    limit: int = dependencies.LimitBody(),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> List[schemas.responses.FlowRunResponse]:
    """
    Get scheduled runs for a set of deployments. Used by a runner to poll for work.
    """
    async with db.session_context() as session:
        orm_flow_runs = await models.flow_runs.read_flow_runs(
            session=session,
            limit=limit,
            deployment_filter=schemas.filters.DeploymentFilter(
                id=schemas.filters.DeploymentFilterId(any_=deployment_ids),
            ),
            flow_run_filter=schemas.filters.FlowRunFilter(
                next_scheduled_start_time=schemas.filters.FlowRunFilterNextScheduledStartTime(
                    before_=scheduled_before
                ),
                state=schemas.filters.FlowRunFilterState(
                    type=schemas.filters.FlowRunFilterStateType(
                        any_=[schemas.states.StateType.SCHEDULED]
                    )
                ),
            ),
            sort=schemas.sorting.FlowRunSort.NEXT_SCHEDULED_START_TIME_ASC,
        )

        flow_run_responses = [
            schemas.responses.FlowRunResponse.from_orm(orm_flow_run=orm_flow_run)
            for orm_flow_run in orm_flow_runs
        ]

    async with db.session_context(
        begin_transaction=True, with_for_update=True
    ) as session:
        await models.deployments._update_deployment_last_polled(
            session=session, deployment_ids=deployment_ids
        )

    return flow_run_responses


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
        deployment.paused = False

        # Ensure that we're updating the replicated schedule's `active` field,
        # if there is only a single schedule. This is support for legacy
        # clients.

        number_of_schedules = len(deployment.schedules)

        if number_of_schedules == 1:
            deployment.schedules[0].active = True
        elif number_of_schedules > 1:
            raise _multiple_schedules_error(deployment_id)


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
        deployment.paused = False

        # Ensure that we're updating the replicated schedule's `active` field,
        # if there is only a single schedule. This is support for legacy
        # clients.

        number_of_schedules = len(deployment.schedules)

        if number_of_schedules == 1:
            deployment.schedules[0].active = False
        elif number_of_schedules > 1:
            raise _multiple_schedules_error(deployment_id)

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
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    response: Response = None,
) -> schemas.responses.FlowRunResponse:
    """
    Create a flow run from a deployment.

    Any parameters not provided will be inferred from the deployment's parameters.
    If tags are not provided, the deployment's tags will be used.

    If no state is provided, the flow run will be created in a SCHEDULED state.
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

        if experiment_enabled("enhanced_deployment_parameters"):
            try:
                dehydrated_params = deployment.parameters
                dehydrated_params.update(flow_run.parameters or {})
                ctx = await HydrationContext.build(session=session, raise_on_error=True)
                parameters = hydrate(dehydrated_params, ctx)
            except HydrationError as exc:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail=f"Error hydrating flow run parameters: {exc}",
                )
        else:
            parameters = deployment.parameters
            parameters.update(flow_run.parameters or {})

        if deployment.enforce_parameter_schema:
            if not isinstance(deployment.parameter_openapi_schema, dict):
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail=(
                        "Error updating deployment: Cannot update parameters because"
                        " parameter schema enforcement is enabled and the deployment"
                        " does not have a valid parameter schema."
                    ),
                )
            try:
                validate(
                    parameters, deployment.parameter_openapi_schema, raise_on_error=True
                )
            except ValidationError as exc:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail=f"Error creating flow run: {exc}",
                )
            except CircularSchemaRefError:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Invalid schema: Unable to validate schema with circular references.",
                )

        if PREFECT_EXPERIMENTAL_ENABLE_FLOW_RUN_INFRA_OVERRIDES:
            validate_job_variables_for_flow_run(flow_run, deployment)

        work_queue_name = deployment.work_queue_name
        work_queue_id = deployment.work_queue_id

        if flow_run.work_queue_name:
            # can't mutate the ORM model or else it will commit the changes back
            work_queue_id = await worker_lookups._get_work_queue_id_from_name(
                session=session,
                work_pool_name=deployment.work_queue.work_pool.name,
                work_queue_name=flow_run.work_queue_name,
                create_queue_if_not_found=True,
            )
            work_queue_name = flow_run.work_queue_name

        # hydrate the input model into a full flow run / state model
        flow_run = schemas.core.FlowRun(
            **flow_run.dict(
                exclude={
                    "parameters",
                    "tags",
                    "infrastructure_document_id",
                    "work_queue_name",
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
            work_queue_name=work_queue_name,
            work_queue_id=work_queue_id,
        )

        if not flow_run.state:
            flow_run.state = schemas.states.Scheduled()

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
    except ObjectNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found"
        )
    return work_queues


@router.get("/{id}/schedules")
async def read_deployment_schedules(
    deployment_id: UUID = Path(..., description="The deployment id", alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> List[schemas.core.DeploymentSchedule]:
    async with db.session_context() as session:
        deployment = await models.deployments.read_deployment(
            session=session, deployment_id=deployment_id
        )

        if not deployment:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail="Deployment not found."
            )

        return await models.deployments.read_deployment_schedules(
            session=session,
            deployment_id=deployment.id,
        )


@router.post("/{id}/schedules", status_code=status.HTTP_201_CREATED)
async def create_deployment_schedules(
    deployment_id: UUID = Path(..., description="The deployment id", alias="id"),
    schedules: List[schemas.actions.DeploymentScheduleCreate] = Body(
        default=..., description="The schedules to create"
    ),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> List[schemas.core.DeploymentSchedule]:
    async with db.session_context(begin_transaction=True) as session:
        deployment = await models.deployments.read_deployment(
            session=session, deployment_id=deployment_id
        )

        if not deployment:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail="Deployment not found."
            )

        created = await models.deployments.create_deployment_schedules(
            session=session,
            deployment_id=deployment.id,
            schedules=schedules,
        )

        return created


@router.patch("/{id}/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_deployment_schedule(
    deployment_id: UUID = Path(..., description="The deployment id", alias="id"),
    schedule_id: UUID = Path(..., description="The schedule id", alias="schedule_id"),
    schedule: schemas.actions.DeploymentScheduleUpdate = Body(
        default=..., description="The updated schedule"
    ),
    db: PrefectDBInterface = Depends(provide_database_interface),
):
    async with db.session_context(begin_transaction=True) as session:
        deployment = await models.deployments.read_deployment(
            session=session, deployment_id=deployment_id
        )

        if not deployment:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail="Deployment not found."
            )

        updated = await models.deployments.update_deployment_schedule(
            session=session,
            deployment_id=deployment_id,
            deployment_schedule_id=schedule_id,
            schedule=schedule,
        )

        if not updated:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Schedule not found.")

        await models.deployments._delete_scheduled_runs(
            session=session,
            deployment_id=deployment_id,
            db=db,
            auto_scheduled_only=True,
        )


@router.delete("/{id}/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deployment_schedule(
    deployment_id: UUID = Path(..., description="The deployment id", alias="id"),
    schedule_id: UUID = Path(..., description="The schedule id", alias="schedule_id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
):
    async with db.session_context(begin_transaction=True) as session:
        deployment = await models.deployments.read_deployment(
            session=session, deployment_id=deployment_id
        )

        if not deployment:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail="Deployment not found."
            )

        deleted = await models.deployments.delete_deployment_schedule(
            session=session,
            deployment_id=deployment_id,
            deployment_schedule_id=schedule_id,
        )

        if not deleted:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Schedule not found.")

        await models.deployments._delete_scheduled_runs(
            session=session,
            deployment_id=deployment_id,
            db=db,
            auto_scheduled_only=True,
        )
