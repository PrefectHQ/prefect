import datetime
import logging
from uuid import uuid4

import pytest
import sqlalchemy as sa

from prefect.server import models, schemas
from prefect.types._datetime import now


@pytest.fixture
async def many_flow_run_states(flow, session, db):
    """Creates 5 flow runs, each with 5 states. The data payload of each state is an integer 0-4"""

    # clear all other flow runs
    await session.execute(sa.delete(db.FlowRun))
    await session.execute(sa.delete(db.FlowRunState))

    for _ in range(5):
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.actions.FlowRunCreate(flow_id=flow.id, flow_version="1"),
        )

        states = [
            db.FlowRunState(
                flow_run_id=flow_run.id,
                **schemas.states.State(
                    type={
                        0: schemas.states.StateType.PENDING,
                        1: schemas.states.StateType.RUNNING,
                        2: schemas.states.StateType.COMPLETED,
                    }[i],
                    timestamp=now("UTC") + datetime.timedelta(minutes=i),
                ).orm_dict(),
            )
            for i in range(3)
        ]

        flow_run.set_state(states[-1])

        session.add_all(states)
    await session.commit()


@pytest.fixture
async def many_task_run_states(flow_run, session, db):
    """Creates 5 task runs, each with 5 states. The data payload of each state is an integer 0-4"""

    # clear all other task runs
    await session.execute(sa.delete(db.TaskRun))
    await session.execute(sa.delete(db.TaskRunState))

    for i in range(5):
        task_run = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.actions.TaskRunCreate(
                flow_run_id=flow_run.id,
                task_key="test-task",
                dynamic_key=str(i),
            ),
        )

        states = [
            db.TaskRunState(
                task_run_id=task_run.id,
                **schemas.states.State(
                    type={
                        0: schemas.states.StateType.PENDING,
                        1: schemas.states.StateType.RUNNING,
                        2: schemas.states.StateType.COMPLETED,
                    }[i],
                    timestamp=now("UTC") + datetime.timedelta(minutes=i),
                ).orm_dict(),
            )
            for i in range(3)
        ]

        task_run.set_state(states[-1])

        session.add_all(states)

    await session.commit()


class TestBase:
    async def test_repr(self, db, session, flow):
        assert repr(flow) == f"Flow(id={flow.id})"
        assert repr(db.Flow()) == "Flow(id=None)"
        flow_id = uuid4()
        assert repr(db.Flow(id=flow_id)) == f"Flow(id={flow_id})"


