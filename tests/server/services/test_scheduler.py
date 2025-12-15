import datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import models, schemas
from prefect.server.database import PrefectDBInterface
from prefect.server.services.scheduler import (
    schedule_deployments,
    schedule_recent_deployments,
)
from prefect.settings import (
    PREFECT_API_SERVICES_SCHEDULER_INSERT_BATCH_SIZE,
    PREFECT_SERVER_SERVICES_SCHEDULER_RECENT_DEPLOYMENTS_LOOP_SECONDS,
    temporary_settings,
)
from prefect.settings.context import get_current_settings
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
    settings = get_current_settings().server.services.scheduler
    min_runs = settings.min_runs

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

    await schedule_deployments()
    runs = await models.flow_runs.read_flow_runs(session)
    assert len(runs) == min_runs * num_active_schedules

    expected_dates: set[datetime.datetime] = set()
    for schedule in active_schedules:
        expected_dates.update(await schedule.get_dates(min_runs))
    assert set(expected_dates) == {r.state.state_details.scheduled_time for r in runs}

    assert all([r.state_name == "Scheduled" for r in runs]), (
        "Scheduler sets flow_run.state_name"
    )


async def test_create_parametrized_schedules_from_deployment(
    flow: schemas.core.Flow, session: AsyncSession
):
    settings = get_current_settings().server.services.scheduler
    min_runs = settings.min_runs

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

    await schedule_deployments()
    runs = await models.flow_runs.read_flow_runs(session)

    # Should have min_runs from each of the two schedules
    assert len(runs) == 2 * min_runs

    expected_dates = await schedule.get_dates(min_runs)

    for schedule_param_name in ("whoami", "whoami2"):
        schedule_runs = [
            r for r in runs if r.parameters.get("name") == schedule_param_name
        ]
        assert len(schedule_runs) == min_runs

        # Each schedule has overwritten the deployment parameter `name`
        assert all(r.parameters["name"] == schedule_param_name for r in schedule_runs)

        # Each schedule has not changed the other deployment parameters
        assert all(r.parameters["x"] == 11 for r in schedule_runs)

        # Each schedule has scheduled the same datetimes
        assert set(expected_dates) == {
            r.state.state_details.scheduled_time for r in schedule_runs
        }


async def test_create_parametrized_schedules_with_slugs(
    flow: schemas.core.Flow, session: AsyncSession
):
    """Test that schedules with slugs use them in idempotency keys, and schedules without slugs fall back to ID"""
    settings = get_current_settings().server.services.scheduler
    min_runs = settings.min_runs

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

    await schedule_deployments()
    runs = await models.flow_runs.read_flow_runs(session)

    # We should get min_runs * 2 because we have two schedules
    assert len(runs) == min_runs * 2

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
    expected_dates = await schedule.get_dates(min_runs)
    for date in expected_dates:
        # Find runs for this date
        date_runs = [r for r in runs if r.state.state_details.scheduled_time == date]
        assert len(date_runs) == 2  # Should have two runs per date

        # One run should use the schedule ID in its idempotency key
        assert any(
            f"scheduled {deployment.id} {schedule_with_slug.id} {date}"
            == r.idempotency_key
            for r in date_runs
        )
        # The other run should use its schedule ID
        assert any(
            f"scheduled {deployment.id} {schedule_without_slug.id} {date}"
            == r.idempotency_key
            for r in date_runs
        )


async def test_create_schedule_respects_max_future_time(
    flow: schemas.core.Flow, session: AsyncSession
):
    settings = get_current_settings().server.services.scheduler
    max_scheduled_time = settings.max_scheduled_time
    min_runs = settings.min_runs

    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="test",
            flow_id=flow.id,
            schedules=[
                schemas.core.DeploymentSchedule(
                    schedule=schemas.schedules.IntervalSchedule(
                        interval=datetime.timedelta(days=30)
                    ),
                    active=True,
                )
            ],
        ),
    )
    await session.commit()

    n_runs = await models.flow_runs.count_flow_runs(session)
    assert n_runs == 0

    await schedule_deployments()
    runs = await models.flow_runs.read_flow_runs(session)
    # the schedule would generate 100 runs, but we limit it to min_runs
    # since they would all be past the max_scheduled_time
    assert len(runs) == min_runs

    # runs for this deployment should be no more than max_scheduled_time in the future
    deployment_runs = [r for r in runs if r.deployment_id == deployment.id]
    assert all(
        r.state.state_details.scheduled_time < now("UTC") + max_scheduled_time
        for r in deployment_runs
    )


async def test_create_schedules_from_multiple_deployments(
    flow: schemas.core.Flow,
    session: AsyncSession,
    deployment_without_schedules,
    deployment_with_active_schedules,
    deployment_with_inactive_schedules,
):
    settings = get_current_settings().server.services.scheduler
    min_runs = settings.min_runs

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

    await schedule_deployments()
    runs = await models.flow_runs.read_flow_runs(session)
    # min_runs per active schedule - only the active deployment had active schedules
    assert len(runs) == min_runs * num_active_schedules

    # confirm that the runs are for the active deployment
    assert all(r.deployment_id == deployment_with_active_schedules.id for r in runs)


async def test_create_schedules_from_multiple_deployments_in_batches(flow, session):
    settings = get_current_settings().server.services.scheduler
    min_runs = settings.min_runs

    for i in range(10):
        await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name=f"test-{i}",
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

    with temporary_settings(
        {
            PREFECT_API_SERVICES_SCHEDULER_INSERT_BATCH_SIZE: 7,
        }
    ):
        await schedule_deployments()

    runs = await models.flow_runs.read_flow_runs(session)
    assert len(runs) == 10 * min_runs


