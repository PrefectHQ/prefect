from sqlalchemy import select
import pytest
import pendulum
from prefect.orion.models import orm
from prefect.orion import schemas


class TestFlowRun:
    @pytest.fixture(autouse=True)
    async def create_flow_run_states(self, flow_run, database_session):
        # insert states out of order
        states = [
            orm.FlowRunState(
                flow_run_id=flow_run.id,
                **schemas.core.State(
                    type=schemas.core.StateType.PENDING,
                    timestamp=pendulum.now().subtract(seconds=1),
                ).dict(exclude={"data"})
            ),
            orm.FlowRunState(
                flow_run_id=flow_run.id,
                **schemas.core.State(
                    type=schemas.core.StateType.COMPLETED,
                    timestamp=pendulum.now().add(seconds=1),
                ).dict(exclude={"data"})
            ),
            orm.FlowRunState(
                flow_run_id=flow_run.id,
                **schemas.core.State(
                    type=schemas.core.StateType.RUNNING, timestamp=pendulum.now()
                ).dict(exclude={"data"})
            ),
        ]

        database_session.add_all(states)
        await database_session.flush()
        await database_session.refresh(flow_run)

    async def test_flow_run_states_relationship(self, flow_run):
        assert [s.type for s in flow_run.states] == [
            schemas.core.StateType.PENDING,
            schemas.core.StateType.RUNNING,
            schemas.core.StateType.COMPLETED,
        ]

    async def test_flow_run_state_property(self, flow_run):
        assert flow_run.state.type is schemas.core.StateType.COMPLETED


class TestTaskRun:
    @pytest.fixture(autouse=True)
    async def create_task_run_states(sel, task_run, database_session):
        # insert states out of order
        states = [
            orm.TaskRunState(
                task_run_id=task_run.id,
                **schemas.core.State(
                    type=schemas.core.StateType.PENDING,
                    timestamp=pendulum.now().subtract(seconds=1),
                ).dict(exclude={"data"})
            ),
            orm.TaskRunState(
                task_run_id=task_run.id,
                **schemas.core.State(
                    type=schemas.core.StateType.COMPLETED,
                    timestamp=pendulum.now().add(seconds=1),
                ).dict(exclude={"data"})
            ),
            orm.TaskRunState(
                task_run_id=task_run.id,
                **schemas.core.State(
                    type=schemas.core.StateType.RUNNING, timestamp=pendulum.now()
                ).dict(exclude={"data"})
            ),
        ]

        database_session.add_all(states)
        await database_session.flush()
        await database_session.refresh(task_run)

    async def test_task_run_states_relationship(self, task_run):
        assert [s.type for s in task_run.states] == [
            schemas.core.StateType.PENDING,
            schemas.core.StateType.RUNNING,
            schemas.core.StateType.COMPLETED,
        ]

    async def test_task_run_state_property(self, task_run):
        assert task_run.state.type is schemas.core.StateType.COMPLETED