class TestFlowRun:
    async def test_flow_run_state_relationship_retrieves_current_state(
        self, many_flow_run_states, session, db
    ):
        # efficient query for most recent state without knowing its ID
        # by getting the state with the most recent timestamp
        frs_alias = sa.orm.aliased(db.FlowRunState)
        query = (
            sa.select(
                db.FlowRun,
                db.FlowRunState.id,
                db.FlowRunState.type,
            )
            .select_from(db.FlowRun)
            .join(
                db.FlowRunState,
                db.FlowRun.id == db.FlowRunState.flow_run_id,
                isouter=True,
            )
            .join(
                frs_alias,
                sa.and_(
                    db.FlowRunState.flow_run_id == frs_alias.flow_run_id,
                    db.FlowRunState.timestamp < frs_alias.timestamp,
                ),
                isouter=True,
            )
            .where(frs_alias.id is None)
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
        self, many_flow_run_states, session, db
    ):
        query = sa.select(db.FlowRun).where(
            db.FlowRun.state.has(
                db.FlowRunState.type == schemas.states.StateType.COMPLETED
            )
        )
        result = await session.execute(query)
        assert len(result.all()) == 5

    async def test_flow_run_state_relationship_query_doesnt_match_old_data(
        self,
        many_flow_run_states,
        session,
        db,
    ):
        query = sa.select(db.FlowRun.id).where(
            db.FlowRun.state.has(
                db.FlowRunState.type == schemas.states.StateType.RUNNING
            )
        )
        result = await session.execute(query)
        assert len(result.all()) == 0

    async def test_flow_run_state_relationship_type_filter_selects_current_state(
        self, flow, many_flow_run_states, session, db
    ):
        # the flow runs are most recently in a Completed state
        match_query = sa.select(sa.func.count(db.FlowRun.id)).where(
            db.FlowRun.flow_id == flow.id,
            db.FlowRun.state.has(
                db.FlowRunState.type == schemas.states.StateType.COMPLETED
            ),
        )
        result = await session.execute(match_query)
        assert result.scalar() == 5

        # no flow run is in a running state
        miss_query = sa.select(sa.func.count(db.FlowRun.id)).where(
            db.FlowRun.flow_id == flow.id,
            db.FlowRun.state.has(
                db.FlowRunState.type == schemas.states.StateType.RUNNING
            ),
        )
        result = await session.execute(miss_query)
        assert result.scalar() == 0

    async def test_assign_to_state_inserts_state(self, flow_run, session, db):
        flow_run_id = flow_run.id
        assert flow_run.state is None

        # delete all states
        await session.execute(sa.delete(db.FlowRunState))
        flow_run.set_state(db.FlowRunState(**schemas.states.Completed().orm_dict()))
        await session.commit()
        session.expire_all()
        retrieved_flow_run = await session.get(db.FlowRun, flow_run_id)
        assert retrieved_flow_run.state.type.value == "COMPLETED"

        result = await session.execute(
            sa.select(db.FlowRunState).filter_by(flow_run_id=flow_run_id)
        )
        states = result.scalars().all()
        assert len(states) == 1
        assert states[0].type.value == "COMPLETED"

    async def test_assign_multiple_to_state_inserts_states(self, flow_run, session, db):
        flow_run_id = flow_run.id

        # delete all states
        await session.execute(sa.delete(db.FlowRunState))

        now_dt = now("UTC")
        flow_run.set_state(
            db.FlowRunState(**schemas.states.Pending(timestamp=now_dt).orm_dict())
        )
        flow_run.set_state(
            db.FlowRunState(
                **schemas.states.Running(
                    timestamp=now_dt + datetime.timedelta(minutes=1)
                ).orm_dict()
            )
        )
        flow_run.set_state(
            db.FlowRunState(
                **schemas.states.Completed(
                    timestamp=now_dt + datetime.timedelta(minutes=2)
                ).orm_dict()
            )
        )
        await session.commit()
        session.expire_all()
        retrieved_flow_run = await session.get(db.FlowRun, flow_run_id)
        assert retrieved_flow_run.state.type.value == "COMPLETED"

        result = await session.execute(
            sa.select(db.FlowRunState)
            .filter_by(flow_run_id=flow_run_id)
            .order_by(db.FlowRunState.timestamp.asc())
        )
        states = result.scalars().all()
        assert len(states) == 3
        assert states[0].type.value == "PENDING"
        assert states[1].type.value == "RUNNING"
        assert states[2].type.value == "COMPLETED"


