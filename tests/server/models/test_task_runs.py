from datetime import timedelta
from uuid import uuid4

import pytest
import sqlalchemy as sa

from prefect.server import models, schemas
from prefect.server.models import concurrency_limits, task_runs
from prefect.server.orchestration.core_policy import CoreTaskPolicy
from prefect.server.schemas.core import TaskRunResult
from prefect.server.schemas.states import Failed, Pending, Running, Scheduled
from prefect.types._datetime import now


class TestCreateTaskRun:
    async def test_create_task_run_succeeds(self, flow_run, session):
        fake_task_run = schemas.core.TaskRun(
            flow_run_id=flow_run.id, task_key="my-key", dynamic_key="0"
        )
        task_run = await models.task_runs.create_task_run(
            session=session, task_run=fake_task_run
        )
        assert task_run.flow_run_id == flow_run.id
        assert task_run.task_key == "my-key"
        assert task_run.dynamic_key == "0"

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

    async def test_create_task_run_task_inputs(self, flow_run, session):
        id1 = uuid4()
        id2 = uuid4()
        task_inputs = dict(
            x=[TaskRunResult(id=id1)],
            y=[],
            z=[TaskRunResult(id=id1), TaskRunResult(id=id2)],
        )

        task_run = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id,
                task_key="my-key",
                dynamic_key="0",
                task_inputs=task_inputs,
            ),
        )
        task_run_id = task_run.id

        await session.commit()
        session.expire_all()

        task_run_2 = await models.task_runs.read_task_run(session, task_run_id)
        assert task_run_2.task_inputs == task_inputs

    async def test_create_task_run_has_no_default_state(self, flow_run, session):
        task_run = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id, task_key="my-key", dynamic_key="0"
            ),
        )
        assert task_run.flow_run_id == flow_run.id
        assert task_run.state is None

    async def test_create_task_run_with_state(self, flow_run, session, db):
        state_id = uuid4()
        task_run = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id,
                task_key="my-key",
                dynamic_key="0",
                state=schemas.states.State(
                    id=state_id, type="RUNNING", name="My Running State"
                ),
            ),
        )
        assert task_run.flow_run_id == flow_run.id
        assert task_run.state.id == state_id

        query = await session.execute(sa.select(db.TaskRunState).filter_by(id=state_id))
        result = query.scalar()
        assert result.id == state_id
        assert result.name == "My Running State"

    async def test_create_task_run_with_state_and_dynamic_key(
        self, flow_run, session, db
    ):
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
            sa.select(db.TaskRunState).filter_by(id=scheduled_state_id)
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
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id, task_key="my-key", dynamic_key="0"
            ),
        )
        task_run_2 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id, task_key="my-key-2", dynamic_key="0"
            ),
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

    async def test_read_task_runs_filters_by_task_run_names(self, flow_run, session):
        await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id,
                task_key="my-key",
                dynamic_key="0",
                name="{task_key}",
            ),
        )
        task_run_2 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id,
                task_key="my-key-2",
                dynamic_key="0",
                name="my task run",
            ),
        )

        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                name=schemas.filters.TaskRunFilterName(any_=["my task run"])
            ),
        )
        assert {res.id for res in result} == {task_run_2.id}
        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                name=schemas.filters.TaskRunFilterName(any_=["not my task run"])
            ),
        )
        assert len(result) == 0

    async def test_read_task_runs_filters_by_task_run_tags(self, flow_run, session):
        task_run_1 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id,
                task_key="my-key",
                dynamic_key="0",
                tags=["db", "blue"],
            ),
        )
        task_run_2 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id,
                task_key="my-key-2",
                dynamic_key="0",
                tags=["db"],
            ),
        )
        task_run_3 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id,
                task_key="my-key-2",
                dynamic_key="1",
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
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id, task_key="my-key", dynamic_key="0"
            ),
        )
        await models.task_runs.set_task_run_state(
            session=session,
            task_run_id=task_run_1.id,
            state=Scheduled(),
        )
        task_run_2 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id, task_key="my-key-2", dynamic_key="0"
            ),
        )
        await models.task_runs.set_task_run_state(
            session=session,
            task_run_id=task_run_2.id,
            state=schemas.states.Completed(),
        )

        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                state=dict(
                    type=schemas.filters.TaskRunFilterStateType(any_=["SCHEDULED"])
                )
            ),
        )
        assert {res.id for res in result} == {task_run_1.id}

        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                state=dict(
                    type=schemas.filters.TaskRunFilterStateType(
                        any_=["SCHEDULED", "COMPLETED"]
                    )
                )
            ),
        )
        assert {res.id for res in result} == {task_run_1.id, task_run_2.id}

        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                state=dict(
                    type=schemas.filters.TaskRunFilterStateType(any_=["RUNNING"])
                )
            ),
        )
        assert len(result) == 0

    async def test_read_task_runs_filters_by_task_run_start_time(
        self, flow_run, session
    ):
        now_dt = now("UTC")
        task_run_1 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id,
                task_key="my-key",
                dynamic_key="0",
                start_time=now_dt - timedelta(minutes=1),
            ),
        )
        task_run_2 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id,
                task_key="my-key-2",
                dynamic_key="0",
                start_time=now_dt + timedelta(minutes=1),
            ),
        )
        task_run_3 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id, task_key="my-key-2", dynamic_key="1"
            ),
        )

        # before_
        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                start_time=schemas.filters.TaskRunFilterStartTime(before_=now_dt)
            ),
        )
        assert {res.id for res in result} == {task_run_1.id}

        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                start_time=schemas.filters.TaskRunFilterStartTime(
                    before_=now_dt + timedelta(minutes=10)
                )
            ),
        )
        assert {res.id for res in result} == {task_run_1.id, task_run_2.id}

        # after_
        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                start_time=schemas.filters.TaskRunFilterStartTime(after_=now_dt)
            ),
        )
        assert {res.id for res in result} == {task_run_2.id}

        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                start_time=schemas.filters.TaskRunFilterStartTime(
                    after_=now_dt - timedelta(minutes=10)
                )
            ),
        )
        assert {res.id for res in result} == {task_run_1.id, task_run_2.id}

        # before_ AND after_
        result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                start_time=schemas.filters.TaskRunFilterStartTime(
                    before_=now_dt, after_=now_dt - timedelta(minutes=10)
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

    async def test_read_task_runs_filters_by_flow_run_id(self, flow_run, session):
        task_run_1 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id, task_key="my-key", dynamic_key="0"
            ),
        )
        task_run_2 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=None, task_key="my-key-2", dynamic_key="0"
            ),
        )

        all_result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                flow_run_id=schemas.filters.TaskRunFilterFlowRunId(is_null_=None)
            ),
        )
        assert {res.id for res in all_result} == {task_run_1.id, task_run_2.id}

        flow_run_tasks_result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                flow_run_id=schemas.filters.TaskRunFilterFlowRunId(is_null_=False)
            ),
        )
        assert {res.id for res in flow_run_tasks_result} == {task_run_1.id}

        autonomous_tasks_result = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                flow_run_id=schemas.filters.TaskRunFilterFlowRunId(is_null_=True)
            ),
        )
        assert {res.id for res in autonomous_tasks_result} == {task_run_2.id}

    async def test_read_task_runs_filters_by_flow_run_criteria(self, flow_run, session):
        task_run_1 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id, task_key="my-key", dynamic_key="0"
            ),
        )
        task_run_2 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id, task_key="my-key-2", dynamic_key="0"
            ),
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
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id, task_key="my-key", dynamic_key="0"
            ),
        )
        task_run_2 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id, task_key="my-key-2", dynamic_key="0"
            ),
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

    async def test_read_task_runs_filters_by_deployment_criteria(
        self, deployment, session
    ):
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=deployment.flow_id,
                deployment_id=deployment.id,
                flow_version="1.0",
            ),
        )
        task_run_1 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run_1.id, task_key="my-key", dynamic_key="0"
            ),
        )

        result = await models.task_runs.read_task_runs(
            session=session,
            deployment_filter=schemas.filters.DeploymentFilter(
                id=dict(any_=[deployment.id])
            ),
        )
        assert {res.id for res in result} == {task_run_1.id}

        result = await models.task_runs.read_task_runs(
            session=session,
            deployment_filter=schemas.filters.DeploymentFilter(id=dict(any_=[uuid4()])),
        )
        assert len(result) == 0

    async def test_read_task_runs_filters_by_flow_and_flow_run_criteria(
        self, flow, flow_run, session
    ):
        task_run_1 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id, task_key="my-key", dynamic_key="0"
            ),
        )
        task_run_2 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id, task_key="my-key-2", dynamic_key="0"
            ),
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
        await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id, task_key="my-key", dynamic_key="0"
            ),
        )
        await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id, task_key="my-key-2", dynamic_key="0"
            ),
        )
        result = await models.task_runs.read_task_runs(session=session, limit=1)
        assert len(result) == 1

    async def test_read_task_runs_applies_offset(self, flow_run, session):
        task_run_1 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id, task_key="my-key", dynamic_key="0"
            ),
        )
        task_run_2 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id, task_key="my-key-2", dynamic_key="0"
            ),
        )
        result_1 = await models.task_runs.read_task_runs(
            session=session, offset=0, limit=1
        )
        result_2 = await models.task_runs.read_task_runs(
            session=session, offset=1, limit=1
        )

        assert {result_1[0].id, result_2[0].id} == {task_run_1.id, task_run_2.id}

    async def test_read_task_runs_applies_sort(self, flow_run, session):
        now_dt = now("UTC")
        await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id,
                task_key="my-key",
                dynamic_key="0",
                expected_start_time=now_dt - timedelta(minutes=5),
            ),
        )
        task_run_2 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id,
                task_key="my-key",
                dynamic_key="1",
                expected_start_time=now_dt + timedelta(minutes=5),
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

    async def test_delete_task_run_with_data(self, flow_run, session):
        state_id = uuid4()
        task_run = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id,
                task_key="my-key",
                dynamic_key="0",
                state=schemas.states.State(
                    id=state_id,
                    type="COMPLETED",
                    name="My Running State",
                    data={"hello": "world"},
                ),
            ),
        )
        assert task_run.flow_run_id == flow_run.id
        assert task_run.state.id == state_id

        assert await models.task_runs.read_task_run(
            session=session, task_run_id=task_run.id
        )

        assert await models.task_runs.delete_task_run(
            session=session, task_run_id=task_run.id
        )

        # make sure the task run is deleted
        assert (
            await models.task_runs.read_task_run(
                session=session, task_run_id=task_run.id
            )
        ) is None


