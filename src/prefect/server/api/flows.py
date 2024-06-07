"""
Routes for interacting with flow objects.
"""

from typing import List, Optional
from uuid import UUID

import pendulum
from fastapi import Depends, HTTPException, Path, Response, status
from fastapi.param_functions import Body

import prefect.server.api.dependencies as dependencies
import prefect.server.models as models
import prefect.server.schemas as schemas
from prefect.server.database.dependencies import provide_database_interface
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.schemas.responses import FlowPaginationResponse
from prefect.server.utilities.server import PrefectRouter

router = PrefectRouter(prefix="/flows", tags=["Flows"])


@router.post("/")
async def create_flow(
    flow: schemas.actions.FlowCreate,
    response: Response,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> schemas.core.Flow:
    """Gracefully creates a new flow from the provided schema. If a flow with the
    same name already exists, the existing flow is returned.
    """
    # hydrate the input model into a full flow model
    flow = schemas.core.Flow(**flow.model_dump())

    now = pendulum.now("UTC")

    async with db.session_context(begin_transaction=True) as session:
        model = await models.flows.create_flow(session=session, flow=flow)

    if model.created >= now:
        response.status_code = status.HTTP_201_CREATED
    return model


@router.patch("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_flow(
    flow: schemas.actions.FlowUpdate,
    flow_id: UUID = Path(..., description="The flow id", alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
):
    """
    Updates a flow.
    """
    async with db.session_context(begin_transaction=True) as session:
        result = await models.flows.update_flow(
            session=session, flow=flow, flow_id=flow_id
        )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found"
        )


@router.post("/count")
async def count_flows(
    flows: schemas.filters.FlowFilter = None,
    flow_runs: schemas.filters.FlowRunFilter = None,
    task_runs: schemas.filters.TaskRunFilter = None,
    deployments: schemas.filters.DeploymentFilter = None,
    work_pools: schemas.filters.WorkPoolFilter = None,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> int:
    """
    Count flows.
    """
    async with db.session_context() as session:
        return await models.flows.count_flows(
            session=session,
            flow_filter=flows,
            flow_run_filter=flow_runs,
            task_run_filter=task_runs,
            deployment_filter=deployments,
            work_pool_filter=work_pools,
        )


@router.get("/name/{name}")
async def read_flow_by_name(
    name: str = Path(..., description="The name of the flow"),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> schemas.core.Flow:
    """
    Get a flow by name.
    """
    async with db.session_context() as session:
        flow = await models.flows.read_flow_by_name(session=session, name=name)
    if not flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found"
        )
    return flow


@router.get("/{id}")
async def read_flow(
    flow_id: UUID = Path(..., description="The flow id", alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> schemas.core.Flow:
    """
    Get a flow by id.
    """
    async with db.session_context() as session:
        flow = await models.flows.read_flow(session=session, flow_id=flow_id)
    if not flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found"
        )
    return flow


@router.post("/filter")
async def read_flows(
    limit: int = dependencies.LimitBody(),
    offset: int = Body(0, ge=0),
    flows: schemas.filters.FlowFilter = None,
    flow_runs: schemas.filters.FlowRunFilter = None,
    task_runs: schemas.filters.TaskRunFilter = None,
    deployments: schemas.filters.DeploymentFilter = None,
    work_pools: schemas.filters.WorkPoolFilter = None,
    sort: schemas.sorting.FlowSort = Body(schemas.sorting.FlowSort.NAME_ASC),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> List[schemas.core.Flow]:
    """
    Query for flows.
    """
    async with db.session_context() as session:
        return await models.flows.read_flows(
            session=session,
            flow_filter=flows,
            flow_run_filter=flow_runs,
            task_run_filter=task_runs,
            deployment_filter=deployments,
            work_pool_filter=work_pools,
            sort=sort,
            offset=offset,
            limit=limit,
        )


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flow(
    flow_id: UUID = Path(..., description="The flow id", alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
):
    """
    Delete a flow by id.
    """
    async with db.session_context(begin_transaction=True) as session:
        result = await models.flows.delete_flow(session=session, flow_id=flow_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found"
        )


@router.post("/paginate")
async def paginate_flows(
    limit: int = dependencies.LimitBody(),
    page: int = Body(1, ge=1),
    flows: Optional[schemas.filters.FlowFilter] = None,
    flow_runs: Optional[schemas.filters.FlowRunFilter] = None,
    task_runs: Optional[schemas.filters.TaskRunFilter] = None,
    deployments: Optional[schemas.filters.DeploymentFilter] = None,
    work_pools: Optional[schemas.filters.WorkPoolFilter] = None,
    sort: schemas.sorting.FlowSort = Body(schemas.sorting.FlowSort.NAME_ASC),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> FlowPaginationResponse:
    """
    Pagination query for flows.
    """
    offset = (page - 1) * limit

    async with db.session_context() as session:
        results = await models.flows.read_flows(
            session=session,
            flow_filter=flows,
            flow_run_filter=flow_runs,
            task_run_filter=task_runs,
            deployment_filter=deployments,
            work_pool_filter=work_pools,
            sort=sort,
            offset=offset,
            limit=limit,
        )

        count = await models.flows.count_flows(
            session=session,
            flow_filter=flows,
            flow_run_filter=flow_runs,
            task_run_filter=task_runs,
            deployment_filter=deployments,
            work_pool_filter=work_pools,
        )

    return FlowPaginationResponse(
        results=results,
        count=count,
        limit=limit,
        pages=(count + limit - 1) // limit,
        page=page,
    )
