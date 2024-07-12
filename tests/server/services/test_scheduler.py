import datetime

import pendulum
import pytest
import sqlalchemy as sa

from prefect.server import models, schemas
from prefect.server.services.scheduler import RecentDeploymentsScheduler, Scheduler
from prefect.settings import (
    PREFECT_API_SERVICES_SCHEDULER_INSERT_BATCH_SIZE,
    PREFECT_API_SERVICES_SCHEDULER_MIN_RUNS,
)


@pytest.fixture
async def deployment_without_schedules(flow, session):
    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="no schedules",
            flow_id=flow.id,
        ),
    )
    await session.commit()
    return deployment


@pytest.fixture
async def deployment_with_inactive_schedules(flow, session):
    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="inactive schedules",
            flow_id=flow.id,
            schedules=[
                schemas.core.DeploymentSchedule(
                    schedule=schemas.schedules.IntervalSchedule(
                        interval=datetime.timedelta(hours=1)
                    ),
                    active=False,
                ),
                schemas.core.DeploymentSchedule(
                    schedule=schemas.schedules.IntervalSchedule(
                        interval=datetime.timedelta(hours=2)
                    ),
                    active=False,
                ),
                schemas.core.DeploymentSchedule(
                    schedule=schemas.schedules.IntervalSchedule(
                        interval=datetime.timedelta(hours=4)
                    ),
                    active=False,
                ),
            ],
        ),
    )
    await session.commit()
    return deployment


@pytest.fixture
async def deployment_with_active_schedules(flow, session):
    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="active schedules",
            flow_id=flow.id,
            schedules=[
                schemas.core.DeploymentSchedule(
                    schedule=schemas.schedules.IntervalSchedule(
                        interval=datetime.timedelta(hours=1)
                    ),
                    active=True,
                ),
                schemas.core.DeploymentSchedule(
                    schedule=schemas.schedules.IntervalSchedule(
                        interval=datetime.timedelta(hours=2)
                    ),
                    active=True,
                ),
                schemas.core.DeploymentSchedule(
                    schedule=schemas.schedules.IntervalSchedule(
                        interval=datetime.timedelta(hours=4)
                    ),
                    active=False,
                ),
            ],
        ),
    )
    await session.commit()
    return deployment


async def test_create_schedules_from_deployment(
    session, deployment_with_active_schedules
):
    active_schedules = [
        s.schedule
        for s in await models.deployments.read_deployment_schedules(
            session=session,
            deployment_id=deployment_with_active_schedules.id,
            deployment_schedule_filter=schemas.filters.DeploymentScheduleFilter(
                active=schemas.filters.DeploymentScheduleFilterActive(eq_=True)
            ),
        )
    ]
    num_active_schedules = len(active_schedules)

    n_runs = await models.flow_runs.count_flow_runs(session)
    assert n_runs == 0

    service = Scheduler()
    await service.start(loops=1)
    runs = await models.flow_runs.read_flow_runs(session)
    assert len(runs) == service.min_runs * num_active_schedules

    expected_dates = set()
    for schedule in active_schedules:
        expected_dates.update(await schedule.get_dates(service.min_runs))
    assert set(expected_dates) == {r.state.state_details.scheduled_time for r in runs}

    assert all(
        [r.state_name == "Scheduled" for r in runs]
    ), "Scheduler sets flow_run.state_name"


async def test_create_schedule_respects_max_future_time(flow, session):
    schedule = schemas.schedules.IntervalSchedule(
        interval=datetime.timedelta(days=30), anchor_date=pendulum.now("UTC")
    )

    await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="test",
            flow_id=flow.id,
            schedules=[
                schemas.core.DeploymentSchedule(
                    schedule=schedule,
                    active=True,
                ),
            ],
        ),
    )
    await session.commit()

    n_runs = await models.flow_runs.count_flow_runs(session)
    assert n_runs == 0
    service = Scheduler()
    await service.start(loops=1)
    runs = await models.flow_runs.read_flow_runs(session)

    assert len(runs) == 3
    expected_dates = await schedule.get_dates(
        service.max_runs, end=pendulum.now("UTC") + service.max_scheduled_time
    )
    assert set(expected_dates) == {r.state.state_details.scheduled_time for r in runs}