class TestPreventOrphanedConcurrencySlots:
    @pytest.fixture
    async def task_run_1(self, session, flow_run):
        model = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id,
                task_key="my-key-1",
                dynamic_key="0",
                tags=["red"],
                state=Pending(),
            ),
        )
        await session.commit()
        return model

    @pytest.fixture
    async def task_run_2(self, session, flow_run):
        model = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id,
                task_key="my-key-2",
                dynamic_key="1",
                tags=["red"],
                state=Pending(),
            ),
        )
        await session.commit()
        return model

    async def test_force_releases_concurrency(self, session, task_run_1, task_run_2):
        # first set flow runs in a running state
        await models.flow_runs.set_flow_run_state(
            session=session, flow_run_id=task_run_1.flow_run_id, state=Running()
        )
        await models.flow_runs.set_flow_run_state(
            session=session, flow_run_id=task_run_2.flow_run_id, state=Running()
        )

        await concurrency_limits.create_concurrency_limit(
            session=session,
            concurrency_limit=schemas.core.ConcurrencyLimit(
                tag="red", concurrency_limit=1
            ),
        )

        await session.commit()

        # take a concurrency slot
        await task_runs.set_task_run_state(
            session, task_run_1.id, Running(), task_policy=CoreTaskPolicy
        )

        # assert it is used up
        result = await task_runs.set_task_run_state(
            session, task_run_2.id, Running(), task_policy=CoreTaskPolicy
        )
        assert result.status.value == "WAIT"

        # forcibly take the task out of a running state
        # the force will disregard the provided task policy
        await task_runs.set_task_run_state(
            session, task_run_1.id, Failed(), force=True, task_policy=CoreTaskPolicy
        )

        # assert the slot is available
        result2 = await task_runs.set_task_run_state(
            session, task_run_2.id, Running(), task_policy=CoreTaskPolicy
        )
        assert result2.status.value == "ACCEPT"
