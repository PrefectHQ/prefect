"""
Routes for interacting with flow objects.
"""

from typing import List
from uuid import UUID

import pendulum
from fastapi import Depends, HTTPException, Path, Response, status
from fastapi.param_functions import Body

import prefect.orion.api.dependencies as dependencies
import prefect.orion.models as models
import prefect.orion.schemas as schemas
from prefect.orion.database.dependencies import provide_database_interface
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.utilities.server import OrionRouter

router = OrionRouter(prefix="/flows", tags=["Flows"])


@router.post("/")
async def create_flow(
    flow: schemas.actions.FlowCreate,
    response: Response,
    db: OrionDBInterface = Depends(provide_database_interface),
) -> schemas.core.Flow:
    """Gracefully creates a new flow from the provided schema. If a flow with the
    same name already exists, the existing flow is returned.
    """
    # hydrate the input model into a full flow model
    flow = schemas.core.Flow(**flow.dict())

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
    db: OrionDBInterface = Depends(provide_database_interface),
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
    db: OrionDBInterface = Depends(provide_database_interface),
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
        )


@router.get("/name/{name}")
async def read_flow_by_name(
    name: str = Path(..., description="The name of the flow"),
    db: OrionDBInterface = Depends(provide_database_interface),
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
    db: OrionDBInterface = Depends(provide_database_interface),
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
    sort: schemas.sorting.FlowSort = Body(schemas.sorting.FlowSort.NAME_ASC),
    db: OrionDBInterface = Depends(provide_database_interface),
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
            sort=sort,
            offset=offset,
            limit=limit,
        )


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flow(
    flow_id: UUID = Path(..., description="The flow id", alias="id"),
    db: OrionDBInterface = Depends(provide_database_interface),
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
