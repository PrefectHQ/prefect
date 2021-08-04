import pytest
from uuid import uuid4
import pendulum
from prefect.orion import models, schemas


class TestCreateTaskRunState:
    async def test_create_task_run_state_succeeds(self, task_run, database_session):
        fake_task_run_state = schemas.actions.StateCreate(type="RUNNING")
        task_run_state = await models.task_run_states.create_task_run_state(
            session=database_session,
            task_run_id=task_run.id,
            state=fake_task_run_state,
        )
        assert task_run_state.name == fake_task_run_state.name
        assert task_run_state.type == fake_task_run_state.type
        assert task_run_state.task_run_id == task_run.id
        assert task_run_state.state_details.task_run_id == task_run.id

    async def test_create_task_run_state_twice_succeeds(
        self, task_run, database_session
    ):
        fake_task_run_state = schemas.actions.StateCreate(
            type="SCHEDULED",
        )
        task_run_state = await models.task_run_states.create_task_run_state(
            session=database_session,
            task_run_id=task_run.id,
            state=fake_task_run_state,
        )

        another_fake_task_run_state = schemas.actions.StateCreate(type="RUNNING")
        another_task_run_state = await models.task_run_states.create_task_run_state(
            session=database_session,
            task_run_id=task_run.id,
            state=another_fake_task_run_state,
        )
        assert another_task_run_state.run_details.previous_state_id == task_run_state.id


class TestReadTaskRunState:
    async def test_read_task_run_state(self, database_session):
        # create a task run to read
        fake_task_run_state = schemas.actions.StateCreate(type="RUNNING")
        task_run_state = await models.task_run_states.create_task_run_state(
            session=database_session,
            task_run_id=uuid4(),
            state=fake_task_run_state,
        )
        read_task_run_state = await models.task_run_states.read_task_run_state(
            session=database_session, task_run_state_id=task_run_state.id
        )
        assert task_run_state == read_task_run_state

    async def test_read_task_run_state_returns_none_if_does_not_exist(
        self, database_session
    ):
        assert (
            await models.task_run_states.read_task_run_state(
                session=database_session, task_run_state_id=uuid4()
            )
        ) is None


class TestReadTaskRunStates:
    async def test_task_run_states(self, database_session, task_run, task_run_states):
        task_run_states_by_task_run_id = (
            await models.task_run_states.read_task_run_states(
                session=database_session, task_run_id=task_run.id
            )
        )
        assert len(task_run_states_by_task_run_id) == len(task_run_states)

    async def test_task_run_states_filters_by_task_run_id(self, database_session):
        # query for states using a random task run id
        task_run_states_by_task_run_id = (
            await models.task_run_states.read_task_run_states(
                session=database_session, task_run_id=uuid4()
            )
        )
        assert len(task_run_states_by_task_run_id) == 0


class TestDeleteTaskRunState:
    async def test_delete_task_run_state(self, database_session):
        # create a task run to read
        fake_task_run_state = schemas.actions.StateCreate(type="RUNNING")
        task_run_state = await models.task_run_states.create_task_run_state(
            session=database_session,
            task_run_id=uuid4(),
            state=fake_task_run_state,
        )

        assert await models.task_run_states.delete_task_run_state(
            session=database_session, task_run_state_id=task_run_state.id
        )

        # make sure the task run state is deleted
        assert (
            await models.task_run_states.read_task_run_state(
                session=database_session, task_run_state_id=task_run_state.id
            )
        ) is None

    async def test_delete_task_run_state_returns_false_if_does_not_exist(
        self, database_session
    ):
        assert not (
            await models.task_run_states.delete_task_run_state(
                session=database_session, task_run_state_id=uuid4()
            )
        )
