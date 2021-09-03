import contextlib
import pendulum
import pytest
from itertools import product
from unittest.mock import MagicMock

from prefect.orion import schemas
from prefect.orion.models import orm
from prefect.orion.orchestration.rules import OrchestrationContext
from prefect.orion.orchestration.core_policy import WaitForScheduledTime
from prefect.orion.schemas import states


async def create_task_run_state(
    session, task_run, state_type: states.StateType, state_details=None
):
    if state_type is None:
        return None
    state_details = dict() if state_details is None else state_details

    if (
        state_type == states.StateType.SCHEDULED
        and "scheduled_time" not in state_details
    ):
        state_details.update({"scheduled_time": pendulum.now()})

    new_state = schemas.actions.StateCreate(
        type=state_type,
        timestamp=pendulum.now("UTC").subtract(seconds=5),
        state_details=state_details,
    )

    orm_state = orm.TaskRunState(
        task_run_id=task_run.id,
        **new_state.dict(shallow=True),
    )

    session.add(orm_state)
    await session.flush()
    return orm_state.as_state()


class TestWaitForScheduledTimeRule:
    async def test_late_scheduled_states_just_run(self, session, task_run):
        initial_state_type = states.StateType.SCHEDULED
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        scheduled_state = await create_task_run_state(
            session,
            task_run,
            initial_state_type,
            {"scheduled_time": pendulum.now().subtract(minutes=5)},
        )
        proposed_state = await create_task_run_state(
            session,
            task_run,
            proposed_state_type,
        )

        ctx = OrchestrationContext(
            initial_state=scheduled_state,
            proposed_state=proposed_state,
            session=session,
            run=schemas.core.TaskRun.from_orm(task_run),
            task_run_id=task_run.id,
        )

        async with WaitForScheduledTime(ctx, *intended_transition) as ctx:
            validated_orm_state = orm.TaskRunState(
                task_run_id=ctx.task_run_id,
                **ctx.proposed_state.dict(shallow=True),
            )
            ctx.validated_state = validated_orm_state.as_state()

        assert ctx.validated_state_type == proposed_state_type

    async def test_early_scheduled_states_are_delayed(self, session, task_run):
        initial_state_type = states.StateType.SCHEDULED
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        scheduled_state = await create_task_run_state(
            session,
            task_run,
            initial_state_type,
            {"scheduled_time": pendulum.now().add(minutes=5)},
        )
        proposed_state = await create_task_run_state(
            session,
            task_run,
            proposed_state_type,
        )

        ctx = OrchestrationContext(
            initial_state=scheduled_state,
            proposed_state=proposed_state,
            session=session,
            run=schemas.core.TaskRun.from_orm(task_run),
            task_run_id=task_run.id,
        )

        async with WaitForScheduledTime(ctx, *intended_transition) as ctx:
            if ctx.proposed_state:
                validated_orm_state = orm.TaskRunState(
                    task_run_id=ctx.task_run_id,
                    **ctx.proposed_state.dict(shallow=True),
                )
                ctx.validated_state = validated_orm_state.as_state()

            assert ctx.response_status == schemas.responses.SetStateStatus.WAIT
            assert ctx.proposed_state is None
            assert abs(ctx.response_details.delay_seconds - 300) < 2
