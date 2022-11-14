import datetime
from uuid import uuid4

import pendulum
import pytest

from prefect.orion import models, schemas
from prefect.orion.exceptions import ObjectNotFoundError
from prefect.orion.orchestration.dependencies import (
    provide_task_orchestration_parameters,
    provide_task_policy,
    temporary_task_orchestration_parameters,
    temporary_task_policy,
)
from prefect.orion.orchestration.policies import BaseOrchestrationPolicy
from prefect.orion.orchestration.rules import (
    ALL_ORCHESTRATION_STATES,
    BaseOrchestrationRule,
)
from prefect.orion.schemas.states import Failed, Running, Scheduled, StateType


class TestCreateTaskRunState:
    async def test_create_task_run_state_succeeds(self, task_run, session):
        task_run_state = (
            await models.task_runs.set_task_run_state(
                session=session,
                task_run_id=task_run.id,
                state=Running(),
            )
        ).state
        assert task_run_state.name == "Running"
        assert task_run_state.type == StateType.RUNNING
        assert task_run_state.state_details.task_run_id == task_run.id

    async def test_run_details_are_updated_entering_running(self, task_run, session):
        trs = await models.task_runs.set_task_run_state(
            session=session,
            task_run_id=task_run.id,
            state=Scheduled(),
        )

        await session.refresh(task_run)

        assert task_run.start_time is None
        assert task_run.run_count == 0

        dt = pendulum.now("UTC")
        trs2 = await models.task_runs.set_task_run_state(
            session=session,
            task_run_id=task_run.id,
            state=Running(timestamp=dt),
        )
        await session.refresh(task_run)
        assert task_run.start_time == dt
        assert task_run.run_count == 1
        assert task_run.total_run_time == datetime.timedelta(0)

        dt2 = pendulum.now("UTC")
        trs3 = await models.task_runs.set_task_run_state(
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
        task_run.empirical_policy.retries = 1
        await session.flush()

        (
            await models.task_runs.set_task_run_state(
                session=session,
                task_run_id=task_run.id,
                state=Running(),
                task_policy=await provide_task_policy(),
            )
        ).state

        new_state = (
            await models.task_runs.set_task_run_state(
                session=session,
                task_run_id=task_run.id,
                state=Failed(),
                task_policy=await provide_task_policy(),
            )
        ).state

        assert new_state.name == "AwaitingRetry"
        assert new_state.type == StateType.SCHEDULED

    async def test_failed_doesnt_retry_if_flag_set(self, task_run, client, session):
        # set max retries to 1
        # copy to trigger ORM updates
        task_run.empirical_policy = task_run.empirical_policy.copy()
        task_run.empirical_policy.retries = 1
        await session.flush()

        (
            await models.task_runs.set_task_run_state(
                session=session,
                task_run_id=task_run.id,
                state=Running(),
            )
        ).state

        new_state = (
            await models.task_runs.set_task_run_state(
                session=session,
                task_run_id=task_run.id,
                state=Failed(),
                force=True,
            )
        ).state

        assert new_state.type == StateType.FAILED

    async def test_database_is_not_updated_when_no_transition_takes_place(
        self, task_run, session
    ):

        # place the run in a scheduled state in the future
        trs = await models.task_runs.set_task_run_state(
            session=session,
            task_run_id=task_run.id,
            state=Scheduled(scheduled_time=pendulum.now().add(months=1)),
            task_policy=await provide_task_policy(),
        )

        # attempt to put the run in a pending state, which will tell the transition to WAIT
        trs2 = await models.task_runs.set_task_run_state(
            session=session,
            task_run_id=task_run.id,
            state=Running(),
            task_policy=await provide_task_policy(),
        )

        assert trs2.status == schemas.responses.SetStateStatus.WAIT
        # the original state remains in place
        await session.refresh(task_run)
        assert task_run.state.id == trs.state.id

    async def test_no_orchestration_with_injected_empty_policy(self, task_run, session):
        class EmptyPolicy(BaseOrchestrationPolicy):
            def priority():
                return []

        with temporary_task_policy(EmptyPolicy):
            # place the run in a scheduled state in the future
            trs = await models.task_runs.set_task_run_state(
                session=session,
                task_run_id=task_run.id,
                state=Scheduled(scheduled_time=pendulum.now().add(months=1)),
                task_policy=await provide_task_policy(),
            )

            # put the run in a pending state, which succeeds due to injected orchestration
            trs2 = await models.task_runs.set_task_run_state(
                session=session,
                task_run_id=task_run.id,
                state=Running(),
                task_policy=await provide_task_policy(),
            )

            assert trs2.status == schemas.responses.SetStateStatus.ACCEPT
            # the original state remains in place
            await session.refresh(task_run)
            assert task_run.state.id != trs.state.id

    async def test_orchestration_with_injected_parameters(self, task_run, session):
        class AbortingRule(BaseOrchestrationRule):
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

            async def before_transition(self, initial_state, proposed_state, context):
                # this rule mutates the proposed state type, but won't fizzle itself upon exiting
                if context.parameters.get("special-signal") == "abort":
                    await self.abort_transition("wow, aborting this transition")

        class AbortingPolicy(BaseOrchestrationPolicy):
            def priority():
                return [AbortingRule]

        with temporary_task_orchestration_parameters({"special-signal": "abort"}):
            with temporary_task_policy(AbortingPolicy):
                trs = await models.task_runs.set_task_run_state(
                    session=session,
                    task_run_id=task_run.id,
                    state=Scheduled(scheduled_time=pendulum.now().add(months=1)),
                    task_policy=await provide_task_policy(),
                    orchestration_parameters=await provide_task_orchestration_parameters(),
                )

                assert trs.status == schemas.responses.SetStateStatus.ABORT

    async def test_object_not_found_if_id_not_found(self, session):
        with pytest.raises(ObjectNotFoundError):
            await models.task_runs.set_task_run_state(
                session=session,
                task_run_id=uuid4(),
                state=Running(),
            )


class TestReadTaskRunState:
    async def test_read_task_run_state(self, task_run, session):
        # create a task run to read
        task_run_state = (
            await models.task_runs.set_task_run_state(
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
            await models.task_runs.set_task_run_state(
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
