from unittest import mock

import pytest

from prefect import __version__
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import VersionInfo
from prefect.events.clients import AssertingEventsClient
from prefect.events.worker import EventsWorker
from prefect.server.database import orm_models
from prefect.states import Scheduled
from prefect.testing.cli import invoke_and_assert
from prefect.testing.utilities import AsyncMock
from prefect.types._datetime import now
from prefect.workers.base import BaseJobConfiguration, BaseWorker, BaseWorkerResult


class WorkerEventsTestImpl(BaseWorker):
    type = "events-test"
    job_configuration = BaseJobConfiguration

    async def run(self):
        pass


async def test_worker_emits_submitted_event(
    asserting_events_worker: EventsWorker,
    reset_worker_events,
    prefect_client: PrefectClient,
    worker_deployment_wq1,
    work_pool,
):
    flow_run = await prefect_client.create_flow_run_from_deployment(
        worker_deployment_wq1.id,
        state=Scheduled(scheduled_time=now("UTC")),
        tags=["flow-run-one"],
    )

    flow = await prefect_client.read_flow(flow_run.flow_id)

    async with WorkerEventsTestImpl(work_pool_name=work_pool.name) as worker:
        worker._work_pool = work_pool
        worker.run = AsyncMock()
        await worker.get_and_submit_flow_runs()

    await asserting_events_worker.drain()

    assert isinstance(asserting_events_worker._client, AssertingEventsClient)

    # When a worker submits a flow-run, it monitors that flow run until it's complete.
    # When it's complete, it fires a second 'monitored' event, which
    # is covered by the test_worker_emits_monitored_event below.
    assert len(asserting_events_worker._client.events) == 2

    submit_events = list(
        filter(
            lambda e: e.event == "prefect.worker.submitted-flow-run",
            asserting_events_worker._client.events,
        )
    )
    assert len(submit_events) == 1

    assert dict(submit_events[0].resource.items()) == {
        "prefect.resource.id": f"prefect.worker.events-test.{worker.get_name_slug()}",
        "prefect.resource.name": worker.name,
        "prefect.version": str(__version__),
        "prefect.worker-type": worker.type,
    }

    assert len(submit_events[0].related) == 6

    related = [dict(r.items()) for r in submit_events[0].related]

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
    prefect_client: PrefectClient,
    worker_deployment_wq1,
    work_pool,
):
    flow_run = await prefect_client.create_flow_run_from_deployment(
        worker_deployment_wq1.id,
        state=Scheduled(scheduled_time=now("UTC")),
        tags=["flow-run-one"],
    )

    flow = await prefect_client.read_flow(flow_run.flow_id)

    worker_result = BaseWorkerResult(status_code=1, identifier="process123")
    run_flow_fn = AsyncMock(return_value=worker_result)

    async with WorkerEventsTestImpl(work_pool_name=work_pool.name) as worker:
        worker._work_pool = work_pool
        worker.run = run_flow_fn
        await worker.get_and_submit_flow_runs()

    await asserting_events_worker.drain()

    assert isinstance(asserting_events_worker._client, AssertingEventsClient)

    # When a worker submits a flow-run, it monitors that flow run until it's complete.
    # When it's complete, it fires a second 'submitted' event, which
    # is covered by the test_worker_emits_submitted_event below.
    assert len(asserting_events_worker._client.events) == 2

    submitted_events = list(
        filter(
            lambda e: e.event == "prefect.worker.submitted-flow-run",
            asserting_events_worker._client.events,
        )
    )
    assert len(submitted_events) == 1

    executed_events = list(
        filter(
            lambda e: e.event == "prefect.worker.executed-flow-run",
            asserting_events_worker._client.events,
        )
    )
    assert len(executed_events) == 1

    assert executed_events[0].event == "prefect.worker.executed-flow-run"

    assert dict(executed_events[0].resource.items()) == {
        "prefect.resource.id": f"prefect.worker.events-test.{worker.get_name_slug()}",
        "prefect.resource.name": worker.name,
        "prefect.version": str(__version__),
        "prefect.worker-type": worker.type,
    }

    assert len(executed_events[0].related) == 6

    related = [dict(r.items()) for r in executed_events[0].related]

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

    assert executed_events[0].follows == submitted_events[0].id