class TestTaskRun:
    async def test_task_run_state_relationship_retrieves_current_state(
        self, many_task_run_states, session, db
    ):
        # efficient query for most recent state without knowing its ID
        # by getting the state with the most recent timestamp
        frs_alias = sa.orm.aliased(db.TaskRunState)
        query = (
            sa.select(
                db.TaskRun,
                db.TaskRunState.id,
                db.TaskRunState.type,
            )
            .select_from(db.TaskRun)
            .join(
                db.TaskRunState,
                db.TaskRun.id == db.TaskRunState.task_run_id,
                isouter=True,
            )
            .join(
                frs_alias,
                sa.and_(
                    db.TaskRunState.task_run_id == frs_alias.task_run_id,
                    db.TaskRunState.timestamp < frs_alias.timestamp,
                ),
                isouter=True,
            )
            .where(frs_alias.id is None)
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

    async def test_task_run_state_relationship_query_matches_current_data(
        self, many_task_run_states, session, db
    ):
        query = sa.select(db.TaskRun).where(
            db.TaskRun.state.has(
                db.TaskRunState.type == schemas.states.StateType.COMPLETED
            )
        )
        result = await session.execute(query)
        assert len(result.all()) == 5

    async def test_task_run_state_relationship_query_doesnt_match_old_data(
        self, many_task_run_states, session, db
    ):
        query = sa.select(db.TaskRun.id).where(
            db.TaskRun.state.has(
                db.TaskRunState.type == schemas.states.StateType.RUNNING
            )
        )
        result = await session.execute(query)
        assert len(result.all()) == 0

    async def test_task_run_state_relationship_type_filter_selects_current_state(
        self, flow_run, many_task_run_states, session, db
    ):
        # the task runs are most recently in a completed state
        match_query = sa.select(sa.func.count(db.TaskRun.id)).where(
            db.TaskRun.flow_run_id == flow_run.id,
            db.TaskRun.state.has(
                db.TaskRunState.type == schemas.states.StateType.COMPLETED
            ),
        )
        result = await session.execute(match_query)
        assert result.scalar() == 5

        # no task run is in a running state
        miss_query = sa.select(sa.func.count(db.TaskRun.id)).where(
            db.TaskRun.flow_run_id == flow_run.id,
            db.TaskRun.state.has(
                db.TaskRunState.type == schemas.states.StateType.RUNNING
            ),
        )
        result = await session.execute(miss_query)
        assert result.scalar() == 0

    async def test_assign_to_state_inserts_state(self, task_run, session, db):
        task_run_id = task_run.id
        assert task_run.state is None

        # delete all states
        await session.execute(sa.delete(db.TaskRunState))
        task_run.set_state(db.TaskRunState(**schemas.states.Completed().orm_dict()))
        await session.commit()
        session.expire_all()
        retrieved_flow_run = await session.get(db.TaskRun, task_run_id)
        assert retrieved_flow_run.state.type.value == "COMPLETED"

        result = await session.execute(
            sa.select(db.TaskRunState).filter_by(task_run_id=task_run_id)
        )
        states = result.scalars().all()
        assert len(states) == 1
        assert states[0].type.value == "COMPLETED"

    async def test_assign_multiple_to_state_inserts_states(self, task_run, session, db):
        task_run_id = task_run.id

        # delete all states
        await session.execute(sa.delete(db.TaskRunState))

        now_dt = now("UTC")
        task_run.set_state(
            db.TaskRunState(**schemas.states.Pending(timestamp=now_dt).orm_dict())
        )
        task_run.set_state(
            db.TaskRunState(
                **schemas.states.Running(
                    timestamp=now_dt + datetime.timedelta(minutes=1)
                ).orm_dict()
            )
        )
        task_run.set_state(
            db.TaskRunState(
                **schemas.states.Completed(
                    timestamp=now_dt + datetime.timedelta(minutes=2)
                ).orm_dict()
            )
        )
        await session.commit()
        session.expire_all()
        retrieved_flow_run = await session.get(db.TaskRun, task_run_id)
        assert retrieved_flow_run.state.type.value == "COMPLETED"

        result = await session.execute(
            sa.select(db.TaskRunState)
            .filter_by(task_run_id=task_run_id)
            .order_by(db.TaskRunState.timestamp.asc())
        )
        states = result.scalars().all()
        assert len(states) == 3
        assert states[0].type.value == "PENDING"
        assert states[1].type.value == "RUNNING"
        assert states[2].type.value == "COMPLETED"


class TestTotalRunTimeEstimate:
    async def test_flow_run_estimated_run_time_matches_total_run_time(
        self, session, flow, db
    ):
        dt = now("UTC") - datetime.timedelta(minutes=1)
        fr = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id, state=schemas.states.Pending(timestamp=dt)
            ),
        )
        # move into a running state for 3 seconds, then complete
        await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=fr.id,
            state=schemas.states.Running(timestamp=dt + datetime.timedelta(seconds=1)),
        )
        await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=fr.id,
            state=schemas.states.Completed(
                timestamp=dt + datetime.timedelta(seconds=4)
            ),
        )

        assert fr.total_run_time == datetime.timedelta(seconds=3)
        assert fr.estimated_run_time == datetime.timedelta(seconds=3)

        # check SQL logic
        await session.commit()
        result = await session.execute(
            sa.select(db.FlowRun.estimated_run_time).filter_by(id=fr.id)
        )

        assert result.scalar() == datetime.timedelta(seconds=3)

    async def test_flow_run_estimated_run_time_includes_current_run(
        self, session, flow, db
    ):
        tolerance = datetime.timedelta(seconds=3)

        dt = now("UTC") - datetime.timedelta(minutes=1)
        fr = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id, state=schemas.states.Pending(timestamp=dt)
            ),
        )
        # move into a running state
        await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=fr.id,
            state=schemas.states.Running(timestamp=dt + datetime.timedelta(seconds=1)),
        )

        assert fr.total_run_time == datetime.timedelta(0)
        # the estimated time is between ~59 and ~60 seconds
        assert (
            datetime.timedelta(seconds=59) - tolerance
            < fr.estimated_run_time
            < datetime.timedelta(seconds=60) + tolerance
        )

        # check SQL logic
        await session.commit()
        result = await session.execute(
            sa.select(db.FlowRun.estimated_run_time).filter_by(id=fr.id)
        )
        assert (
            datetime.timedelta(seconds=59) - tolerance
            < result.scalar()
            < datetime.timedelta(seconds=60) + tolerance
        )

    async def test_task_run_estimated_run_time_matches_total_run_time(
        self, session, flow_run, db
    ):
        dt = now("UTC") - datetime.timedelta(minutes=1)
        tr = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id,
                task_key="a",
                dynamic_key="0",
                state=schemas.states.Pending(timestamp=dt),
            ),
        )
        # move into a running state for 3 seconds, then complete
        await models.task_runs.set_task_run_state(
            session=session,
            task_run_id=tr.id,
            state=schemas.states.Running(timestamp=dt + datetime.timedelta(seconds=1)),
        )
        await models.task_runs.set_task_run_state(
            session=session,
            task_run_id=tr.id,
            state=schemas.states.Completed(
                timestamp=dt + datetime.timedelta(seconds=4)
            ),
        )

        assert tr.total_run_time == datetime.timedelta(seconds=3)
        assert tr.estimated_run_time == datetime.timedelta(seconds=3)

        # check SQL logic
        await session.commit()
        result = await session.execute(
            sa.select(db.TaskRun.estimated_run_time).filter_by(id=tr.id)
        )

        assert result.scalar() == datetime.timedelta(seconds=3)

    async def test_task_run_estimated_run_time_includes_current_run(
        self, session, flow_run, db
    ):
        tolerance = datetime.timedelta(seconds=3)

        dt = now("UTC") - datetime.timedelta(minutes=1)
        tr = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id,
                task_key="a",
                dynamic_key="0",
                state=schemas.states.Pending(timestamp=dt),
            ),
        )
        # move into a running state
        await models.task_runs.set_task_run_state(
            session=session,
            task_run_id=tr.id,
            state=schemas.states.Running(timestamp=dt + datetime.timedelta(seconds=1)),
        )

        assert tr.total_run_time == datetime.timedelta(0)
        # the estimated time is between ~59 and ~60 seconds
        assert (
            datetime.timedelta(seconds=59) - tolerance
            < tr.estimated_run_time
            < datetime.timedelta(seconds=60) + tolerance
        )

        # check SQL logic
        await session.commit()
        result = await session.execute(
            sa.select(db.TaskRun.estimated_run_time).filter_by(id=tr.id)
        )

        assert (
            datetime.timedelta(seconds=59) - tolerance
            < result.scalar()
            < datetime.timedelta(seconds=60) + tolerance
        )

    async def test_estimated_run_time_in_correlated_subquery(self, session, flow, db):
        """
        The estimated_run_time includes a .correlate() statement that ensures it can
        be used as a correlated subquery within other selects or joins.
        """
        dt = now("UTC") - datetime.timedelta(minutes=1)
        fr = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id, state=schemas.states.Pending(timestamp=dt)
            ),
        )
        # move into a running state for 3 seconds, then complete
        await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=fr.id,
            state=schemas.states.Running(timestamp=dt + datetime.timedelta(seconds=1)),
        )
        await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=fr.id,
            state=schemas.states.Completed(
                timestamp=dt + datetime.timedelta(seconds=4)
            ),
        )

        await session.commit()
        query = (
            sa.select(
                db.FlowRun.id,
                db.FlowRun.estimated_run_time,
                db.FlowRunState.type,
            )
            .select_from(db.FlowRun)
            .join(
                db.FlowRunState,
                db.FlowRunState.id == db.FlowRun.state_id,
            )
            .where(db.FlowRun.id == fr.id)
        )

        # this query has only one FROM clause due to correlation
        assert str(query).count("FROM") == 1
        # this query has only one JOIN clause due to correlation
        assert str(query).count("JOIN") == 1

        result = await session.execute(query)
        assert result.all() == [
            (
                fr.id,
                datetime.timedelta(seconds=3),
                schemas.states.StateType.COMPLETED,
            )
        ]


