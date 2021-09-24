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

    async def test_create_task_run_with_dynamic_key(self, flow_run, session):
        fake_task_run = schemas.core.TaskRun(
            flow_run_id=flow_run.id, task_key="my-key", dynamic_key="TB12"
        )
        task_run = await models.task_runs.create_task_run(
            session=session, task_run=fake_task_run
        )
        assert task_run.flow_run_id == flow_run.id
        assert task_run.task_key == "my-key"
        assert task_run.dynamic_key == "TB12"

        task_run_2 = await models.task_runs.create_task_run(
            session=session, task_run=fake_task_run
        )
        assert task_run_2.id == task_run.id

    async def test_create_task_run_has_no_default_state(self, flow_run, session):
        task_run = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(flow_run_id=flow_run.id, task_key="my-key"),
        )
        assert task_run.flow_run_id == flow_run.id
        assert task_run.state is None

    async def test_create_task_run_with_state(self, flow_run, session):
        state_id = uuid4()
        task_run = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
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

        # creating a different task run without a dynamic key should create
        # a new state
        new_task_run = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id,
                task_key="my-key",
                state=schemas.states.State(type="SCHEDULED", name="My Scheduled State"),
            ),
        )
        assert new_task_run.flow_run_id == flow_run.id
        assert new_task_run.state.id != task_run.state.id

        query = await session.execute(
            sa.select(models.orm.TaskRunState).filter_by(id=new_task_run.state.id)
        )
        result = query.scalar()
        assert result.id != state_id
        assert result.name == "My Scheduled State"

    async def test_create_task_run_with_state_and_dynamic_key(self, flow_run, session):
        scheduled_state_id = uuid4()
        running_state_id = uuid4()

        scheduled_task_run = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id,
                task_key="my-key",
                dynamic_key="TB12",
                state=schemas.states.State(
                    id=scheduled_state_id, type="SCHEDULED", name="My Scheduled State"
                ),
            ),
        )
        assert scheduled_task_run.flow_run_id == flow_run.id
        assert scheduled_task_run.state.id == scheduled_state_id

        running_task_run = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id,
                task_key="my-key",
                dynamic_key="TB12",
                state=schemas.states.State(
                    id=running_state_id, type="RUNNING", name="My Running State"
                ),
            ),
        )
        assert running_task_run.flow_run_id == flow_run.id
        assert running_task_run.state.id == scheduled_state_id

        query = await session.execute(
            sa.select(models.orm.TaskRunState).filter_by(id=scheduled_state_id)
        )
        result = query.scalar()
        assert result.id == scheduled_state_id
        assert result.name == "My Scheduled State"


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
    async def test_read_task_runs_filters_by_task_run_ids_any(self, flow_run, session):
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
            task_run_filter=schemas.filters.TaskRunFilter(
                id=schemas.filters.TaskRunFilterId(any_=[task_run_1.id])
            ),
        )
        assert {res.id for res in result} == {task_run_1.id}

        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                id=schemas.filters.TaskRunFilterId(any_=[task_run_1.id, task_run_2.id])
            ),
        )
        assert {res.id for res in result} == {task_run_1.id, task_run_2.id}

        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                id=schemas.filters.TaskRunFilterId(any_=[uuid4()])
            ),
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
        task_run_3 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id,
                task_key="my-key-2",
            ),
        )

        # any_
        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                tags=schemas.filters.TaskRunFilterTags(all_=["db", "blue"])
            ),
        )
        assert {res.id for res in result} == {task_run_1.id}

        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                tags=schemas.filters.TaskRunFilterTags(all_=["db"])
            ),
        )
        assert {res.id for res in result} == {task_run_1.id, task_run_2.id}

        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                tags=schemas.filters.TaskRunFilterTags(all_=["green"])
            ),
        )
        assert len(result) == 0

        # is_null_
        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                tags=schemas.filters.TaskRunFilterTags(is_null_=True)
            ),
        )
        assert {res.id for res in result} == {task_run_3.id}
        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                tags=schemas.filters.TaskRunFilterTags(is_null_=False)
            ),
        )
        assert {res.id for res in result} == {task_run_1.id, task_run_2.id}

    async def test_read_task_runs_filters_by_task_run_states_any(
        self, flow_run, session
    ):
        task_run_1 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(flow_run_id=flow_run.id, task_key="my-key"),
        )
        task_run_state_1 = await models.task_runs.set_task_run_state(
            session=session,
            task_run_id=task_run_1.id,
            state=Scheduled(),
        )
        task_run_2 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(flow_run_id=flow_run.id, task_key="my-key-2"),
        )
        task_run_state_2 = await models.task_runs.set_task_run_state(
            session=session,
            task_run_id=task_run_2.id,
            state=schemas.states.Completed(),
        )

        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                state_type=schemas.filters.TaskRunFilterStateType(any_=["SCHEDULED"])
            ),
        )
        assert {res.id for res in result} == {task_run_1.id}

        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                state_type=schemas.filters.TaskRunFilterStateType(
                    any_=["SCHEDULED", "COMPLETED"]
                )
            ),
        )
        assert {res.id for res in result} == {task_run_1.id, task_run_2.id}

        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                state_type=schemas.filters.TaskRunFilterStateType(any_=["RUNNING"])
            ),
        )
        assert len(result) == 0

    async def test_read_task_runs_filters_by_task_run_start_time(
        self, flow_run, session
    ):
        now = pendulum.now()
        task_run_1 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id,
                task_key="my-key",
                start_time=now.subtract(minutes=1),
            ),
        )
        task_run_2 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id,
                task_key="my-key-2",
                start_time=now.add(minutes=1),
            ),
        )
        task_run_3 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id,
                task_key="my-key-2",
            ),
        )

        # before_
        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                start_time=schemas.filters.TaskRunFilterStartTime(before_=now)
            ),
        )
        assert {res.id for res in result} == {task_run_1.id}

        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                start_time=schemas.filters.TaskRunFilterStartTime(
                    before_=now.add(minutes=10)
                )
            ),
        )
        assert {res.id for res in result} == {task_run_1.id, task_run_2.id}

        # after_
        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                start_time=schemas.filters.TaskRunFilterStartTime(after_=now)
            ),
        )
        assert {res.id for res in result} == {task_run_2.id}

        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                start_time=schemas.filters.TaskRunFilterStartTime(
                    after_=now.subtract(minutes=10)
                )
            ),
        )
        assert {res.id for res in result} == {task_run_1.id, task_run_2.id}

        # before_ AND after_
        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                start_time=schemas.filters.TaskRunFilterStartTime(
                    before_=now, after_=now.subtract(minutes=10)
                )
            ),
        )
        assert {res.id for res in result} == {task_run_1.id}

        # is_null_
        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                start_time=schemas.filters.TaskRunFilterStartTime(is_null_=True)
            ),
        )
        assert {res.id for res in result} == {task_run_3.id}
        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                start_time=schemas.filters.TaskRunFilterStartTime(is_null_=False)
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
            flow_run_filter=schemas.filters.FlowRunFilter(
                id=schemas.filters.FlowRunFilterId(any_=[flow_run.id])
            ),
        )
        assert {res.id for res in result} == {task_run_1.id, task_run_2.id}

        result = await models.task_runs.read_task_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                id=schemas.filters.FlowRunFilterId(any_=[uuid4()])
            ),
        )
        assert len(result) == 0

    async def test_read_task_runs_filters_by_flow_criteria(
        self, flow, flow_run, session
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
            flow_filter=schemas.filters.FlowFilter(
                id=schemas.filters.FlowFilterId(any_=[flow.id])
            ),
        )
        assert {res.id for res in result} == {task_run_1.id, task_run_2.id}

        result = await models.task_runs.read_task_runs(
            session=session,
            flow_filter=schemas.filters.FlowFilter(
                id=schemas.filters.FlowFilterId(any_=[uuid4()])
            ),
        )
        assert len(result) == 0

    async def test_read_task_runs_filters_by_flow_and_flow_run_criteria(
        self, flow, flow_run, session
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
            flow_filter=schemas.filters.FlowFilter(
                id=schemas.filters.FlowFilterId(any_=[flow.id])
            ),
            flow_run_filter=schemas.filters.FlowRunFilter(
                id=schemas.filters.FlowRunFilterId(any_=[flow_run.id])
            ),
        )
        assert {res.id for res in result} == {task_run_1.id, task_run_2.id}

        result = await models.task_runs.read_task_runs(
            session=session,
            flow_filter=schemas.filters.FlowFilter(
                id=schemas.filters.FlowFilterId(any_=[uuid4()])
            ),
            flow_run_filter=schemas.filters.FlowRunFilter(
                id=schemas.filters.FlowRunFilterId(any_=[flow_run.id])
            ),
        )
        assert len(result) == 0

        result = await models.task_runs.read_task_runs(
            session=session,
            flow_filter=schemas.filters.FlowFilter(
                id=schemas.filters.FlowFilterId(any_=[flow.id])
            ),
            flow_run_filter=schemas.filters.FlowRunFilter(
                id=schemas.filters.FlowRunFilterId(any_=[uuid4()])
            ),
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
            sort=schemas.sorting.TaskRunSort.EXPECTED_START_TIME_DESC,
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
