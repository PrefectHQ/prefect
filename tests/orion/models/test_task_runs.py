from uuid import uuid4

import pytest
import pendulum
import sqlalchemy as sa

from prefect.orion import models, schemas
from prefect.orion.schemas.states import Scheduled


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
    async def test_read_task_runs_filters_by_task_run_ids(self, flow_run, session):
        task_run_1 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(flow_run_id=flow_run.id, task_key="my-key"),
        )
        task_run_2 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(flow_run_id=flow_run.id, task_key="my-key-2"),
        )

        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(ids=[task_run_1.id]),
        )
        assert len(result) == 1
        assert result[0].id == task_run_1.id

        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                ids=[task_run_1.id, task_run_2.id]
            ),
        )
        assert {res.id for res in result} == {task_run_1.id, task_run_2.id}

        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(ids=[uuid4()]),
        )
        assert len(result) == 0

    async def test_read_task_runs_filters_by_task_run_tags(self, flow_run, session):
        task_run_1 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id, task_key="my-key", tags=["db", "blue"]
            ),
        )
        task_run_2 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id, task_key="my-key-2", tags=["db"]
            ),
        )

        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(tags_all=["db", "blue"]),
        )
        assert len(result) == 1
        assert result[0].id == task_run_1.id

        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(tags_all=["db"]),
        )
        assert {res.id for res in result} == {task_run_1.id, task_run_2.id}

        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(tags_all=["green"]),
        )
        assert len(result) == 0

    async def test_read_task_runs_filters_by_task_run_states(self, flow_run, session):
        task_run_1 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(flow_run_id=flow_run.id, task_key="my-key"),
        )
        task_run_state_1 = await models.task_run_states.orchestrate_task_run_state(
            session=session,
            task_run_id=task_run_1.id,
            state=Scheduled(),
        )
        task_run_2 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(flow_run_id=flow_run.id, task_key="my-key-2"),
        )
        task_run_state_2 = await models.task_run_states.orchestrate_task_run_state(
            session=session,
            task_run_id=task_run_2.id,
            state=schemas.states.Completed(),
        )

        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(states=["SCHEDULED"]),
        )
        assert len(result) == 1
        assert result[0].id == task_run_1.id

        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                states=["SCHEDULED", "COMPLETED"]
            ),
        )
        assert {res.id for res in result} == {task_run_1.id, task_run_2.id}

        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(states=["RUNNING"]),
        )
        assert len(result) == 0

    async def test_read_task_runs_filters_by_task_run_start_time_before(
        self, flow_run, session
    ):
        now = pendulum.now()
        task_run_1 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(flow_run_id=flow_run.id, task_key="my-key"),
        )
        task_run_state_1 = await models.task_run_states.orchestrate_task_run_state(
            session=session,
            task_run_id=task_run_1.id,
            state=schemas.states.State(
                type="SCHEDULED", timestamp=now.subtract(minutes=1)
            ),
        )
        task_run_2 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(flow_run_id=flow_run.id, task_key="my-key-2"),
        )
        task_run_state_2 = await models.task_run_states.orchestrate_task_run_state(
            session=session,
            task_run_id=task_run_2.id,
            state=Scheduled(timestamp=now.add(minutes=1)),
        )

        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(start_time_before=now),
        )
        assert len(result) == 1
        assert result[0].id == task_run_1.id

        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                start_time_before=now.add(minutes=10)
            ),
        )
        assert {res.id for res in result} == {task_run_1.id, task_run_2.id}

    async def test_read_task_runs_filters_by_task_run_start_time_after(
        self, flow_run, session
    ):
        now = pendulum.now()
        task_run_1 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(flow_run_id=flow_run.id, task_key="my-key"),
        )
        task_run_state_1 = await models.task_run_states.orchestrate_task_run_state(
            session=session,
            task_run_id=task_run_1.id,
            state=schemas.states.State(
                type="SCHEDULED", timestamp=now.subtract(minutes=1)
            ),
        )
        task_run_2 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(flow_run_id=flow_run.id, task_key="my-key-2"),
        )
        task_run_state_2 = await models.task_run_states.orchestrate_task_run_state(
            session=session,
            task_run_id=task_run_2.id,
            state=Scheduled(timestamp=now.add(minutes=1)),
        )

        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(start_time_after=now),
        )
        assert len(result) == 1
        assert result[0].id == task_run_2.id

        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                start_time_after=now.subtract(minutes=10)
            ),
        )
        assert {res.id for res in result} == {task_run_1.id, task_run_2.id}

    async def test_read_task_runs_filters_by_flow_run_criteria(self, flow_run, session):
        task_run_1 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(flow_run_id=flow_run.id, task_key="my-key"),
        )
        task_run_2 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(flow_run_id=flow_run.id, task_key="my-key-2"),
        )

        result = await models.task_runs.read_task_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(ids=[flow_run.id]),
        )
        assert {res.id for res in result} == {task_run_1.id, task_run_2.id}

        result = await models.task_runs.read_task_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(ids=[uuid4()]),
        )
        assert len(result) == 0

    async def test_read_task_runs_filters_by_flow_criteria(self, flow_run, session):
        task_run_1 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(flow_run_id=flow_run.id, task_key="my-key"),
        )
        task_run_2 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(flow_run_id=flow_run.id, task_key="my-key-2"),
        )

        result = await models.task_runs.read_task_runs(
            session=session,
            flow_filter=schemas.filters.FlowFilter(ids=[flow_run.flow_id]),
        )
        assert {res.id for res in result} == {task_run_1.id, task_run_2.id}

        result = await models.task_runs.read_task_runs(
            session=session,
            flow_filter=schemas.filters.FlowFilter(ids=[uuid4()]),
        )
        assert len(result) == 0

    async def test_read_task_runs_filters_by_flow_and_flow_run_criteria(
        self, flow_run, session
    ):
        task_run_1 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(flow_run_id=flow_run.id, task_key="my-key"),
        )
        task_run_2 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(flow_run_id=flow_run.id, task_key="my-key-2"),
        )

        result = await models.task_runs.read_task_runs(
            session=session,
            flow_filter=schemas.filters.FlowFilter(ids=[flow_run.flow_id]),
            flow_run_filter=schemas.filters.FlowRunFilter(ids=[flow_run.id]),
        )
        assert {res.id for res in result} == {task_run_1.id, task_run_2.id}

        result = await models.task_runs.read_task_runs(
            session=session,
            flow_filter=schemas.filters.FlowFilter(ids=[uuid4()]),
            flow_run_filter=schemas.filters.FlowRunFilter(ids=[flow_run.id]),
        )
        assert len(result) == 0

        result = await models.task_runs.read_task_runs(
            session=session,
            flow_filter=schemas.filters.FlowFilter(ids=[flow_run.flow_id]),
            flow_run_filter=schemas.filters.FlowRunFilter(ids=[uuid4()]),
        )
        assert len(result) == 0

    async def test_read_task_runs_applies_limit(self, flow_run, session):
        task_run_1 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(flow_run_id=flow_run.id, task_key="my-key"),
        )
        task_run_2 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(flow_run_id=flow_run.id, task_key="my-key-2"),
        )
        result = await models.task_runs.read_task_runs(session=session, limit=1)
        assert len(result) == 1

    async def test_read_task_runs_applies_offset(self, flow_run, session):
        task_run_1 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(flow_run_id=flow_run.id, task_key="my-key"),
        )
        task_run_2 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(flow_run_id=flow_run.id, task_key="my-key-2"),
        )
        result_1 = await models.task_runs.read_task_runs(
            session=session, offset=0, limit=1
        )
        result_2 = await models.task_runs.read_task_runs(
            session=session, offset=1, limit=1
        )

        assert {result_1[0].id, result_2[0].id} == {task_run_1.id, task_run_2.id}

    async def test_read_task_runs_applies_sort(self, flow_run, session):
        now = pendulum.now()
        task_run_1 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id,
                task_key="my-key",
                expected_start_time=now.subtract(minutes=5),
            ),
        )
        task_run_2 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id,
                task_key="my-key",
                expected_start_time=now.add(minutes=5),
            ),
        )

        result = await models.task_runs.read_task_runs(
            session=session,
            limit=1,
            sort=[schemas.sorting.TaskRunSort.expected_start_time_desc.as_sql_sort()],
        )
        assert result[0].id == task_run_2.id


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
