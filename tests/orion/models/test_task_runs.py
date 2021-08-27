import sqlalchemy as sa
import pytest
from uuid import uuid4
from prefect.orion import models, schemas


class TestCreateTaskRun:
    async def test_create_task_run_succeeds(self, flow_run, session):
        fake_task_run = schemas.core.TaskRun(flow_run_id=flow_run.id, task_key="my-key")
        task_run = await models.task_runs.create_task_run(
            session=session, task_run=fake_task_run
        )
        assert task_run.flow_run_id == flow_run.id
        assert task_run.task_key == "my-key"

    async def test_create_flow_run_has_no_default_state(self, flow_run, session):
        task_run = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.actions.TaskRunCreate(
                flow_run_id=flow_run.id, task_key="my-key"
            ),
        )
        assert task_run.flow_run_id == flow_run.id
        assert task_run.state is None

    async def test_create_task_run_with_state(self, flow_run, session):
        state_id = uuid4()
        task_run = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.actions.TaskRunCreate(
                flow_run_id=flow_run.id,
                task_key="my-key",
                state=schemas.states.State(
                    id=state_id, type="RUNNING", name="My Running State"
                ),
            ),
        )
        assert task_run.flow_run_id == flow_run.id
        assert task_run.state.id == state_id

        query = await session.execute(
            sa.select(models.orm.TaskRunState).filter_by(id=state_id)
        )
        result = query.scalar()
        assert result.id == state_id
        assert result.name == "My Running State"


class TestReadTaskRun:
    async def test_read_task_run(self, task_run, session):
        read_task_run = await models.task_runs.read_task_run(
            session=session, task_run_id=task_run.id
        )
        assert task_run == read_task_run

    async def test_read_task_run_returns_none_if_does_not_exist(self, session):
        assert (
            await models.task_runs.read_task_run(session=session, task_run_id=uuid4())
        ) is None


class TestReadTaskRuns:
    @pytest.fixture
    async def task_runs(self, flow_run, session):
        fake_task_run_0 = schemas.core.TaskRun(
            flow_run_id=flow_run.id, task_key="my-key"
        )
        task_run_0 = await models.task_runs.create_task_run(
            session=session, task_run=fake_task_run_0
        )
        fake_task_run_1 = schemas.core.TaskRun(
            flow_run_id=flow_run.id, task_key="my-key-2"
        )
        task_run_1 = await models.task_runs.create_task_run(
            session=session, task_run=fake_task_run_1
        )
        await session.commit()
        return [task_run_0, task_run_1]

    async def test_read_task_runs(self, task_runs, flow_run, session):
        read_task_runs = await models.task_runs.read_task_runs(
            session=session, flow_run_id=flow_run.id
        )
        assert len(read_task_runs) == len(task_runs)

    async def test_read_task_runs_filters_by_flow_run(self, session):
        read_task_runs = await models.task_runs.read_task_runs(
            session=session, flow_run_id=uuid4()
        )
        assert len(read_task_runs) == 0


class TestDeleteTaskRun:
    async def test_delete_task_run(self, task_run, session):
        assert await models.task_runs.delete_task_run(
            session=session, task_run_id=task_run.id
        )

        # make sure the task run is deleted
        assert (
            await models.task_runs.read_task_run(
                session=session, task_run_id=task_run.id
            )
        ) is None

    async def test_delete_task_run_returns_false_if_does_not_exist(self, session):
        assert not (
            await models.task_runs.delete_task_run(session=session, task_run_id=uuid4())
        )
