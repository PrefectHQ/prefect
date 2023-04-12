import pendulum

from prefect import __version__
from prefect.client.orchestration import PrefectClient
from prefect.events.clients import AssertingEventsClient
from prefect.events.worker import EventsWorker
from prefect.states import Scheduled
from prefect.testing.utilities import AsyncMock
from prefect.workers.base import BaseJobConfiguration, BaseWorker


class WorkerEventsTestImpl(BaseWorker):
    type = "events-test"
    job_configuration = BaseJobConfiguration

    async def run(self):
        pass

    async def verify_submitted_deployment(self, deployment):
        pass


async def test_worker_calls_run_with_expected_arguments(
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
    assert len(asserting_events_worker._client.events) == 1

    submit_event = asserting_events_worker._client.events[0]
    assert submit_event.event == "prefect.worker.submitted-flow-run"

    assert dict(submit_event.resource.items()) == {
        "prefect.resource.id": f"prefect.worker.events-test.{worker.get_name_slug()}",
        "prefect.name": worker.name,
        "prefect.version": str(__version__),
        "prefect.worker-type": worker.type,
    }

    assert len(submit_event.related) == 6

    related = [dict(r.items()) for r in submit_event.related]

    assert related == [
        {
            "prefect.resource.id": f"prefect.deployment.{worker_deployment_wq1.id}",
            "prefect.resource.role": "deployment",
            "prefect.name": worker_deployment_wq1.name,
        },
        {
            "prefect.resource.id": f"prefect.flow.{flow.id}",
            "prefect.resource.role": "flow",
            "prefect.name": flow.name,
        },
        {
            "prefect.resource.id": f"prefect.flow-run.{flow_run.id}",
            "prefect.resource.role": "flow-run",
            "prefect.name": flow_run.name,
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
            "prefect.name": work_pool.name,
        },
    ]