class TestExpectedStartTimeDelta:
    async def test_flow_run_lateness_when_scheduled(self, session, flow, db):
        lateness = datetime.timedelta(seconds=60)
        dt = now("UTC") - lateness

        fr = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id, state=schemas.states.Scheduled(scheduled_time=dt)
            ),
        )
        assert lateness <= fr.estimated_start_time_delta <= (now() - dt)

        # check SQL logic
        await session.commit()
        result = await session.execute(
            sa.select(db.FlowRun.estimated_start_time_delta).filter_by(id=fr.id)
        )
        estimated_start_time_delta = result.scalar()

        # allow for some wiggle room in the time delta
        assert (estimated_start_time_delta - lateness) <= datetime.timedelta(seconds=1)
        assert (now() - dt - lateness) <= datetime.timedelta(seconds=1)

    async def test_flow_run_lateness_when_pending(self, session, flow, db):
        lateness = datetime.timedelta(seconds=60)
        dt = now("UTC") - lateness

        fr = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id, state=schemas.states.Scheduled(scheduled_time=dt)
            ),
        )
        await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=fr.id,
            state=schemas.states.Pending(timestamp=dt + datetime.timedelta(seconds=1)),
        )

        # pending has no impact on lateness
        assert lateness <= fr.estimated_start_time_delta <= (now() - dt)

        # check SQL logic
        await session.commit()
        result = await session.execute(
            sa.select(db.FlowRun.estimated_start_time_delta).filter_by(id=fr.id)
        )
        estimated_start_time_delta = result.scalar()

        # allow for some wiggle room in the time delta to allow for slow tests
        wiggle_room = datetime.timedelta(seconds=5)

        assert (estimated_start_time_delta - lateness) <= wiggle_room
        assert (now() - dt - lateness) <= wiggle_room

    async def test_flow_run_lateness_when_running(self, session, flow, db):
        dt = now("UTC") - datetime.timedelta(minutes=1)
        fr = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id, state=schemas.states.Scheduled(scheduled_time=dt)
            ),
        )
        await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=fr.id,
            state=schemas.states.Running(timestamp=dt + datetime.timedelta(seconds=5)),
        )

        # running created a start time
        assert fr.estimated_start_time_delta == datetime.timedelta(seconds=5)

        # check SQL logic
        await session.commit()
        result = await session.execute(
            sa.select(db.FlowRun.estimated_start_time_delta).filter_by(id=fr.id)
        )
        assert result.scalar() == datetime.timedelta(seconds=5)

    async def test_flow_run_lateness_when_terminal(self, session, flow, db):
        dt = now("UTC") - datetime.timedelta(minutes=1)
        fr = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id, state=schemas.states.Scheduled(scheduled_time=dt)
            ),
        )
        await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=fr.id,
            state=schemas.states.Completed(
                timestamp=dt + datetime.timedelta(seconds=5)
            ),
        )

        # final states remove lateness even if the run never started
        assert fr.estimated_start_time_delta == datetime.timedelta(seconds=0)

        # check SQL logic
        await session.commit()
        result = await session.execute(
            sa.select(db.FlowRun.estimated_start_time_delta).filter_by(id=fr.id)
        )
        assert result.scalar() == datetime.timedelta(seconds=0)

    async def test_flow_run_lateness_is_zero_when_early(self, session, flow, db):
        dt = now("UTC") - datetime.timedelta(minutes=1)
        fr = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id, state=schemas.states.Scheduled(scheduled_time=dt)
            ),
        )
        await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=fr.id,
            state=schemas.states.Running(timestamp=dt - datetime.timedelta(minutes=5)),
        )

        # running early results in zero lateness
        assert fr.estimated_start_time_delta == datetime.timedelta(seconds=0)

        # check SQL logic
        await session.commit()
        result = await session.execute(
            sa.select(db.FlowRun.estimated_start_time_delta).filter_by(id=fr.id)
        )
        assert result.scalar() == datetime.timedelta(seconds=0)