async def test_scheduler_respects_paused(
    session: AsyncSession,
    deployment_with_active_schedules: schemas.core.Deployment,
):
    # pause the deployment
    await models.deployments.update_deployment(
        session=session,
        deployment_id=deployment_with_active_schedules.id,
        deployment=schemas.actions.DeploymentUpdate(paused=True),
    )
    await session.commit()

    n_runs = await models.flow_runs.count_flow_runs(session)
    assert n_runs == 0

    await schedule_deployments()
    runs = await models.flow_runs.read_flow_runs(session)
    assert len(runs) == 0


async def test_scheduler_runs_when_too_few_scheduled_runs_but_doesnt_overwrite(
    flow: schemas.core.Flow,
    session: AsyncSession,
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
    await schedule_deployments()
    await schedule_deployments()

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
    await schedule_deployments()
    runs = await models.flow_runs.read_flow_runs(
        session,
        flow_run_filter=schemas.filters.FlowRunFilter(
            deployment_id=dict(any_=[deployment.id])
        ),
    )
    assert len(runs) == 3
    assert {r.state_type for r in runs} == {"SCHEDULED", "SCHEDULED", "CANCELLED"}


async def test_only_looks_at_deployments_with_active_schedules(
    session: AsyncSession,
    deployment_with_active_schedules: schemas.core.Deployment,
    deployment_with_inactive_schedules: schemas.core.Deployment,
    deployment_without_schedules: schemas.core.Deployment,
):
    await schedule_deployments()
    runs = await models.flow_runs.read_flow_runs(session)
    # only the active deployment should have runs
    assert all(r.deployment_id == deployment_with_active_schedules.id for r in runs)


class TestRecentDeploymentsScheduler:
    async def test_recent_scheduler_picks_up_recent_deployments(
        self,
        flow: schemas.core.Flow,
        session: AsyncSession,
    ):
        settings = get_current_settings().server.services.scheduler
        min_runs = settings.min_runs

        await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="new deployment",
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

        await schedule_recent_deployments()
        runs = await models.flow_runs.read_flow_runs(session)
        assert len(runs) == min_runs

    async def test_recent_scheduler_ignores_deployments_with_inactive_schedules(
        self, session, deployment_with_inactive_schedules
    ):
        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == 0

        await schedule_recent_deployments()
        runs = await models.flow_runs.read_flow_runs(session)
        assert len(runs) == 0

    async def test_recent_scheduler_ignores_old_deployments(
        self,
        db: PrefectDBInterface,
        flow: schemas.core.Flow,
        session: AsyncSession,
    ):
        settings = get_current_settings().server.services.scheduler
        recent_loop_seconds = settings.recent_deployments_loop_seconds

        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="old deployment",
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
        # Set the deployment's updated time to be older than the recent loop
        old_time = now("UTC") - datetime.timedelta(seconds=recent_loop_seconds + 10)
        await session.execute(
            sa.update(db.Deployment)
            .where(db.Deployment.id == deployment.id)
            .values(updated=old_time)
        )
        await session.commit()

        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == 0

        await schedule_recent_deployments()
        runs = await models.flow_runs.read_flow_runs(session)
        # Should not pick up old deployment
        assert len(runs) == 0

    async def test_recent_scheduler_works_within_expected_loop_interval(
        self,
        flow: schemas.core.Flow,
        session: AsyncSession,
    ):
        """
        Verifies that the recent scheduler picks up deployments created within
        PREFECT_SERVER_SERVICES_SCHEDULER_RECENT_DEPLOYMENTS_LOOP_SECONDS + 1 seconds
        """
        settings = get_current_settings().server.services.scheduler
        min_runs = settings.min_runs

        await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="new deployment",
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

        # Use a long loop interval to ensure the deployment is picked up
        with temporary_settings(
            {PREFECT_SERVER_SERVICES_SCHEDULER_RECENT_DEPLOYMENTS_LOOP_SECONDS: 60}
        ):
            await schedule_recent_deployments()

        runs = await models.flow_runs.read_flow_runs(session)
        assert len(runs) == min_runs


class TestScheduleRulesWaterfall:
    """
    These tests verify the scheduling waterfall, which is:

    - Runs will be generated starting on or after the `start_time`
    - No more than `max_runs` runs will be generated
    - No runs will be generated after `end_time` is reached
    - At least `min_runs` runs will be generated
    - Runs will be generated until at least `start_time + min_time` is reached
    """

    @pytest.fixture
    async def deployment(self, flow: schemas.core.Flow, session: AsyncSession):
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="hourly",
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
        return deployment

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
                            anchor_date=now("UTC") + datetime.timedelta(seconds=1),
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
        await schedule_deployments()

        runs = await models.flow_runs.read_flow_runs(session)
        assert len(runs) == n

    async def test_min_runs_honored_when_min_time_reached(
        self, session: AsyncSession, deployment: schemas.core.Deployment
    ):
        """When min_time would not produce enough runs, min_runs takes precedence."""
        settings = get_current_settings().server.services.scheduler
        min_runs = settings.min_runs

        await schedule_deployments()

        runs = await models.flow_runs.read_flow_runs(session)
        # With hourly schedule and min_runs=3 (default), we should have at least 3 runs
        assert len(runs) >= min_runs
