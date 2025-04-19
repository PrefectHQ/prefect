import datetime
from datetime import timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import models, schemas
from prefect.server.database import PrefectDBInterface
from prefect.server.services.scheduler import RecentDeploymentsScheduler, Scheduler
from prefect.settings import (
    PREFECT_API_SERVICES_SCHEDULER_INSERT_BATCH_SIZE,
    PREFECT_API_SERVICES_SCHEDULER_MIN_RUNS,
    PREFECT_SERVER_SERVICES_SCHEDULER_RECENT_DEPLOYMENTS_LOOP_SECONDS,
    temporary_settings,
)
from prefect.types._datetime import now
from prefect.utilities.callables import parameter_schema


@pytest.fixture
async def deployment_without_schedules(flow: schemas.core.Flow, session: AsyncSession):
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
async def deployment_with_inactive_schedules(
    flow: schemas.core.Flow, session: AsyncSession
):
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
async def deployment_with_active_schedules(
    flow: schemas.core.Flow, session: AsyncSession
):
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
    session: AsyncSession,
    deployment_with_active_schedules: schemas.core.Deployment,
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

    expected_dates: set[datetime.datetime] = set()
    for schedule in active_schedules:
        expected_dates.update(await schedule.get_dates(service.min_runs))
    assert set(expected_dates) == {r.state.state_details.scheduled_time for r in runs}

    assert all([r.state_name == "Scheduled" for r in runs]), (
        "Scheduler sets flow_run.state_name"
    )


