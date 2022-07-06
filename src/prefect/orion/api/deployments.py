"""
Routes for interacting with Deployment objects.
"""

import datetime
from typing import List
from uuid import UUID

import pendulum
import sqlalchemy as sa
from fastapi import Body, Depends, HTTPException, Path, Response, status

import prefect.orion.api.dependencies as dependencies
import prefect.orion.models as models
import prefect.orion.schemas as schemas
from prefect.orion.database.dependencies import provide_database_interface
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.exceptions import ObjectNotFoundError
from prefect.orion.utilities.server import OrionRouter

router = OrionRouter(prefix="/deployments", tags=["Deployments"])


@router.post("/")
async def create_deployment(
    deployment: schemas.actions.DeploymentCreate,
    response: Response,
    session: sa.orm.Session = Depends(dependencies.get_session),
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

    now = pendulum.now()
    model = await models.deployments.create_deployment(
        session=session, deployment=deployment
    )

    if model.created >= now:
        response.status_code = status.HTTP_201_CREATED

    # this deployment might have already scheduled runs (if it's being upserted)
    # so we delete them all here; if the upserted deployment has an active schedule
    # then its runs will be rescheduled.
    delete_query = sa.delete(db.FlowRun).where(
        db.FlowRun.deployment_id == model.id,
        db.FlowRun.state_type == schemas.states.StateType.SCHEDULED.value,
        db.FlowRun.auto_scheduled.is_(True),
    )
    await session.execute(delete_query)
    return model


@router.get("/name/{flow_name}/{deployment_name}")
async def read_deployment_by_name(
    flow_name: str = Path(..., description="The name of the flow"),
    deployment_name: str = Path(..., description="The name of the deployment"),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.core.Deployment:
    """
    Get a deployment using the name of the flow and the deployment.
    """
    deployment = await models.deployments.read_deployment_by_name(
        session=session, name=deployment_name, flow_name=flow_name
    )
    if not deployment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Deployment not found")
    return deployment


@router.get("/{id}")
async def read_deployment(
    deployment_id: UUID = Path(..., description="The deployment id", alias="id"),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.core.Deployment:
    """
    Get a deployment by id.
    """
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
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> List[schemas.core.Deployment]:
    """
    Query for deployments.
    """
    return await models.deployments.read_deployments(
        session=session,
        offset=offset,
        limit=limit,
        flow_filter=flows,
        flow_run_filter=flow_runs,
        task_run_filter=task_runs,
        deployment_filter=deployments,
    )


@router.post("/count")
async def count_deployments(
    flows: schemas.filters.FlowFilter = None,
    flow_runs: schemas.filters.FlowRunFilter = None,
    task_runs: schemas.filters.TaskRunFilter = None,
    deployments: schemas.filters.DeploymentFilter = None,
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> int:
    """
    Count deployments.
    """
    return await models.deployments.count_deployments(
        session=session,
        flow_filter=flows,
        flow_run_filter=flow_runs,
        task_run_filter=task_runs,
        deployment_filter=deployments,
    )


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deployment(
    deployment_id: UUID = Path(..., description="The deployment id", alias="id"),
    session: sa.orm.Session = Depends(dependencies.get_session),
    db: OrionDBInterface = Depends(provide_database_interface),
):
    """
    Delete a deployment by id.
    """
    result = await models.deployments.delete_deployment(
        session=session, deployment_id=deployment_id
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found"
        )

    # if the delete succeeded, delete any scheduled runs
    delete_query = sa.delete(db.FlowRun).where(
        db.FlowRun.deployment_id == deployment_id,
        db.FlowRun.state_type == schemas.states.StateType.SCHEDULED.value,
    )
    await session.execute(delete_query)


@router.post("/{id}/schedule")
async def schedule_deployment(
    deployment_id: UUID = Path(..., description="The deployment id", alias="id"),
    start_time: datetime.datetime = Body(
        None, description="The earliest date to schedule"
    ),
    end_time: datetime.datetime = Body(None, description="The latest date to schedule"),
    max_runs: int = Body(None, description="The maximum number of runs to schedule"),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> None:
    """
    Schedule runs for a deployment. For backfills, provide start/end times in the past.
    """
    await models.deployments.schedule_runs(
        session=session,
        deployment_id=deployment_id,
        start_time=start_time,
        end_time=end_time,
        max_runs=max_runs,
    )


@router.post("/{id}/set_schedule_active")
async def set_schedule_active(
    deployment_id: UUID = Path(..., description="The deployment id", alias="id"),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> None:
    """
    Set a deployment schedule to active. Runs will be scheduled immediately.
    """
    deployment = await models.deployments.read_deployment(
        session=session, deployment_id=deployment_id
    )
    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found"
        )
    deployment.is_schedule_active = True
    await session.flush()


@router.post("/{id}/set_schedule_inactive")
async def set_schedule_inactive(
    deployment_id: UUID = Path(..., description="The deployment id", alias="id"),
    session: sa.orm.Session = Depends(dependencies.get_session),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> None:
    """
    Set a deployment schedule to inactive. Any auto-scheduled runs still in a Scheduled
    state will be deleted.
    """
    deployment = await models.deployments.read_deployment(
        session=session, deployment_id=deployment_id
    )
    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found"
        )
    deployment.is_schedule_active = False
    await session.flush()

    # delete any future scheduled runs that were auto-scheduled
    delete_query = sa.delete(db.FlowRun).where(
        db.FlowRun.deployment_id == deployment.id,
        db.FlowRun.state_type == schemas.states.StateType.SCHEDULED.value,
        db.FlowRun.auto_scheduled.is_(True),
    )
    await session.execute(delete_query)


@router.post("/{id}/create_flow_run")
async def create_flow_run_from_deployment(
    flow_run: schemas.actions.DeploymentFlowRunCreate,
    deployment_id: UUID = Path(..., description="The deployment id", alias="id"),
    session: sa.orm.Session = Depends(dependencies.get_session),
    response: Response = None,
) -> schemas.core.FlowRun:
    """
    Create a flow run from a deployment.

    Any parameters not provided will be inferred from the deployment's parameters.
    If tags are not provided, the deployment's tags will be used.

    If no state is provided, the flow run will be created in a PENDING state.
    """
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
                "runner_type",
                "runner_config",
                "flow_runner",
            }
        ),
        flow_id=deployment.flow_id,
        deployment_id=deployment.id,
        parameters=parameters,
        tags=set(deployment.tags).union(flow_run.tags),
        flow_runner=flow_run.flow_runner or deployment.flow_runner,
    )

    if not flow_run.state:
        flow_run.state = schemas.states.Pending()

    now = pendulum.now("UTC")
    model = await models.flow_runs.create_flow_run(session=session, flow_run=flow_run)
    if model.created >= now:
        response.status_code = status.HTTP_201_CREATED
    return model


@router.get("/{id}/work_queue_check")
async def work_queue_check_for_deployment(
    deployment_id: UUID = Path(..., description="The deployment id", alias="id"),
    session: sa.orm.Session = Depends(dependencies.get_session),
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
        work_queues = await models.deployments.check_work_queues_for_deployment(
            session=session, deployment_id=deployment_id
        )
    except ObjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found"
        )
    return work_queues