async def test_create_schedules_from_multiple_deployments(flow, session):
    schedule1 = schemas.schedules.IntervalSchedule(interval=datetime.timedelta(hours=1))
    schedule2 = schemas.schedules.IntervalSchedule(interval=datetime.timedelta(days=10))
    schedule3 = schemas.schedules.IntervalSchedule(interval=datetime.timedelta(days=5))

    flow_2 = await models.flows.create_flow(
        session=session, flow=schemas.core.Flow(name="flow-2")
    )

    await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="test",
            flow_id=flow.id,
            schedules=[
                schemas.core.DeploymentSchedule(
                    schedule=schedule1,
                    active=True,
                ),
            ],
        ),
    )
    await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="test-2",
            flow_id=flow.id,
            schedules=[
                schemas.core.DeploymentSchedule(
                    schedule=schedule2,
                    active=True,
                ),
            ],
        ),
    )
    await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="test",
            flow_id=flow_2.id,
            schedules=[
                schemas.core.DeploymentSchedule(
                    schedule=schedule3,
                    active=True,
                ),
            ],
        ),
    )
    await session.commit()

    n_runs = await models.flow_runs.count_flow_runs(session)
    assert n_runs == 0

    service = Scheduler()
    await service.start(loops=1)
    runs = await models.flow_runs.read_flow_runs(session)

    expected_dates = set()
    for schedule in [schedule1, schedule2, schedule3]:
        dep_runs = await schedule.get_dates(
            service.min_runs,
            start=pendulum.now("UTC"),
            end=pendulum.now("UTC") + service.max_scheduled_time,
        )
        expected_dates.update(dep_runs)
    assert set(expected_dates) == {r.state.state_details.scheduled_time for r in runs}


async def test_create_schedules_from_multiple_deployments_in_batches(flow, session):
    await models.flows.create_flow(
        session=session, flow=schemas.core.Flow(name="flow-2")
    )

    # create deployments that will have to insert
    # flow runs in batches of scheduler_insertion_batch_size
    deployments_to_schedule = (
        PREFECT_API_SERVICES_SCHEDULER_INSERT_BATCH_SIZE.value()
        // PREFECT_API_SERVICES_SCHEDULER_MIN_RUNS.value()
    ) + 1
    for i in range(deployments_to_schedule):
        await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name=f"test_{i}",
                flow_id=flow.id,
                schedules=[
                    schemas.core.DeploymentSchedule(
                        schedule=schemas.schedules.IntervalSchedule(
                            interval=datetime.timedelta(hours=1)
                        ),
                        active=True,
                    )
                ],
            ),
        )
    await session.commit()

    n_runs = await models.flow_runs.count_flow_runs(session)
    assert n_runs == 0

    # should insert more than the batch size successfully
    await Scheduler().start(loops=1)
    runs = await models.flow_runs.read_flow_runs(session)
    assert (
        len(runs)
        == deployments_to_schedule * PREFECT_API_SERVICES_SCHEDULER_MIN_RUNS.value()
    )
    assert len(runs) > PREFECT_API_SERVICES_SCHEDULER_INSERT_BATCH_SIZE.value()


async def test_scheduler_respects_paused(flow, session):
    await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="test",
            flow_id=flow.id,
            schedules=[
                schemas.core.DeploymentSchedule(
                    schedule=schemas.schedules.IntervalSchedule(
                        interval=datetime.timedelta(hours=1)
                    ),
                    active=True,
                )
            ],
            schedule=schemas.schedules.IntervalSchedule(
                interval=datetime.timedelta(hours=1)
            ),
            paused=True,
        ),
    )
    await session.commit()

    n_runs = await models.flow_runs.count_flow_runs(session)
    assert n_runs == 0

    await Scheduler().start(loops=1)
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
            schedules=[
                schemas.core.DeploymentSchedule(
                    schedule=schemas.schedules.IntervalSchedule(
                        interval=datetime.timedelta(hours=1)
                    ),
                    active=True,
                )
            ],
        ),
    )
    await session.commit()

    n_runs = await models.flow_runs.count_flow_runs(session)
    assert n_runs == 0

    # run multiple loops
    await Scheduler().start(loops=1)
    await Scheduler().start(loops=1)

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
        session, runs[0].id, state=schemas.states.Cancelled()
    )
    await session.commit()

    # run scheduler again
    await Scheduler().start(loops=1)
    runs = await models.flow_runs.read_flow_runs(
        session,
        flow_run_filter=schemas.filters.FlowRunFilter(
            deployment_id=dict(any_=[deployment.id])
        ),
    )
    assert len(runs) == 3
    assert {r.state_type for r in runs} == {"SCHEDULED", "SCHEDULED", "CANCELLED"}


