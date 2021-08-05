import pendulum
import pytest
import sqlalchemy as sa

from prefect.orion import models, schemas
from prefect.orion.models import orm


@pytest.fixture
async def many_flow_run_states(flow, database_session):
    """Creates 10 flow runs, each with 5 states. The data payload of each state is an integer 0-4"""

    # clear all other flow runs
    await database_session.execute(sa.delete(orm.FlowRun))
    await database_session.execute(sa.delete(orm.FlowRunState))

    for _ in range(10):
        flow_run = await models.flow_runs.create_flow_run(
            session=database_session,
            flow_run=schemas.actions.FlowRunCreate(flow_id=flow.id, flow_version=1),
        )

        states = [
            orm.FlowRunState(
                flow_run_id=flow_run.id,
                **schemas.states.State(
                    type=schemas.states.StateType.PENDING,
                    data=i,
                    timestamp=pendulum.now("UTC"),
                ).dict()
            )
            for i in range(5)
        ]

        database_session.add_all(states)
        await database_session.flush()
        await database_session.refresh(flow_run)


@pytest.fixture
async def many_task_run_states(flow_run, database_session):
    """Creates 10 task runs, each with 5 states. The data payload of each state is an integer 0-4"""

    # clear all other task runs
    await database_session.execute(sa.delete(orm.TaskRun))
    await database_session.execute(sa.delete(orm.TaskRunState))

    for _ in range(10):
        task_run = await models.task_runs.create_task_run(
            session=database_session,
            task_run=schemas.actions.TaskRunCreate(
                flow_run_id=flow_run.id, task_key="test-task"
            ),
        )

        states = [
            orm.TaskRunState(
                task_run_id=task_run.id,
                **schemas.states.State(
                    type=schemas.states.StateType.PENDING,
                    data=i,
                    timestamp=pendulum.now("UTC"),
                ).dict()
            )
            for i in range(5)
        ]

        database_session.add_all(states)
        await database_session.flush()
        await database_session.refresh(task_run)


class TestFlowRun:
    async def test_flow_run_state_relationship_retrieves_current_state(
        self, many_flow_run_states, database_session
    ):

        # full query for most recent states
        frs_alias = sa.orm.aliased(orm.FlowRunState)
        query = (
            sa.select(orm.FlowRun, orm.FlowRunState.id, orm.FlowRunState.data)
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
            .filter(frs_alias.id == None)
        )
        result = await database_session.execute(query)
        objs = result.all()

        # assert that our handcrafted query picked up all the FINAL states
        assert all([o[2] == 4 for o in objs])
        # assert that the `state` relationship picked up all the FINAL states
        assert all([o[0].state.data == 4 for o in objs])
        # assert that the `state` relationship picked up the correct state id
        assert all([o[0].state.id == o[1] for o in objs])

    async def test_flow_run_state_relationship_query_matches_current_data(
        self, many_flow_run_states, database_session
    ):
        query_4 = sa.select(orm.FlowRun).filter(
            orm.FlowRun.state.has(orm.FlowRunState.data == 4)
        )
        result_4 = await database_session.execute(query_4)
        # all flow runs have data == 4
        assert len(result_4.all()) == 10

    async def test_flow_run_state_relationship_query_doesnt_match_old_data(
        self, many_flow_run_states, database_session
    ):
        query_3 = sa.select(orm.FlowRun).filter(
            orm.FlowRun.state.has(orm.FlowRunState.data == 3)
        )
        result_3 = await database_session.execute(query_3)
        # no flow runs have data == 3
        assert len(result_3.all()) == 0


class TestTaskRun:
    async def test_task_run_state_relationship_retrieves_current_state(
        self, many_task_run_states, database_session
    ):

        # full query for most recent states
        frs_alias = sa.orm.aliased(orm.TaskRunState)
        query = (
            sa.select(orm.TaskRun, orm.TaskRunState.id, orm.TaskRunState.data)
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
            .filter(frs_alias.id == None)
        )
        result = await database_session.execute(query)
        objs = result.all()

        # assert that our handcrafted query picked up all the FINAL states
        assert all([o[2] == 4 for o in objs])
        # assert that the `state` relationship picked up all the FINAL states
        assert all([o[0].state.data == 4 for o in objs])
        # assert that the `state` relationship picked up the correct state id
        assert all([o[0].state.id == o[1] for o in objs])

    async def test_task_run_state_relationship_query_matches_current_data(
        self, many_task_run_states, database_session
    ):
        query_4 = sa.select(orm.TaskRun).filter(
            orm.TaskRun.state.has(orm.TaskRunState.data == 4)
        )
        result_4 = await database_session.execute(query_4)
        # all task runs have data == 4
        assert len(result_4.all()) == 10

    async def test_task_run_state_relationship_query_doesnt_match_old_data(
        self, many_task_run_states, database_session
    ):
        query_3 = sa.select(orm.TaskRun).filter(
            orm.TaskRun.state.has(orm.TaskRunState.data == 3)
        )
        result_3 = await database_session.execute(query_3)
        # no task runs have data == 3
        assert len(result_3.all()) == 0