async def test_create_parametrized_schedules_from_deployment(
    flow: schemas.core.Flow, session: AsyncSession
):
    schedule = schemas.schedules.IntervalSchedule(
        interval=datetime.timedelta(days=30),
        anchor_date=now("UTC"),
    )

    def func_for_params(name: str, x: int = 42):
        pass

    param_schema = parameter_schema(func_for_params).model_dump_for_openapi()

    await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="test",
            flow_id=flow.id,
            parameters={"name": "deployment-test", "x": 11},
            parameter_openapi_schema=param_schema,
            schedules=[
                schemas.core.DeploymentSchedule(
                    schedule=schedule,
                    parameters={"name": "whoami"},
                    active=True,
                ),
                schemas.core.DeploymentSchedule(
                    schedule=schedule,  # Same schedule/timing
                    parameters={"name": "whoami2"},  # Different parameters
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

    # We expect min_runs * 2 because we have two schedules
    # However, we only get min_runs because the second schedule's runs
    # overwrite the first schedule's runs due to having the same idempotency key
    # (scheduled {deployment.id} {date})
    assert len(runs) == service.min_runs * 2  # Should create runs for both schedules

    expected_dates = await schedule.get_dates(service.min_runs)
    # Each expected date should have two runs with different parameters
    assert set(expected_dates) == {r.state.state_details.scheduled_time for r in runs}

    # Check that we have runs with both sets of parameters
    run_params = {(r.parameters["name"], r.parameters["x"]) for r in runs}
    assert run_params == {("whoami", 11), ("whoami2", 11)}

    assert all([r.state_name == "Scheduled" for r in runs]), (
        "Scheduler sets flow_run.state_name"
    )


async def test_create_parametrized_schedules_with_slugs(
    flow: schemas.core.Flow, session: AsyncSession
):
    """Test that schedules with slugs use them in idempotency keys, and schedules without slugs fall back to ID"""
    schedule = schemas.schedules.IntervalSchedule(
        interval=datetime.timedelta(days=30),
        anchor_date=now("UTC"),
    )

    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="test",
            flow_id=flow.id,
            parameters={"name": "deployment-test", "x": 11},
            schedules=[
                schemas.core.DeploymentSchedule(
                    schedule=schedule,
                    parameters={"name": "whoami"},
                    slug="my-schedule",
                    active=True,
                ),
                schemas.core.DeploymentSchedule(
                    schedule=schedule,  # Same schedule/timing
                    parameters={"name": "whoami2"},  # Different parameters
                    active=True,  # No slug on this one
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

    # We should get min_runs * 2 because we have two schedules
    assert len(runs) == service.min_runs * 2

    # Check that we have runs with both sets of parameters
    run_params = {(r.parameters["name"], r.parameters["x"]) for r in runs}
    assert run_params == {("whoami", 11), ("whoami2", 11)}

    # Get the deployment schedules to check their IDs/slugs
    schedules = await models.deployments.read_deployment_schedules(
        session=session,
        deployment_id=deployment.id,
    )
    schedule_with_slug = next(s for s in schedules if s.slug == "my-schedule")
    schedule_without_slug = next(s for s in schedules if not s.slug)

    # Verify the schedule with slug has the expected properties
    assert schedule_with_slug.slug == "my-schedule"
    assert schedule_with_slug.parameters == {"name": "whoami"}
    assert schedule_with_slug.active is True

    # Check that idempotency keys use slugs when available and IDs when not
    expected_dates = await schedule.get_dates(service.min_runs)
    for date in expected_dates:
        # Find runs for this date
        date_runs = [r for r in runs if r.state.state_details.scheduled_time == date]
        assert len(date_runs) == 2  # Should have two runs per date

        # One run should use the slug in its idempotency key
        assert any(
            f"scheduled {deployment.id} {schedule_with_slug.id} {date}"
            == r.idempotency_key
            for r in date_runs
        )
        # One run should use the ID in its idempotency key
        assert any(
            f"scheduled {deployment.id} {schedule_without_slug.id} {date}"
            == r.idempotency_key
            for r in date_runs
        )


async def test_create_schedule_respects_max_future_time(
    flow: schemas.core.Flow, session: AsyncSession
):
    schedule = schemas.schedules.IntervalSchedule(
        interval=datetime.timedelta(days=30), anchor_date=now("UTC")
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
        service.max_runs,
        end=datetime.datetime.now(timezone.utc) + service.max_scheduled_time,
    )
    assert set(expected_dates) == {r.state.state_details.scheduled_time for r in runs}


async def test_create_schedules_from_multiple_deployments(
    flow: schemas.core.Flow, session: AsyncSession
):
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
            start=datetime.datetime.now(timezone.utc),
            end=datetime.datetime.now(timezone.utc) + service.max_scheduled_time,
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


async def test_scheduler_respects_paused(
    flow: schemas.core.Flow, session: AsyncSession
):
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
    flow: schemas.core.Flow, session: AsyncSession
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


@pytest.mark.usefixtures(
    "deployment_without_schedules", "deployment_with_inactive_schedules"
)
async def test_only_looks_at_deployments_with_active_schedules(
    session: AsyncSession,
    deployment_with_active_schedules: schemas.core.Deployment,
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

    async def test_tight_loop_can_be_configured(self):
        assert RecentDeploymentsScheduler(loop_seconds=1).loop_seconds == 1

        with temporary_settings(
            {PREFECT_SERVER_SERVICES_SCHEDULER_RECENT_DEPLOYMENTS_LOOP_SECONDS: 42}
        ):
            assert RecentDeploymentsScheduler().loop_seconds == 42

    async def test_schedules_runs_for_recently_created_deployments(
        self,
        deployment: schemas.core.Deployment,
        session: AsyncSession,
        db: PrefectDBInterface,
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
        self,
        deployment: schemas.core.Deployment,
        session: AsyncSession,
        db: PrefectDBInterface,
    ):
        # artificially move the created time back (updated time will still be recent)
        await session.execute(
            sa.update(db.Deployment)
            .where(db.Deployment.id == deployment.id)
            .values(
                created=datetime.datetime.now(timezone.utc)
                - datetime.timedelta(hours=1)
            )
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
        self,
        deployment: schemas.core.Deployment,
        session: AsyncSession,
        db: PrefectDBInterface,
    ):
        # artificially move the updated time back
        await session.execute(
            sa.update(db.Deployment)
            .where(db.Deployment.id == deployment.id)
            .values(
                updated=datetime.datetime.now(timezone.utc)
                - datetime.timedelta(minutes=1)
            )
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
        session: AsyncSession,
        db: PrefectDBInterface,
        deployment_without_schedules: schemas.core.Deployment,
        deployment_with_inactive_schedules: schemas.core.Deployment,
        deployment_with_active_schedules: schemas.core.Deployment,
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
        self,
        flow: schemas.core.Flow,
        session: AsyncSession,
        interval: datetime.timedelta,
        n: int,
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
                            anchor_date=datetime.datetime.now(timezone.utc)
                            + datetime.timedelta(seconds=1),
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