async def test_worker_event_includes_deployment_version(
    asserting_events_worker: EventsWorker,
    reset_worker_events,
    prefect_client: PrefectClient,
    worker_deployment_wq1: orm_models.Deployment,
    work_pool: orm_models.WorkPool,
):
    await prefect_client.create_flow_run_from_deployment(
        worker_deployment_wq1.id,
        state=Scheduled(scheduled_time=now("UTC")),
        tags=["flow-run-one"],
    )

    worker_result = BaseWorkerResult(status_code=1, identifier="process123")
    run_flow_fn = AsyncMock(return_value=worker_result)

    # mock the client to return a DeploymentResponse with a version_id and version_info,
    # which would be the case if the deployment was created Prefect Cloud experimental
    # deployment versioning support.
    server_deployment = await prefect_client.read_deployment(worker_deployment_wq1.id)
    server_deployment.version_id = "aaaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    server_deployment.version_info = VersionInfo(
        type="githubulous", version="1.2.3.4.5.6"
    )

    with mock.patch(
        "prefect.client.orchestration.PrefectClient.read_deployment",
        return_value=server_deployment,
    ):
        async with WorkerEventsTestImpl(work_pool_name=work_pool.name) as worker:
            worker._work_pool = work_pool
            worker.run = run_flow_fn
            await worker.get_and_submit_flow_runs()

    await asserting_events_worker.drain()

    assert isinstance(asserting_events_worker._client, AssertingEventsClient)

    # When a worker submits a flow-run, it monitors that flow run until it's complete.
    # When it's complete, it fires a second 'submitted' event, which
    # is covered by the test_worker_emits_submitted_event below.
    assert len(asserting_events_worker._client.events) == 2

    events = list(
        filter(
            lambda e: (
                e.event == "prefect.worker.submitted-flow-run"
                or e.event == "prefect.worker.executed-flow-run"
            ),
            asserting_events_worker._client.events,
        )
    )
    # We can just spot-check one of the events here
    event = events[0]

    deployment = event.resource_in_role["deployment"]
    assert (
        deployment["prefect.resource.id"]
        == f"prefect.deployment.{worker_deployment_wq1.id}"
    )
    assert deployment["prefect.resource.role"] == "deployment"
    assert deployment["prefect.resource.name"] == worker_deployment_wq1.name
    assert (
        deployment["prefect.deployment.version-id"]
        == "aaaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    )
    assert deployment["prefect.deployment.version-type"] == "githubulous"
    assert deployment["prefect.deployment.version"] == "1.2.3.4.5.6"


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

    # first event will always be `prefect.worker.started`
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

    # last event should be `prefect.worker.stopped`
    stopped_event = asserting_events_worker._client.events[
        len(asserting_events_worker._client.events) - 1
    ]
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


def test_job_configuration_related_resources_no_objects():
    config = BaseJobConfiguration()
    config._related_objects = {
        "deployment": None,
        "flow": None,
        "flow-run": None,
    }
    assert config._related_resources() == []


async def test_worker_can_include_itself_as_related(work_pool):
    async with WorkerEventsTestImpl(work_pool_name=work_pool.name) as worker:
        await worker.sync_with_backend()

        related = [dict(r) for r in worker._event_related_resources(include_self=True)]

        assert related == [
            {
                "prefect.resource.id": f"prefect.work-pool.{work_pool.id}",
                "prefect.resource.role": "work-pool",
                "prefect.resource.name": work_pool.name,
            },
            {
                "prefect.resource.id": (
                    f"prefect.worker.events-test.{worker.get_name_slug()}"
                ),
                "prefect.resource.role": "worker",
                "prefect.resource.name": worker.name,
                "prefect.version": str(__version__),
                "prefect.worker-type": worker.type,
            },
        ]
