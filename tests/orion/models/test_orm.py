import pendulum
import pytest
import sqlalchemy as sa

from prefect.orion import models, schemas
from prefect.orion.models import orm


@pytest.fixture
async def many_flow_run_states(flow, session):
    """Creates 5 flow runs, each with 5 states. The data payload of each state is an integer 0-4"""

    # clear all other flow runs
    await session.execute(sa.delete(orm.FlowRun))
    await session.execute(sa.delete(orm.FlowRunState))

    for _ in range(5):
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.actions.FlowRunCreate(flow_id=flow.id, flow_version=1),
        )

        states = [
            orm.FlowRunState(
                flow_run_id=flow_run.id,
                **schemas.states.State(
                    type={
                        0: schemas.states.StateType.PENDING,
                        1: schemas.states.StateType.RUNNING,
                        2: schemas.states.StateType.COMPLETED,
                    }[i],
                    timestamp=pendulum.now("UTC"),
                ).dict()
            )
            for i in range(3)
        ]

        flow_run.state = states[-1]

        session.add_all(states)
    await session.commit()


@pytest.fixture
async def many_task_run_states(flow_run, session):
    """Creates 5 task runs, each with 5 states. The data payload of each state is an integer 0-4"""

    # clear all other task runs
    await session.execute(sa.delete(orm.TaskRun))
    await session.execute(sa.delete(orm.TaskRunState))

    for _ in range(5):
        task_run = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.actions.TaskRunCreate(
                flow_run_id=flow_run.id, task_key="test-task"
            ),
        )

        states = [
            orm.TaskRunState(
                task_run_id=task_run.id,
                **schemas.states.State(
                    type={
                        0: schemas.states.StateType.PENDING,
                        1: schemas.states.StateType.RUNNING,
                        2: schemas.states.StateType.COMPLETED,
                    }[i],
                    timestamp=pendulum.now("UTC"),
                ).dict()
            )
            for i in range(3)
        ]

        task_run.state = states[-1]

        session.add_all(states)

    await session.commit()


