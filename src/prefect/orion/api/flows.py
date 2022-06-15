"""
Routes for interacting with flow objects.
"""

from typing import List
from uuid import UUID

import pendulum
import sqlalchemy as sa
from fastapi import Depends, HTTPException, Path, Response, status
from fastapi.param_functions import Body

import prefect.orion.api.dependencies as dependencies
import prefect.orion.models as models
import prefect.orion.schemas as schemas
from prefect.orion.utilities.server import OrionRouter

router = OrionRouter(prefix="/flows", tags=["Flows"])


@router.post("/")
async def create_flow(
    flow: schemas.actions.FlowCreate,
    response: Response,
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.core.Flow:
    """Gracefully creates a new flow from the provided schema. If a flow with the
    same name already exists, the existing flow is returned.
    """
    # hydrate the input model into a full flow model
    flow = schemas.core.Flow(**flow.dict())

    now = pendulum.now("UTC")
    model = await models.flows.create_flow(session=session, flow=flow)
    if model.created >= now:
        response.status_code = status.HTTP_201_CREATED
    return model


@router.patch("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_flow(
    flow: schemas.actions.FlowUpdate,
    flow_id: UUID = Path(..., description="The flow id", alias="id"),
    session: sa.orm.Session = Depends(dependencies.get_session),
):
    """
    Updates a flow.
    """
    result = await models.flows.update_flow(session=session, flow=flow, flow_id=flow_id)
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
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> int:
    """
    Count flows.
    """
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
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.core.Flow:
    """
    Get a flow by name.
    """
    flow = await models.flows.read_flow_by_name(session=session, name=name)
    if not flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found"
        )
    return flow


@router.get("/{id}")
async def read_flow(
    flow_id: UUID = Path(..., description="The flow id", alias="id"),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.core.Flow:
    """
    Get a flow by id.
    """
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
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> List[schemas.core.Flow]:
    """
    Query for flows.
    """
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
    session: sa.orm.Session = Depends(dependencies.get_session),
):
    """
    Delete a flow by id.
    """
    result = await models.flows.delete_flow(session=session, flow_id=flow_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found"
        )
