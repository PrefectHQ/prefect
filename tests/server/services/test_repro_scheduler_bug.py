"""
Regression test for multi-schedule deployments where high-frequency
schedules stop producing runs because the scheduler's deployment
selection query checked aggregate run counts across all schedules
instead of per-schedule counts.
"""

import datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import models, schemas
from prefect.server.database import PrefectDBInterface
from prefect.server.services.scheduler import (
    _get_select_deployments_to_schedule_query,
    schedule_deployments,
)
from prefect.settings import (
    PREFECT_API_SERVICES_SCHEDULER_MAX_RUNS,
    PREFECT_API_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME,
    PREFECT_API_SERVICES_SCHEDULER_MIN_RUNS,
    PREFECT_API_SERVICES_SCHEDULER_MIN_SCHEDULED_TIME,
    temporary_settings,
)
from prefect.settings.context import get_current_settings


async def test_scheduler_selects_deployment_when_one_schedule_exhausted(
    flow: schemas.core.Flow,
    session: AsyncSession,
    db: PrefectDBInterface,
):
    """
    When a deployment has multiple schedules with different frequencies,
    and the high-frequency schedule's runs are consumed (no longer SCHEDULED),
    the scheduler query should still select the deployment for re-scheduling.

    Previously, the query checked aggregate count/max_time across ALL schedules,
    so a deployment would not be re-selected if other schedules still had plenty
    of future runs - even though one schedule was completely starved.
    """
    with temporary_settings(
        {
            PREFECT_API_SERVICES_SCHEDULER_MAX_RUNS: 5,
            PREFECT_API_SERVICES_SCHEDULER_MIN_RUNS: 3,
            PREFECT_API_SERVICES_SCHEDULER_MIN_SCHEDULED_TIME: datetime.timedelta(
                hours=1
            ),
            PREFECT_API_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME: datetime.timedelta(
                days=100
            ),
        }
    ):
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="three-schedules",
                flow_id=flow.id,
                schedules=[
                    schemas.core.DeploymentSchedule(
                        schedule=schemas.schedules.IntervalSchedule(
                            interval=datetime.timedelta(minutes=15),
                        ),
                        active=True,
                    ),
                    schemas.core.DeploymentSchedule(
                        schedule=schemas.schedules.IntervalSchedule(
                            interval=datetime.timedelta(hours=2),
                        ),
                        active=True,
                    ),
                    schemas.core.DeploymentSchedule(
                        schedule=schemas.schedules.IntervalSchedule(
                            interval=datetime.timedelta(hours=6),
                        ),
                        active=True,
                    ),
                ],
            ),
        )
        await session.commit()

        dep_schedules = await models.deployments.read_deployment_schedules(
            session=session,
            deployment_id=deployment.id,
            deployment_schedule_filter=schemas.filters.DeploymentScheduleFilter(
                active=schemas.filters.DeploymentScheduleFilterActive(eq_=True)
            ),
        )

        freq_schedule = next(
            s
            for s in dep_schedules
            if s.schedule.interval == datetime.timedelta(minutes=15)
        )

        # Initial scheduling
        await schedule_deployments()

        runs = await models.flow_runs.read_flow_runs(session)
        assert len(runs) == 11  # 5 + 3 + 3

        # After initial scheduling, deployment should NOT need more runs
        settings = get_current_settings().server.services.scheduler
        query = _get_select_deployments_to_schedule_query(
            db,
            settings.deployment_batch_size,
            settings.min_runs,
            settings.min_scheduled_time,
        )
        result = await session.execute(query)
        assert len(result.scalars().all()) == 0

        # Now mark the frequent schedule's runs as completed
        freq_runs = [r for r in runs if str(freq_schedule.id) in r.idempotency_key]
        assert len(freq_runs) == 5

        for r in freq_runs:
            await models.flow_runs.set_flow_run_state(
                session, r.id, state=schemas.states.Completed()
            )
        await session.commit()

        # The query should now select the deployment because the frequent
        # schedule has 0 SCHEDULED runs (< min_runs=3)
        query2 = _get_select_deployments_to_schedule_query(
            db,
            settings.deployment_batch_size,
            settings.min_runs,
            settings.min_scheduled_time,
        )
        result2 = await session.execute(query2)
        selected = result2.scalars().all()
        assert len(selected) == 1, (
            "Deployment should be selected when one schedule has no SCHEDULED runs"
        )
        assert selected[0] == deployment.id


async def test_scheduler_generates_new_runs_after_time_passes(
    flow: schemas.core.Flow,
    session: AsyncSession,
    db: PrefectDBInterface,
):
    """
    End-to-end test: after a high-frequency schedule's runs are consumed
    and time has passed, the scheduler should generate new future runs
    for that schedule.

    We simulate time passing by deleting the completed runs (so idempotency
    keys don't conflict) - in the real world, new dates would be generated
    because start_time=now() would have advanced.
    """
    with temporary_settings(
        {
            PREFECT_API_SERVICES_SCHEDULER_MAX_RUNS: 5,
            PREFECT_API_SERVICES_SCHEDULER_MIN_RUNS: 3,
            PREFECT_API_SERVICES_SCHEDULER_MIN_SCHEDULED_TIME: datetime.timedelta(
                hours=1
            ),
            PREFECT_API_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME: datetime.timedelta(
                days=100
            ),
        }
    ):
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="three-schedules-e2e",
                flow_id=flow.id,
                schedules=[
                    schemas.core.DeploymentSchedule(
                        schedule=schemas.schedules.IntervalSchedule(
                            interval=datetime.timedelta(minutes=15),
                        ),
                        active=True,
                    ),
                    schemas.core.DeploymentSchedule(
                        schedule=schemas.schedules.IntervalSchedule(
                            interval=datetime.timedelta(hours=6),
                        ),
                        active=True,
                    ),
                ],
            ),
        )
        await session.commit()

        dep_schedules = await models.deployments.read_deployment_schedules(
            session=session,
            deployment_id=deployment.id,
            deployment_schedule_filter=schemas.filters.DeploymentScheduleFilter(
                active=schemas.filters.DeploymentScheduleFilterActive(eq_=True)
            ),
        )

        freq_schedule = next(
            s
            for s in dep_schedules
            if s.schedule.interval == datetime.timedelta(minutes=15)
        )

        # Initial scheduling
        await schedule_deployments()

        runs = await models.flow_runs.read_flow_runs(session)
        freq_runs = [r for r in runs if str(freq_schedule.id) in r.idempotency_key]
        assert len(freq_runs) == 5

        # Simulate: time passes, frequent runs complete and are deleted
        # (In reality, now() would advance and produce different dates,
        # but we delete to avoid idempotency key conflicts in the test)
        for r in freq_runs:
            await session.execute(sa.delete(db.FlowRun).where(db.FlowRun.id == r.id))
        await session.commit()

        # Run scheduler again - should regenerate runs for the frequent schedule
        await schedule_deployments()

        all_runs = await models.flow_runs.read_flow_runs(session)
        scheduled = [
            r for r in all_runs if r.state_type == schemas.states.StateType.SCHEDULED
        ]
        freq_scheduled = [
            r for r in scheduled if str(freq_schedule.id) in r.idempotency_key
        ]

        assert len(freq_scheduled) > 0, (
            "After deleting consumed runs, the scheduler should create new runs "
            "for the frequent schedule."
        )
