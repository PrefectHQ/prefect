import datetime

import pendulum
import pytest
import sqlalchemy as sa

from prefect import states
from prefect.orion import models, schemas
from prefect.orion.services.scheduler import RecentDeploymentsScheduler, Scheduler
from prefect.settings import (
    PREFECT_ORION_SERVICES_SCHEDULER_INSERT_BATCH_SIZE,
    PREFECT_ORION_SERVICES_SCHEDULER_MIN_RUNS,
)


async def test_create_schedules_from_deployment(flow, session):
    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="test",
            flow_id=flow.id,
            schedule=schemas.schedules.IntervalSchedule(
                interval=datetime.timedelta(hours=1)
            ),
        ),
    )
    await session.commit()

    n_runs = await models.flow_runs.count_flow_runs(session)
    assert n_runs == 0

    service = Scheduler(handle_signals=False)
    await service.start(loops=1)
    runs = await models.flow_runs.read_flow_runs(session)
    assert len(runs) == service.min_runs
    expected_dates = await deployment.schedule.get_dates(service.min_runs)
    assert set(expected_dates) == {r.state.state_details.scheduled_time for r in runs}

    assert all(
        [r.state_name == "Scheduled" for r in runs]
    ), "Scheduler sets flow_run.state_name"


async def test_create_schedule_respects_max_future_time(flow, session):
    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="test",
            flow_id=flow.id,
            schedule=schemas.schedules.IntervalSchedule(
                interval=datetime.timedelta(days=30),
                anchor_date=pendulum.now("UTC"),
            ),
        ),
    )
    await session.commit()

    n_runs = await models.flow_runs.count_flow_runs(session)
    assert n_runs == 0
    service = Scheduler(handle_signals=False)
    await service.start(loops=1)
    runs = await models.flow_runs.read_flow_runs(session)

    assert len(runs) == 3
    expected_dates = await deployment.schedule.get_dates(
        service.max_runs, end=pendulum.now() + service.max_scheduled_time
    )
    assert set(expected_dates) == {r.state.state_details.scheduled_time for r in runs}


async def test_create_schedules_from_multiple_deployments(flow, session):
    flow_2 = await models.flows.create_flow(
        session=session, flow=schemas.core.Flow(name="flow-2")
    )

    d1 = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="test",
            flow_id=flow.id,
            schedule=schemas.schedules.IntervalSchedule(
                interval=datetime.timedelta(hours=1)
            ),
        ),
    )
    d2 = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="test-2",
            flow_id=flow.id,
            schedule=schemas.schedules.IntervalSchedule(
                interval=datetime.timedelta(days=10)
            ),
        ),
    )
    d3 = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="test",
            flow_id=flow_2.id,
            schedule=schemas.schedules.IntervalSchedule(
                interval=datetime.timedelta(days=5)
            ),
        ),
    )
    await session.commit()

    n_runs = await models.flow_runs.count_flow_runs(session)
    assert n_runs == 0

    service = Scheduler(handle_signals=False)
    await service.start(loops=1)
    runs = await models.flow_runs.read_flow_runs(session)

    expected_dates = set()
    for deployment in [d1, d2, d3]:
        dep_runs = await deployment.schedule.get_dates(
            service.min_runs,
            start=pendulum.now(),
            end=pendulum.now() + service.max_scheduled_time,
        )
        expected_dates.update(dep_runs)
    assert set(expected_dates) == {r.state.state_details.scheduled_time for r in runs}


async def test_create_schedules_from_multiple_deployments_in_batches(flow, session):
    flow_2 = await models.flows.create_flow(
        session=session, flow=schemas.core.Flow(name="flow-2")
    )

    # create deployments that will have to insert
    # flow runs in batches of scheduler_insertion_batch_size
    deployments_to_schedule = (
        PREFECT_ORION_SERVICES_SCHEDULER_INSERT_BATCH_SIZE.value()
        // PREFECT_ORION_SERVICES_SCHEDULER_MIN_RUNS.value()
    ) + 1
    for i in range(deployments_to_schedule):
        await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name=f"test_{i}",
                flow_id=flow.id,
                schedule=schemas.schedules.IntervalSchedule(
                    interval=datetime.timedelta(hours=1)
                ),
            ),
        )
    await session.commit()

    n_runs = await models.flow_runs.count_flow_runs(session)
    assert n_runs == 0

    # should insert more than the batch size successfully
    await Scheduler(handle_signals=False).start(loops=1)
    runs = await models.flow_runs.read_flow_runs(session)
    assert (
        len(runs)
        == deployments_to_schedule * PREFECT_ORION_SERVICES_SCHEDULER_MIN_RUNS.value()
    )
    assert len(runs) > PREFECT_ORION_SERVICES_SCHEDULER_INSERT_BATCH_SIZE.value()


async def test_scheduler_respects_schedule_is_active(flow, session):
    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="test",
            flow_id=flow.id,
            schedule=schemas.schedules.IntervalSchedule(
                interval=datetime.timedelta(hours=1)
            ),
            is_schedule_active=False,
        ),
    )
    await session.commit()

    n_runs = await models.flow_runs.count_flow_runs(session)
    assert n_runs == 0

    await Scheduler(handle_signals=False).start(loops=1)
    n_runs_2 = await models.flow_runs.count_flow_runs(session)
    assert n_runs_2 == 0


