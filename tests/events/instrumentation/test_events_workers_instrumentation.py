import pendulum

from prefect import __version__
from prefect.client.orchestration import PrefectClient
from prefect.events.clients import AssertingEventsClient
from prefect.events.worker import EventsWorker
from prefect.states import Scheduled
from prefect.testing.utilities import AsyncMock
from prefect.workers.base import BaseJobConfiguration, BaseWorker, BaseWorkerResult


class WorkerEventsTestImpl(BaseWorker):
    type = "events-test"
    job_configuration = BaseJobConfiguration

    async def run(self):
        pass

    async def verify_submitted_deployment(self, deployment):
        pass


async def test_worker_emits_submitted_event(
    asserting_events_worker: EventsWorker,
    reset_worker_events,
    orion_client: PrefectClient,
    worker_deployment_wq1,
    work_pool,
):
    flow_run = await orion_client.create_flow_run_from_deployment(
        worker_deployment_wq1.id,
        state=Scheduled(scheduled_time=pendulum.now("utc")),
        tags=["flow-run-one"],
    )

    flow = await orion_client.read_flow(flow_run.flow_id)

    async with WorkerEventsTestImpl(work_pool_name=work_pool.name) as worker:
        worker._work_pool = work_pool
        worker.run = AsyncMock()
        await worker.get_and_submit_flow_runs()

    asserting_events_worker.drain()

    assert isinstance(asserting_events_worker._client, AssertingEventsClient)

    # When a worker submits a flow-run it also monitors that flow run until it's
    # complete. When it's complete it fires a second 'monitored' event, which
    # is covered by the test_worker_emits_monitored_event below.
    assert len(asserting_events_worker._client.events) == 2

    submit_event = asserting_events_worker._client.events[0]
    assert submit_event.event == "prefect.worker.submitted-flow-run"

    assert dict(submit_event.resource.items()) == {
        "prefect.resource.id": f"prefect.worker.events-test.{worker.get_name_slug()}",
        "prefect.resource.name": worker.name,
        "prefect.version": str(__version__),
        "prefect.worker-type": worker.type,
    }

    assert len(submit_event.related) == 6

    related = [dict(r.items()) for r in submit_event.related]

    assert related == [
        {
            "prefect.resource.id": f"prefect.deployment.{worker_deployment_wq1.id}",
            "prefect.resource.role": "deployment",
            "prefect.resource.name": worker_deployment_wq1.name,
        },
        {
            "prefect.resource.id": f"prefect.flow.{flow.id}",
            "prefect.resource.role": "flow",
            "prefect.resource.name": flow.name,
        },
        {
            "prefect.resource.id": f"prefect.flow-run.{flow_run.id}",
            "prefect.resource.role": "flow-run",
            "prefect.resource.name": flow_run.name,
        },
        {
            "prefect.resource.id": "prefect.tag.flow-run-one",
            "prefect.resource.role": "tag",
        },
        {
            "prefect.resource.id": "prefect.tag.test",
            "prefect.resource.role": "tag",
        },
        {
            "prefect.resource.id": f"prefect.work-pool.{work_pool.id}",
            "prefect.resource.role": "work-pool",
            "prefect.resource.name": work_pool.name,
        },
    ]


async def test_worker_emits_monitored_event(
    asserting_events_worker: EventsWorker,
    reset_worker_events,
    orion_client: PrefectClient,
    worker_deployment_wq1,
    work_pool,
):
    flow_run = await orion_client.create_flow_run_from_deployment(
        worker_deployment_wq1.id,
        state=Scheduled(scheduled_time=pendulum.now("utc")),
        tags=["flow-run-one"],
    )

    flow = await orion_client.read_flow(flow_run.flow_id)

    worker_result = BaseWorkerResult(status_code=1, identifier="process123")
    run_flow_fn = AsyncMock(return_value=worker_result)

    async with WorkerEventsTestImpl(work_pool_name=work_pool.name) as worker:
        worker._work_pool = work_pool
        worker.run = run_flow_fn
        await worker.get_and_submit_flow_runs()

    asserting_events_worker.drain()

    assert isinstance(asserting_events_worker._client, AssertingEventsClient)

    # When a worker submits a flow-run it also monitors that flow run until
    # it's complete. When it's submits it fires a 'sumbitted' event,
    # which is covered by the test_worker_emits_submitted_event above.
    assert len(asserting_events_worker._client.events) == 2

    monitored_event = asserting_events_worker._client.events[1]
    assert monitored_event.event == "prefect.worker.executed-flow-run"

    assert dict(monitored_event.resource.items()) == {
        "prefect.resource.id": f"prefect.worker.events-test.{worker.get_name_slug()}",
        "prefect.resource.name": worker.name,
        "prefect.version": str(__version__),
        "prefect.worker-type": worker.type,
    }

    assert len(monitored_event.related) == 6

    related = [dict(r.items()) for r in monitored_event.related]

    assert related == [
        {
            "prefect.resource.id": f"prefect.deployment.{worker_deployment_wq1.id}",
            "prefect.resource.role": "deployment",
            "prefect.resource.name": worker_deployment_wq1.name,
        },
        {
            "prefect.resource.id": f"prefect.flow.{flow.id}",
            "prefect.resource.role": "flow",
            "prefect.resource.name": flow.name,
        },
        {
            "prefect.resource.id": f"prefect.flow-run.{flow_run.id}",
            "prefect.resource.role": "flow-run",
            "prefect.resource.name": flow_run.name,
            "prefect.infrastructure.status-code": "1",
            "prefect.infrastructure.identifier": "process123",
        },
        {
            "prefect.resource.id": "prefect.tag.flow-run-one",
            "prefect.resource.role": "tag",
        },
        {
            "prefect.resource.id": "prefect.tag.test",
            "prefect.resource.role": "tag",
        },
        {
            "prefect.resource.id": f"prefect.work-pool.{work_pool.id}",
            "prefect.resource.role": "work-pool",
            "prefect.resource.name": work_pool.name,
        },
    ]
