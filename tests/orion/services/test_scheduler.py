import datetime

import pendulum

from prefect.orion import models, schemas
from prefect.orion.schemas.data import DataDocument
from prefect.orion.services.scheduler import Scheduler
from prefect.settings import (
    PREFECT_ORION_SERVICES_SCHEDULER_INSERT_BATCH_SIZE,
    PREFECT_ORION_SERVICES_SCHEDULER_MAX_RUNS,
    PREFECT_ORION_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME,
)


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

    service = Scheduler()
    await service.start(loops=1)
    runs = await models.flow_runs.read_flow_runs(session)
    assert len(runs) == 100 == service.max_runs
    expected_dates = await deployment.schedule.get_dates(service.max_runs)
    assert set(expected_dates) == {r.state.state_details.scheduled_time for r in runs}

    assert all(
        [r.state_name == "Scheduled" for r in runs]
    ), "Scheduler sets flow_run.state_name"


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
    service = Scheduler()
    await service.start(loops=1)
    runs = await models.flow_runs.read_flow_runs(session)

    assert len(runs) == 3
    expected_dates = await deployment.schedule.get_dates(
        service.max_runs, end=pendulum.now() + service.max_scheduled_time
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

    service = Scheduler()
    await service.start(loops=1)
    runs = await models.flow_runs.read_flow_runs(session)
    assert len(runs) == 130

    expected_dates = set()
    for deployment in [d1, d2, d3]:
        dep_runs = await deployment.schedule.get_dates(
            service.max_runs,
            start=pendulum.now(),
            end=pendulum.now() + service.max_scheduled_time,
        )
        expected_dates.update(dep_runs)
    assert set(expected_dates) == {r.state.state_details.scheduled_time for r in runs}


async def test_create_schedules_from_multiple_deployments_in_batches(
    flow, session, flow_function
):
    flow_2 = await models.flows.create_flow(
        session=session, flow=schemas.core.Flow(name="flow-2")
    )

    # create deployments that will have to insert
    # flow runs in batches of scheduler_insertion_batch_size
    deployments_to_schedule = (
        PREFECT_ORION_SERVICES_SCHEDULER_INSERT_BATCH_SIZE.value()
        // PREFECT_ORION_SERVICES_SCHEDULER_MAX_RUNS.value()
    ) + 1
    for i in range(deployments_to_schedule):
        await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name=f"test_{i}",
                flow_id=flow.id,
                flow_data=DataDocument.encode("cloudpickle", flow_function),
                schedule=schemas.schedules.IntervalSchedule(
                    # assumes this interval is small enough that
                    # the maximum amount of runs will be scheduled per deployment
                    interval=datetime.timedelta(minutes=5)
                ),
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
        == deployments_to_schedule * PREFECT_ORION_SERVICES_SCHEDULER_MAX_RUNS.value()
    )
    assert len(runs) > PREFECT_ORION_SERVICES_SCHEDULER_INSERT_BATCH_SIZE.value()


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