async def test_scheduler_runs_when_too_few_scheduled_runs_but_doesnt_overwrite(
    flow, session
):
    """
    Create 3 runs, cancel one, and check that the scheduler doesn't overwrite the cancelled run
    """
    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="test",
            flow_id=flow.id,
            schedule=schemas.schedules.IntervalSchedule(
                interval=datetime.timedelta(hours=1)
            ),
        ),
    )
    await session.commit()

    n_runs = await models.flow_runs.count_flow_runs(session)
    assert n_runs == 0

    # run multiple loops
    await Scheduler(handle_signals=False).start(loops=1)
    await Scheduler(handle_signals=False).start(loops=1)

    n_runs = await models.flow_runs.count_flow_runs(session)
    assert n_runs == 3

    runs = await models.flow_runs.read_flow_runs(
        session,
        limit=1,
        flow_run_filter=schemas.filters.FlowRunFilter(
            state=dict(type=dict(any_=["SCHEDULED"]))
        ),
    )

    # cancel one run
    await models.flow_runs.set_flow_run_state(
        session, runs[0].id, state=states.Cancelled()
    )
    await session.commit()

    # run scheduler again
    await Scheduler(handle_signals=False).start(loops=1)
    runs = await models.flow_runs.read_flow_runs(
        session,
        flow_run_filter=schemas.filters.FlowRunFilter(
            deployment_id=dict(any_=[deployment.id])
        ),
    )
    assert len(runs) == 3
    assert {r.state_type for r in runs} == {"SCHEDULED", "SCHEDULED", "CANCELLED"}


class TestRecentDeploymentsScheduler:
    async def deployment(self, session, flow):
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(name="My Deployment", flow_id=flow.id),
        )
        await session.commit()
        return deployment

    async def test_tight_loop_by_default(self):
        assert RecentDeploymentsScheduler(handle_signals=False).loop_seconds == 5

    async def test_schedules_runs_for_recently_created_deployments(
        self, deployment, session, db
    ):
        recent_scheduler = RecentDeploymentsScheduler(handle_signals=False)
        count_query = (
            sa.select(sa.func.count())
            .select_from(db.FlowRun)
            .where(db.FlowRun.deployment_id == deployment.id)
        )
        runs_count = (await session.execute(count_query)).scalar()
        assert runs_count == 0

        await recent_scheduler.start(loops=1)

        runs_count = (await session.execute(count_query)).scalar()
        assert runs_count == recent_scheduler.min_runs

    async def test_schedules_runs_for_recently_updated_deployments(
        self, deployment, session, db
    ):
        # artifically move the created time back (updated time will still be recent)
        await session.execute(
            sa.update(db.Deployment)
            .where(db.Deployment.id == deployment.id)
            .values(created=pendulum.now().subtract(hours=1))
        )
        await session.commit()

        count_query = (
            sa.select(sa.func.count())
            .select_from(db.FlowRun)
            .where(db.FlowRun.deployment_id == deployment.id)
        )

        recent_scheduler = RecentDeploymentsScheduler(handle_signals=False)
        runs_count = (await session.execute(count_query)).scalar()
        assert runs_count == 0

        await recent_scheduler.start(loops=1)

        runs_count = (await session.execute(count_query)).scalar()
        assert runs_count == recent_scheduler.min_runs

    async def test_schedules_no_runs_for_deployments_updated_a_while_ago(
        self, deployment, session, db
    ):
        # artifically move the updated time back
        await session.execute(
            sa.update(db.Deployment)
            .where(db.Deployment.id == deployment.id)
            .values(updated=pendulum.now().subtract(minutes=1))
        )
        await session.commit()

        count_query = (
            sa.select(sa.func.count())
            .select_from(db.FlowRun)
            .where(db.FlowRun.deployment_id == deployment.id)
        )

        recent_scheduler = RecentDeploymentsScheduler(handle_signals=False)
        runs_count = (await session.execute(count_query)).scalar()
        assert runs_count == 0

        await recent_scheduler.start(loops=1)

        runs_count = (await session.execute(count_query)).scalar()
        assert runs_count == 0


class TestScheduleRulesWaterfall:
    @pytest.mark.parametrize(
        "interval,n",
        [
            # schedule until we at least exceed an hour
            (datetime.timedelta(minutes=1), 61),
            # schedule at least 3 runs
            (datetime.timedelta(hours=1), 3),
            # schedule until we at least exceed an hour
            (datetime.timedelta(minutes=5), 13),
            # schedule until at most 100 days
            (datetime.timedelta(days=60), 2),
        ],
    )
    async def test_create_schedule_respects_max_future_time(
        self, flow, session, interval, n
    ):
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="test",
                flow_id=flow.id,
                schedule=schemas.schedules.IntervalSchedule(
                    interval=interval,
                    anchor_date=pendulum.now("UTC").add(seconds=1),
                ),
            ),
        )
        await session.commit()

        # assert clean slate
        assert (await models.flow_runs.count_flow_runs(session)) == 0

        # run scheduler
        service = Scheduler(handle_signals=False)
        await service.start(loops=1)

        runs = await models.flow_runs.read_flow_runs(session)
        assert len(runs) == n