class TestLog:
    async def test_create_log_with_flow_run_id_and_task_run_id(self, session, db):
        now_dt = now("UTC")
        fifteen_mins_ago = now_dt - datetime.timedelta(minutes=15)

        log = db.Log(
            name="prefect.flow_run",
            level=logging.INFO,
            message="Ahoy, captain",
            timestamp=now_dt,
            flow_run_id=uuid4(),
            task_run_id=uuid4(),
        )

        session.add(log)
        await session.flush()

        query = (
            sa.select(db.Log)
            .where(db.Log.timestamp > fifteen_mins_ago)
            .execution_options(populate_existing=True)
        )

        result = await session.execute(query)
        assert result.scalar() == log

    async def test_create_log_without_task_run_id(self, session, db):
        now_dt = now("UTC")
        fifteen_mins_ago = now_dt - datetime.timedelta(minutes=15)

        log = db.Log(
            name="prefect.flow_run",
            level=logging.WARNING,
            message="Black flag ahead, captain!",
            flow_run_id=uuid4(),
            timestamp=now_dt,
        )

        session.add(log)
        await session.flush()

        query = (
            sa.select(db.Log)
            .where(db.Log.timestamp > fifteen_mins_ago)
            .execution_options(populate_existing=True)
        )

        result = await session.execute(query)
        assert result.scalar() == log
