from contextlib import ExitStack
from unittest import mock

import pytest

from prefect import flow, task
from prefect.client.orchestration import get_client
from prefect.context import FlowRunContext
from prefect.events import RelatedResource
from prefect.events.related import (
    MAX_CACHE_SIZE,
    _get_and_cache_related_object,
    related_resources_from_run_context,
)
from prefect.states import Running


@pytest.fixture
async def spy_client(test_database_connection_url):
    async with get_client() as client:
        exit_stack = ExitStack()

        for method in [
            "read_flow",
            "read_flow_run",
            "read_deployment",
            "read_work_queue",
            "read_work_pool",
        ]:
            exit_stack.enter_context(
                mock.patch.object(client, method, wraps=getattr(client, method)),
            )

        class NoOpClientWrapper:
            def __init__(self, client):
                self.client = client

            async def __aenter__(self):
                return self.client

            async def __aexit__(self, *args):
                pass

        yield NoOpClientWrapper(client)

        exit_stack.close()


async def test_gracefully_handles_missing_context(prefect_client):
    related = await related_resources_from_run_context(prefect_client)
    assert related == []


async def test_gets_related_from_run_context(
    prefect_client, work_queue_1, worker_deployment_wq1
):
    flow_run = await prefect_client.create_flow_run_from_deployment(
        worker_deployment_wq1.id,
        state=Running(),
        tags=["flow-run-one"],
    )

    with FlowRunContext.model_construct(flow_run=flow_run):
        related = await related_resources_from_run_context(prefect_client)

    work_pool = work_queue_1.work_pool
    db_flow = await prefect_client.read_flow(flow_run.flow_id)

    assert related == [
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.flow-run.{flow_run.id}",
                "prefect.resource.role": "flow-run",
                "prefect.resource.name": flow_run.name,
            }
        ),
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.flow.{db_flow.id}",
                "prefect.resource.role": "flow",
                "prefect.resource.name": db_flow.name,
            }
        ),
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.deployment.{worker_deployment_wq1.id}",
                "prefect.resource.role": "deployment",
                "prefect.resource.name": worker_deployment_wq1.name,
            }
        ),
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.work-queue.{work_queue_1.id}",
                "prefect.resource.role": "work-queue",
                "prefect.resource.name": work_queue_1.name,
            }
        ),
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.work-pool.{work_pool.id}",
                "prefect.resource.role": "work-pool",
                "prefect.resource.name": work_pool.name,
            }
        ),
        RelatedResource.model_validate(
            {
                "prefect.resource.id": "prefect.tag.flow-run-one",
                "prefect.resource.role": "tag",
            }
        ),
        RelatedResource.model_validate(
            {
                "prefect.resource.id": "prefect.tag.test",
                "prefect.resource.role": "tag",
            }
        ),
    ]


async def test_can_exclude_by_resource_id(prefect_client):
    @flow
    async def test_flow():
        flow_run_context = FlowRunContext.get()
        assert flow_run_context is not None
        exclude = {f"prefect.flow-run.{flow_run_context.flow_run.id}"}

        return await related_resources_from_run_context(prefect_client, exclude=exclude)

    state = await test_flow(return_state=True)

    flow_run = await prefect_client.read_flow_run(state.state_details.flow_run_id)

    related = await state.result()

    assert f"prefect.flow-run.{flow_run.id}" not in related


async def test_gets_related_from_task_run_context(prefect_client, events_pipeline):
    @task
    async def test_task():
        # Clear the FlowRunContext to simulated a task run in a remote worker.
        token = FlowRunContext.__var__.set(None)
        related_resources = await related_resources_from_run_context(prefect_client)
        FlowRunContext.__var__.reset(token)
        return related_resources

    @flow
    async def test_flow():
        return await test_task(return_state=True)

    state = await test_flow(return_state=True)

    await events_pipeline.process_events()

    task_state = await state.result()

    flow_run = await prefect_client.read_flow_run(state.state_details.flow_run_id)
    db_flow = await prefect_client.read_flow(flow_run.flow_id)

    task_run = await prefect_client.read_task_run(task_state.state_details.task_run_id)

    related = await task_state.result()

    assert related == [
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.flow-run.{flow_run.id}",
                "prefect.resource.role": "flow-run",
                "prefect.resource.name": flow_run.name,
            }
        ),
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.task-run.{task_run.id}",
                "prefect.resource.role": "task-run",
                "prefect.resource.name": task_run.name,
            }
        ),
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.flow.{db_flow.id}",
                "prefect.resource.role": "flow",
                "prefect.resource.name": db_flow.name,
            }
        ),
    ]


async def test_caches_related_objects(spy_client):
    @flow
    async def test_flow():
        flow_run_context = FlowRunContext.get()
        assert flow_run_context is not None

        await related_resources_from_run_context(spy_client.client)
        await related_resources_from_run_context(spy_client.client)

    await test_flow()

    spy_client.client.read_flow.assert_called_once()


async def test_lru_cache_evicts_oldest():
    cache = {}

    async def fetch(obj_id):
        return obj_id

    await _get_and_cache_related_object("flow-run", "flow-run", fetch, "👴", cache)
    assert "flow-run.👴" in cache

    await _get_and_cache_related_object("flow-run", "flow-run", fetch, "👩", cache)
    assert "flow-run.👴" in cache

    for i in range(MAX_CACHE_SIZE):
        await _get_and_cache_related_object(
            "flow-run", "flow-run", fetch, f"👶 {i}", cache
        )

    assert "flow-run.👴" not in cache


async def test_lru_cache_timestamp_updated():
    cache = {}

    async def fetch(obj_id):
        return obj_id

    await _get_and_cache_related_object("flow-run", "flow-run", fetch, "👴", cache)
    _, timestamp = cache["flow-run.👴"]

    await _get_and_cache_related_object("flow-run", "flow-run", fetch, "👴", cache)
    _, next_timestamp = cache["flow-run.👴"]

    assert next_timestamp > timestamp
