import pytest
from uuid import uuid4
from prefect.orion import models, schemas


class TestCreateTaskRun:
    async def test_create_task_run_succeeds(self, flow_run, database_session):
        fake_task_run = schemas.actions.TaskRunCreate(
            flow_run_id=flow_run.id, task_key="my-key"
        )
        task_run = await models.task_runs.create_task_run(
            session=database_session, task_run=fake_task_run
        )
        assert str(task_run.flow_run_id) == flow_run.id
        assert task_run.task_key == "my-key"


class TestReadTaskRun:
    async def test_read_task_run(self, task_run, database_session):
        read_task_run = await models.task_runs.read_task_run(
            session=database_session, id=task_run.id
        )
        assert task_run == read_task_run

    async def test_read_task_run_returns_none_if_does_not_exist(self, database_session):
        assert (
            await models.task_runs.read_task_run(session=database_session, id=uuid4())
        ) is None


# class TestReadTaskRuns:
#     @pytest.fixture
#     async def task_runs(self, database_session):
#         fake_task_run_0 = schemas.actions.TaskRunCreate(
#             task_id=uuid4(), task_version="0.1"
#         )
#         task_run_0 = await models.task_runs.create_task_run(
#             session=database_session, task_run=fake_task_run_0
#         )
#         fake_task_run_1 = schemas.actions.TaskRunCreate(
#             task_id=uuid4(), task_version="0.1"
#         )
#         task_run_1 = await models.task_runs.create_task_run(
#             session=database_session, task_run=fake_task_run_1
#         )
#         return [task_run_0, task_run_1]

#     async def test_read_task_runs(self, task_runs, database_session):
#         read_task_runs = await models.task_runs.read_task_runs(session=database_session)
#         assert len(read_task_runs) == len(task_runs)

#     async def test_read_task_runs_applies_limit(self, task_runs, database_session):
#         read_task_runs = await models.task_runs.read_task_runs(
#             session=database_session, limit=1
#         )
#         assert len(read_task_runs) == 1

#     async def test_read_task_runs_returns_empty_list(self, database_session):
#         read_task_runs = await models.task_runs.read_task_runs(session=database_session)
#         assert len(read_task_runs) == 0


class TestDeleteTaskRun:
    async def test_delete_task_run(self, task_run, database_session):
        assert await models.task_runs.delete_task_run(
            session=database_session, id=task_run.id
        )

        # make sure the task run is deleted
        assert (
            await models.task_runs.read_task_run(
                session=database_session, id=task_run.id
            )
        ) is None

    async def test_delete_task_run_returns_false_if_does_not_exist(
        self, database_session
    ):
        assert not (
            await models.task_runs.delete_task_run(session=database_session, id=uuid4())
        )