class TestFlowRun:
    async def test_flow_run_state_relationship_retrieves_current_state(
        self, many_flow_run_states, session
    ):

        # efficient query for most recent state without knowing its ID
        # by getting the state with the most recent timestamp
        frs_alias = sa.orm.aliased(orm.FlowRunState)
        query = (
            sa.select(
                orm.FlowRun,
                orm.FlowRunState.id,
                orm.FlowRunState.type,
            )
            .select_from(orm.FlowRun)
            .join(
                orm.FlowRunState,
                orm.FlowRun.id == orm.FlowRunState.flow_run_id,
                isouter=True,
            )
            .join(
                frs_alias,
                sa.and_(
                    orm.FlowRunState.flow_run_id == frs_alias.flow_run_id,
                    orm.FlowRunState.timestamp < frs_alias.timestamp,
                ),
                isouter=True,
            )
            .where(frs_alias.id == None)
        )
        result = await session.execute(query)
        objs = result.all()

        # assert that our handcrafted query picked up all the FINAL states
        assert all([o[2] == schemas.states.StateType.COMPLETED for o in objs])
        # assert that the `state` relationship picked up all the FINAL states
        assert all(
            [o[0].state.type == schemas.states.StateType.COMPLETED for o in objs]
        )
        # assert that the `state` relationship picked up the correct state id
        assert all([o[0].state.id == o[1] for o in objs])
        # assert that the `state_id` stores the correct state id
        assert all([o[0].state_id == o[1] for o in objs])

    async def test_flow_run_state_relationship_query_matches_current_data(
        self, many_flow_run_states, session
    ):
        query = sa.select(orm.FlowRun).where(
            orm.FlowRun.state.has(
                orm.FlowRunState.type == schemas.states.StateType.COMPLETED
            )
        )
        result = await session.execute(query)
        assert len(result.all()) == 5

    async def test_flow_run_state_relationship_query_doesnt_match_old_data(
        self, many_flow_run_states, session
    ):
        query = sa.select(orm.FlowRun.id).where(
            orm.FlowRun.state.has(
                orm.FlowRunState.type == schemas.states.StateType.RUNNING
            )
        )
        result = await session.execute(query)
        assert len(result.all()) == 0

    async def test_flow_run_state_relationship_type_filter_selects_current_state(
        self, flow, many_flow_run_states, session
    ):
        # the flow runs are most recently in a Completed state
        match_query = sa.select(sa.func.count(orm.FlowRun.id)).where(
            orm.FlowRun.flow_id == flow.id,
            orm.FlowRun.state.has(
                orm.FlowRunState.type == schemas.states.StateType.COMPLETED
            ),
        )
        result = await session.execute(match_query)
        assert result.scalar() == 5

        # no flow run is in a running state
        miss_query = sa.select(sa.func.count(orm.FlowRun.id)).where(
            orm.FlowRun.flow_id == flow.id,
            orm.FlowRun.state.has(
                orm.FlowRunState.type == schemas.states.StateType.RUNNING
            ),
        )
        result = await session.execute(miss_query)
        assert result.scalar() == 0

    async def test_assign_to_state_inserts_state(self, flow_run, session):
        flow_run_id = flow_run.id
        assert flow_run.state.type == schemas.states.StateType.PENDING

        # delete all states
        await session.execute(sa.delete(orm.FlowRunState))
        flow_run.state = orm.FlowRunState(**schemas.states.Completed().dict())
        await session.commit()
        session.expire_all()
        retrieved_flow_run = await session.get(orm.FlowRun, flow_run_id)
        assert retrieved_flow_run.state.type.value == "COMPLETED"

        result = await session.execute(
            sa.select(orm.FlowRunState).filter_by(flow_run_id=flow_run_id)
        )
        states = result.scalars().all()
        assert len(states) == 1
        assert states[0].type.value == "COMPLETED"

    async def test_assign_multiple_to_state_inserts_states(self, flow_run, session):
        flow_run_id = flow_run.id

        # delete all states
        await session.execute(sa.delete(orm.FlowRunState))

        flow_run.state = orm.FlowRunState(**schemas.states.Pending().dict())
        flow_run.state = orm.FlowRunState(**schemas.states.Running().dict())
        flow_run.state = orm.FlowRunState(**schemas.states.Completed().dict())
        await session.commit()
        session.expire_all()
        retrieved_flow_run = await session.get(orm.FlowRun, flow_run_id)
        assert retrieved_flow_run.state.type.value == "COMPLETED"

        result = await session.execute(
            sa.select(orm.FlowRunState)
            .filter_by(flow_run_id=flow_run_id)
            .order_by(orm.FlowRunState.timestamp.asc())
        )
        states = result.scalars().all()
        assert len(states) == 3
        assert states[0].type.value == "PENDING"
        assert states[1].type.value == "RUNNING"
        assert states[2].type.value == "COMPLETED"


