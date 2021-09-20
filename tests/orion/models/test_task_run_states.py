import datetime
from uuid import uuid4

import pendulum
import pytest

from prefect.orion import models
from prefect.orion.schemas import states
from prefect.orion.schemas.states import Failed, Running, Scheduled, State, StateType


class TestCreateTaskRunState:
    async def test_create_task_run_state_succeeds(self, task_run, session):
        task_run_state = (
            await models.task_run_states.orchestrate_task_run_state(
                session=session,
                task_run_id=task_run.id,
                state=Running(),
            )
        ).state
        assert task_run_state.name == "Running"
        assert task_run_state.type == StateType.RUNNING

    async def test_run_details_are_updated_entering_running(self, task_run, session):
        trs = await models.task_run_states.orchestrate_task_run_state(
            session=session,
            task_run_id=task_run.id,
            state=Scheduled(),
        )

        await session.refresh(task_run)

        assert task_run.start_time is None
        assert task_run.run_count == 0

        dt = pendulum.now("UTC")
        trs2 = await models.task_run_states.orchestrate_task_run_state(
            session=session,
            task_run_id=task_run.id,
            state=Running(timestamp=dt),
        )
        await session.refresh(task_run)
        assert task_run.start_time == dt
        assert task_run.run_count == 1
        assert task_run.total_run_time == datetime.timedelta(0)

        dt2 = pendulum.now("UTC")
        trs3 = await models.task_run_states.orchestrate_task_run_state(
            session=session,
            task_run_id=task_run.id,
            state=Running(timestamp=dt2),
        )
        await session.commit()
        await session.refresh(task_run)
        assert task_run.start_time == dt
        assert task_run.run_count == 2
        assert task_run.total_run_time == (dt2 - dt)

    async def test_failed_becomes_awaiting_retry(self, task_run, client, session):
        # set max retries to 1
        # copy to trigger ORM updates
        task_run.empirical_policy = task_run.empirical_policy.copy()
        task_run.empirical_policy.max_retries = 1
        await session.flush()

        (
            await models.task_run_states.orchestrate_task_run_state(
                session=session,
                task_run_id=task_run.id,
                state=Running(),
            )
        ).state

        new_state = (
            await models.task_run_states.orchestrate_task_run_state(
                session=session,
                task_run_id=task_run.id,
                state=Failed(),
            )
        ).state

        assert new_state.name == "Awaiting Retry"
        assert new_state.type == StateType.SCHEDULED

    async def test_failed_doesnt_retry_if_flag_set(self, task_run, client, session):
        # set max retries to 1
        # copy to trigger ORM updates
        task_run.empirical_policy = task_run.empirical_policy.copy()
        task_run.empirical_policy.max_retries = 1
        await session.flush()

        (
            await models.task_run_states.orchestrate_task_run_state(
                session=session,
                task_run_id=task_run.id,
                state=Running(),
            )
        ).state

        new_state = (
            await models.task_run_states.orchestrate_task_run_state(
                session=session,
                task_run_id=task_run.id,
                state=Failed(),
                apply_orchestration_rules=False,
            )
        ).state

        assert new_state.type == StateType.FAILED


class TestReadTaskRunState:
    async def test_read_task_run_state(self, task_run, session):
        # create a task run to read
        task_run_state = (
            await models.task_run_states.orchestrate_task_run_state(
                session=session,
                task_run_id=task_run.id,
                state=Running(),
            )
        ).state

        read_task_run_state = await models.task_run_states.read_task_run_state(
            session=session, task_run_state_id=task_run_state.id
        )
        assert task_run_state == read_task_run_state.as_state()

    async def test_read_task_run_state_returns_none_if_does_not_exist(self, session):
        result = await models.task_run_states.read_task_run_state(
            session=session, task_run_state_id=uuid4()
        )
        assert result is None


class TestReadTaskRunStates:
    async def test_task_run_states(self, session, task_run, task_run_states):
        task_run_states_by_task_run_id = (
            await models.task_run_states.read_task_run_states(
                session=session, task_run_id=task_run.id
            )
        )
        assert len(task_run_states_by_task_run_id) == len(task_run_states)

    async def test_task_run_states_filters_by_task_run_id(self, session):
        # query for states using a random task run id
        task_run_states_by_task_run_id = (
            await models.task_run_states.read_task_run_states(
                session=session, task_run_id=uuid4()
            )
        )
        assert len(task_run_states_by_task_run_id) == 0


class TestDeleteTaskRunState:
    async def test_delete_task_run_state(self, task_run, session):
        # create a task run to read

        task_run_state = (
            await models.task_run_states.orchestrate_task_run_state(
                session=session,
                task_run_id=task_run.id,
                state=Running(),
            )
        ).state

        assert await models.task_run_states.delete_task_run_state(
            session=session, task_run_state_id=task_run_state.id
        )

        # make sure the task run state is deleted
        result = await models.task_run_states.read_task_run_state(
            session=session, task_run_state_id=task_run_state.id
        )
        assert result is None

    async def test_delete_task_run_state_returns_false_if_does_not_exist(self, session):
        result = await models.task_run_states.delete_task_run_state(
            session=session, task_run_state_id=uuid4()
        )
        assert not result