async def test_only_looks_at_deployments_with_active_schedules(
    session,
    deployment_without_schedules,
    deployment_with_inactive_schedules,
    deployment_with_active_schedules,
):
    n_runs = await models.flow_runs.count_flow_runs(session=session)
    assert n_runs == 0

    query = Scheduler()._get_select_deployments_to_schedule_query().limit(10)

    deployment_ids = (await session.execute(query)).scalars().all()
    assert len(deployment_ids) == 1
    assert deployment_ids[0] == deployment_with_active_schedules.id


class TestRecentDeploymentsScheduler:
    async def test_tight_loop_by_default(self):
        assert RecentDeploymentsScheduler().loop_seconds == 5

    async def test_schedules_runs_for_recently_created_deployments(
        self, deployment, session, db
    ):
        recent_scheduler = RecentDeploymentsScheduler()
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
        # artificially move the created time back (updated time will still be recent)
        await session.execute(
            sa.update(db.Deployment)
            .where(db.Deployment.id == deployment.id)
            .values(created=pendulum.now("UTC").subtract(hours=1))
        )
        await session.commit()

        count_query = (
            sa.select(sa.func.count())
            .select_from(db.FlowRun)
            .where(db.FlowRun.deployment_id == deployment.id)
        )

        recent_scheduler = RecentDeploymentsScheduler()
        runs_count = (await session.execute(count_query)).scalar()
        assert runs_count == 0

        await recent_scheduler.start(loops=1)

        runs_count = (await session.execute(count_query)).scalar()
        assert runs_count == recent_scheduler.min_runs

    async def test_schedules_no_runs_for_deployments_updated_a_while_ago(
        self, deployment, session, db
    ):
        # artificially move the updated time back
        await session.execute(
            sa.update(db.Deployment)
            .where(db.Deployment.id == deployment.id)
            .values(updated=pendulum.now("UTC").subtract(minutes=1))
        )
        await session.commit()

        count_query = (
            sa.select(sa.func.count())
            .select_from(db.FlowRun)
            .where(db.FlowRun.deployment_id == deployment.id)
        )

        recent_scheduler = RecentDeploymentsScheduler()
        runs_count = (await session.execute(count_query)).scalar()
        assert runs_count == 0

        await recent_scheduler.start(loops=1)

        runs_count = (await session.execute(count_query)).scalar()
        assert runs_count == 0

    async def test_only_looks_at_deployments_with_active_schedules(
        self,
        session,
        deployment_without_schedules,
        deployment_with_inactive_schedules,
        deployment_with_active_schedules,
    ):
        n_runs = await models.flow_runs.count_flow_runs(session=session)
        assert n_runs == 0

        query = (
            RecentDeploymentsScheduler()
            ._get_select_deployments_to_schedule_query()
            .limit(10)
        )

        deployment_ids = (await session.execute(query)).scalars().all()
        assert len(deployment_ids) == 1
        assert deployment_ids[0] == deployment_with_active_schedules.id


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
        await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="test",
                flow_id=flow.id,
                schedules=[
                    schemas.core.DeploymentSchedule(
                        schedule=schemas.schedules.IntervalSchedule(
                            interval=interval,
                            anchor_date=pendulum.now("UTC").add(seconds=1),
                        ),
                        active=True,
                    )
                ],
            ),
        )
        await session.commit()

        # assert clean slate
        assert (await models.flow_runs.count_flow_runs(session)) == 0

        # run scheduler
        service = Scheduler()
        await service.start(loops=1)

        runs = await models.flow_runs.read_flow_runs(session)
        assert len(runs) == n