class TestTaskRun:
    async def test_task_run_state_relationship_retrieves_current_state(
        self, many_task_run_states, session
    ):

        # efficient query for most recent state without knowing its ID
        # by getting the state with the most recent timestamp
        frs_alias = sa.orm.aliased(orm.TaskRunState)
        query = (
            sa.select(
                orm.TaskRun,
                orm.TaskRunState.id,
                orm.TaskRunState.data,
                orm.TaskRunState.type,
            )
            .select_from(orm.TaskRun)
            .join(
                orm.TaskRunState,
                orm.TaskRun.id == orm.TaskRunState.task_run_id,
                isouter=True,
            )
            .join(
                frs_alias,
                sa.and_(
                    orm.TaskRunState.task_run_id == frs_alias.task_run_id,
                    orm.TaskRunState.timestamp < frs_alias.timestamp,
                ),
                isouter=True,
            )
            .where(frs_alias.id == None)
        )
        result = await session.execute(query)
        objs = result.all()

        # assert that our handcrafted query picked up all the FINAL states
        assert all([o[3] == schemas.states.StateType.COMPLETED for o in objs])
        # assert that the `state` relationship picked up all the FINAL states
        assert all(
            [o[0].state.type == schemas.states.StateType.COMPLETED for o in objs]
        )
        # assert that the `state` relationship picked up the correct state id
        assert all([o[0].state.id == o[1] for o in objs])
        # assert that the `state_id` stores the correct state id
        assert all([o[0].state_id == o[1] for o in objs])

    async def test_task_run_state_relationship_query_matches_current_data(
        self, many_task_run_states, session
    ):
        query = sa.select(orm.TaskRun).where(
            orm.TaskRun.state.has(
                orm.TaskRunState.type == schemas.states.StateType.COMPLETED
            )
        )
        result = await session.execute(query)
        assert len(result.all()) == 5

    async def test_task_run_state_relationship_query_doesnt_match_old_data(
        self, many_task_run_states, session
    ):
        query = sa.select(orm.TaskRun.id).where(
            orm.TaskRun.state.has(
                orm.TaskRunState.type == schemas.states.StateType.RUNNING
            )
        )
        result = await session.execute(query)
        assert len(result.all()) == 0

    async def test_task_run_state_relationship_type_filter_selects_current_state(
        self, flow_run, many_task_run_states, session
    ):
        # the task runs are most recently in a completed state
        match_query = sa.select(sa.func.count(orm.TaskRun.id)).where(
            orm.TaskRun.flow_run_id == flow_run.id,
            orm.TaskRun.state.has(
                orm.TaskRunState.type == schemas.states.StateType.COMPLETED
            ),
        )
        result = await session.execute(match_query)
        assert result.scalar() == 5

        # no task run is in a running state
        miss_query = sa.select(sa.func.count(orm.TaskRun.id)).where(
            orm.TaskRun.flow_run_id == flow_run.id,
            orm.TaskRun.state.has(
                orm.TaskRunState.type == schemas.states.StateType.RUNNING
            ),
        )
        result = await session.execute(miss_query)
        assert result.scalar() == 0

    async def test_assign_to_state_inserts_state(self, task_run, session):
        task_run_id = task_run.id
        assert task_run.state.type == schemas.states.StateType.PENDING

        # delete all states
        await session.execute(sa.delete(orm.TaskRunState))
        task_run.state = orm.TaskRunState(**schemas.states.Completed().dict())
        await session.commit()
        session.expire_all()
        retrieved_flow_run = await session.get(orm.TaskRun, task_run_id)
        assert retrieved_flow_run.state.type.value == "COMPLETED"

        result = await session.execute(
            sa.select(orm.TaskRunState).filter_by(task_run_id=task_run_id)
        )
        states = result.scalars().all()
        assert len(states) == 1
        assert states[0].type.value == "COMPLETED"

    async def test_assign_multiple_to_state_inserts_states(self, task_run, session):
        task_run_id = task_run.id

        # delete all states
        await session.execute(sa.delete(orm.TaskRunState))

        task_run.state = orm.TaskRunState(**schemas.states.Pending().dict())
        task_run.state = orm.TaskRunState(**schemas.states.Running().dict())
        task_run.state = orm.TaskRunState(**schemas.states.Completed().dict())
        await session.commit()
        session.expire_all()
        retrieved_flow_run = await session.get(orm.TaskRun, task_run_id)
        assert retrieved_flow_run.state.type.value == "COMPLETED"

        result = await session.execute(
            sa.select(orm.TaskRunState)
            .filter_by(task_run_id=task_run_id)
            .order_by(orm.TaskRunState.timestamp.asc())
        )
        states = result.scalars().all()
        assert len(states) == 3
        assert states[0].type.value == "PENDING"
        assert states[1].type.value == "RUNNING"
        assert states[2].type.value == "COMPLETED"
