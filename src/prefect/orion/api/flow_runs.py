from typing import List
from uuid import UUID

import sqlalchemy as sa
from fastapi import Body, Depends, HTTPException, Path, Response, status

from prefect.orion import models, schemas
from prefect.orion.api import dependencies
from prefect.orion.orchestration.rules import OrchestrationResult
from prefect.orion.utilities.server import OrionRouter
from prefect.utilities.logging import get_logger

logger = get_logger("orion.api")

router = OrionRouter(prefix="/flow_runs", tags=["Flow Runs"])


@router.post("/")
async def create_flow_run(
    flow_run: schemas.actions.FlowRunCreate,
    session: sa.orm.Session = Depends(dependencies.get_session),
    response: Response = None,
) -> schemas.core.FlowRun:
    """
    Create a flow run
    """
    nested = await session.begin_nested()
    try:
        result = await models.flow_runs.create_flow_run(
            session=session, flow_run=flow_run
        )
        response.status_code = status.HTTP_201_CREATED
        return result
    except sa.exc.IntegrityError as exc:
        # try to load a flow run with the same idempotency key
        await nested.rollback()
        stmt = await session.execute(
            sa.select(models.orm.FlowRun).filter_by(
                flow_id=flow_run.flow_id,
                idempotency_key=flow_run.idempotency_key,
            )
        )
        result = stmt.scalar()

        # if nothing was returned, then the integrity error was caused by violating
        # a constraint other than the idempotency key. The most probable one is
        # that a primary key was provided that already exists in the database.
        if not result:
            msg = "Could not create flow run due to database constraint violations."
            logger.error(msg, exc_info=True)
            raise ValueError(msg)
        return result


# must be defined before `GET /:id`
@router.get("/count")
async def count_flow_runs(
    flows: schemas.filters.FlowFilter = None,
    flow_runs: schemas.filters.FlowRunFilter = None,
    task_runs: schemas.filters.TaskRunFilter = None,
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> int:
    """
    Query for flow runs
    """
    return await models.flow_runs.count_flow_runs(
        session=session,
        flow_filter=flows,
        flow_run_filter=flow_runs,
        task_run_filter=task_runs,
    )


@router.get("/{id}")
async def read_flow_run(
    flow_run_id: UUID = Path(..., description="The flow run id", alias="id"),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.core.FlowRun:
    """
    Get a flow run by id
    """
    flow_run = await models.flow_runs.read_flow_run(
        session=session, flow_run_id=flow_run_id
    )
    if not flow_run:
        raise HTTPException(status_code=404, detail="Flow run not found")
    return flow_run


from prefect.orion.utilities.enum import AutoEnum


class FlowRunSort(AutoEnum):
    id_desc = AutoEnum.auto()
    expected_start_time_desc = AutoEnum.auto()
    next_scheduled_start_time_asc = AutoEnum.auto()

    def __new__(cls, value):
        obj = object.__new__(cls)
        obj._value_ = value
        obj.sort_expression = cls.enum_string_to_sort_expression(value)
        return obj

    @staticmethod
    def enum_string_to_sort_expression(enum_str: str):
        sort_mapping = {
            "id_desc": models.orm.FlowRun.id.desc(),
            "expected_start_time_desc": models.orm.FlowRun.expected_start_time.desc(),
            "next_scheduled_start_time_asc": models.orm.FlowRun.next_scheduled_start_time.asc(),
        }
        return sort_mapping[enum_str]


@router.get("/")
async def read_flow_runs(
    sort: FlowRunSort = FlowRunSort.id_desc,
    pagination: schemas.filters.Pagination = Depends(),
    flows: schemas.filters.FlowFilter = None,
    flow_runs: schemas.filters.FlowRunFilter = None,
    task_runs: schemas.filters.TaskRunFilter = None,
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> List[schemas.core.FlowRun]:
    """
    Query for flow runs
    """
    return await models.flow_runs.read_flow_runs(
        session=session,
        flow_filter=flows,
        flow_run_filter=flow_runs,
        task_run_filter=task_runs,
        offset=pagination.offset,
        limit=pagination.limit,
        sort=sort.sort_expression,
    )


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flow_run(
    flow_run_id: UUID = Path(..., description="The flow run id", alias="id"),
    session: sa.orm.Session = Depends(dependencies.get_session),
):
    """
    Delete a flow run by id
    """
    result = await models.flow_runs.delete_flow_run(
        session=session, flow_run_id=flow_run_id
    )
    if not result:
        raise HTTPException(status_code=404, detail="Flow run not found")
    return result


@router.post("/{id}/set_state")
async def set_flow_run_state(
    flow_run_id: UUID = Path(..., description="The flow run id", alias="id"),
    state: schemas.actions.StateCreate = Body(..., description="The intended state."),
    session: sa.orm.Session = Depends(dependencies.get_session),
    response: Response = None,
) -> OrchestrationResult:
    """Set a flow run state, invoking any orchestration rules."""

    # create the state
    orchestration_result = await models.flow_run_states.orchestrate_flow_run_state(
        session=session,
        flow_run_id=flow_run_id,
        # convert to a full State object
        state=schemas.states.State.parse_obj(state),
    )

    # set the 201 because a new state was created
    if orchestration_result.status == schemas.responses.SetStateStatus.WAIT:
        response.status_code = status.HTTP_200_OK
    else:
        response.status_code = status.HTTP_201_CREATED

    return orchestration_result
