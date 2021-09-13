import sqlalchemy as sa
import datetime
import pendulum
from prefect.orion import models, schemas
from prefect.orion.services.scheduler import Scheduler
from prefect.orion.schemas.data import DataDocument


async def test_create_schedules_from_deployment(flow, session, flow_function):
    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="test",
            flow_id=flow.id,
            flow_data=DataDocument.encode("cloudpickle", flow_function),
            schedule=schemas.schedules.IntervalSchedule(
                interval=datetime.timedelta(hours=1)
            ),
        ),
    )
    await session.commit()

    n_runs = await models.flow_runs.count_flow_runs(session)
    assert n_runs == 0

    await Scheduler().start(loops=1)
    runs = await models.flow_runs.read_flow_runs(session)
    assert len(runs) == 100 == Scheduler.max_runs
    expected_dates = await deployment.schedule.get_dates(Scheduler.max_runs)
    assert set(expected_dates) == {r.state.state_details.scheduled_time for r in runs}


async def test_create_schedule_respects_max_future_time(flow, session, flow_function):
    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="test",
            flow_id=flow.id,
            flow_data=DataDocument.encode("cloudpickle", flow_function),
            schedule=schemas.schedules.IntervalSchedule(
                interval=datetime.timedelta(days=30),
                anchor_date=pendulum.now("UTC"),
            ),
        ),
    )
    await session.commit()

    n_runs = await models.flow_runs.count_flow_runs(session)
    assert n_runs == 0
    await Scheduler().start(loops=1)
    runs = await models.flow_runs.read_flow_runs(session)

    assert len(runs) == 3
    expected_dates = await deployment.schedule.get_dates(
        Scheduler.max_runs, end=pendulum.now().add(seconds=Scheduler.max_future_seconds)
    )
    assert set(expected_dates) == {r.state.state_details.scheduled_time for r in runs}


async def test_create_schedules_from_multiple_deployments(flow, session, flow_function):
    flow_2 = await models.flows.create_flow(
        session=session, flow=schemas.core.Flow(name="flow-2")
    )

    d1 = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="test",
            flow_id=flow.id,
            flow_data=DataDocument.encode("cloudpickle", flow_function),
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
            flow_data=DataDocument.encode("cloudpickle", flow_function),
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
            flow_data=DataDocument.encode("cloudpickle", flow_function),
            schedule=schemas.schedules.IntervalSchedule(
                interval=datetime.timedelta(days=5)
            ),
        ),
    )
    await session.commit()

    n_runs = await models.flow_runs.count_flow_runs(session)
    assert n_runs == 0

    await Scheduler().start(loops=1)
    runs = await models.flow_runs.read_flow_runs(session)
    assert len(runs) == 130

    expected_dates = set()
    for deployment in [d1, d2, d3]:
        dep_runs = await deployment.schedule.get_dates(
            Scheduler.max_runs,
            start=pendulum.now(),
            end=pendulum.now().add(seconds=Scheduler.max_future_seconds),
        )
        expected_dates.update(dep_runs)
    assert set(expected_dates) == {r.state.state_details.scheduled_time for r in runs}


async def test_scheduler_respects_schedule_is_active(flow, session, flow_function):
    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="test",
            flow_id=flow.id,
            flow_data=DataDocument.encode("cloudpickle", flow_function),
            schedule=schemas.schedules.IntervalSchedule(
                interval=datetime.timedelta(hours=1)
            ),
            is_schedule_active=False,
        ),
    )
    await session.commit()

    n_runs = await models.flow_runs.count_flow_runs(session)
    assert n_runs == 0

    await Scheduler().start(loops=1)
    n_runs_2 = await models.flow_runs.count_flow_runs(session)
    assert n_runs_2 == 0
