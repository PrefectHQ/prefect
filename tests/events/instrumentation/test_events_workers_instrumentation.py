import pendulum
import pytest

from prefect import __version__
from prefect.client.orchestration import PrefectClient
from prefect.events.clients import AssertingEventsClient
from prefect.events.worker import EventsWorker
from prefect.states import Cancelling, Scheduled
from prefect.testing.cli import invoke_and_assert
from prefect.testing.utilities import AsyncMock
from prefect.workers.base import BaseJobConfiguration, BaseWorker, BaseWorkerResult


class WorkerEventsTestImpl(BaseWorker):
    type = "events-test"
    job_configuration = BaseJobConfiguration

    async def run(self):
        pass

    async def kill_infrastructure(
        self,
        infrastructure_pid: str,
        configuration: BaseJobConfiguration,
        grace_seconds: int = 30,
    ):
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

    await asserting_events_worker.drain()

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


async def test_worker_emits_executed_event(
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

    await asserting_events_worker.drain()

    assert isinstance(asserting_events_worker._client, AssertingEventsClient)

    # When a worker submits a flow-run it also monitors that flow run until
    # it's complete. When it's submits it fires a 'sumbitted' event,
    # which is covered by the test_worker_emits_submitted_event above.
    assert len(asserting_events_worker._client.events) == 2

    submitted_event = asserting_events_worker._client.events[0]
    executed_event = asserting_events_worker._client.events[1]

    assert executed_event.event == "prefect.worker.executed-flow-run"

    assert dict(executed_event.resource.items()) == {
        "prefect.resource.id": f"prefect.worker.events-test.{worker.get_name_slug()}",
        "prefect.resource.name": worker.name,
        "prefect.version": str(__version__),
        "prefect.worker-type": worker.type,
    }

    assert len(executed_event.related) == 6

    related = [dict(r.items()) for r in executed_event.related]

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

    assert executed_event.follows == submitted_event.id


@pytest.mark.usefixtures("use_hosted_api_server")
def test_lifecycle_events(
    asserting_events_worker: EventsWorker, reset_worker_events, work_pool
):
    invoke_and_assert(
        command=[
            "worker",
            "start",
            "--run-once",
            "-p",
            work_pool.name,
            "-n",
            "test-worker",
            "-t",
            "process",
        ],
        expected_code=0,
    )

    asserting_events_worker.drain()

    assert isinstance(asserting_events_worker._client, AssertingEventsClient)

    assert len(asserting_events_worker._client.events) == 2

    started_event = asserting_events_worker._client.events[0]

    assert started_event.event == "prefect.worker.started"

    assert dict(started_event.resource.items()) == {
        "prefect.resource.id": "prefect.worker.process.test-worker",
        "prefect.resource.name": "test-worker",
        "prefect.version": str(__version__),
        "prefect.worker-type": "process",
    }

    assert len(started_event.related) == 1

    related = [dict(r.items()) for r in started_event.related]

    assert related == [
        {
            "prefect.resource.id": f"prefect.work-pool.{work_pool.id}",
            "prefect.resource.role": "work-pool",
            "prefect.resource.name": work_pool.name,
        },
    ]

    stopped_event = asserting_events_worker._client.events[1]

    assert stopped_event.event == "prefect.worker.stopped"

    assert dict(stopped_event.resource.items()) == {
        "prefect.resource.id": "prefect.worker.process.test-worker",
        "prefect.resource.name": "test-worker",
        "prefect.version": str(__version__),
        "prefect.worker-type": "process",
    }

    assert len(stopped_event.related) == 1

    related = [dict(r.items()) for r in stopped_event.related]

    assert related == [
        {
            "prefect.resource.id": f"prefect.work-pool.{work_pool.id}",
            "prefect.resource.role": "work-pool",
            "prefect.resource.name": work_pool.name,
        },
    ]


async def test_worker_emits_cancelled_event(
    asserting_events_worker: EventsWorker,
    reset_worker_events,
    orion_client: PrefectClient,
    worker_deployment_wq1,
    work_pool,
):
    flow_run = await orion_client.create_flow_run_from_deployment(
        worker_deployment_wq1.id,
        state=Cancelling(),
        tags=["flow-run-one"],
    )
    await orion_client.update_flow_run(flow_run.id, infrastructure_pid="process123")
    flow = await orion_client.read_flow(flow_run.flow_id)

    async with WorkerEventsTestImpl(work_pool_name=work_pool.name) as worker:
        await worker.sync_with_backend()
        await worker.check_for_cancelled_flow_runs()

    await asserting_events_worker.drain()

    assert isinstance(asserting_events_worker._client, AssertingEventsClient)

    assert len(asserting_events_worker._client.events) == 1
    cancelled_event = asserting_events_worker._client.events[0]

    assert cancelled_event.event == "prefect.worker.cancelled-flow-run"

    assert dict(cancelled_event.resource.items()) == {
        "prefect.resource.id": f"prefect.worker.events-test.{worker.get_name_slug()}",
        "prefect.resource.name": worker.name,
        "prefect.version": str(__version__),
        "prefect.worker-type": worker.type,
    }

    related = [dict(r.items()) for r in cancelled_event.related]

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


def test_job_configuration_related_resources_no_objects():
    config = BaseJobConfiguration()
    config._related_objects = {
        "deployment": None,
        "flow": None,
        "flow-run": None,
    }
    assert config._related_resources() == []
