from contextlib import ExitStack
from unittest import mock

import pytest

from prefect import flow, tags, task
from prefect.client.orchestration import get_client
from prefect.context import FlowRunContext, TaskRunContext
from prefect.events.related import related_resources_from_run_context
from prefect.events.schemas import RelatedResource


@pytest.fixture
async def spy_client(test_database_connection_url):
    async with get_client() as client:
        exit_stack = ExitStack()
        exit_stack.enter_context(
            mock.patch.object(client, "read_flow", wraps=client.read_flow),
        )
        exit_stack.enter_context(
            mock.patch.object(client, "read_flow_run", wraps=client.read_flow_run),
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


async def test_gracefully_handles_missing_context():
    related = await related_resources_from_run_context()
    assert related == []


async def test_gets_related_from_run_context(orion_client):
    @flow
    async def test_flow():
        return await related_resources_from_run_context()

    with tags("testing"):
        state = await test_flow._run()

    flow_run = await orion_client.read_flow_run(state.state_details.flow_run_id)
    db_flow = await orion_client.read_flow(flow_run.flow_id)

    related = await state.result()

    assert related == [
        RelatedResource(
            __root__={
                "prefect.resource.id": f"prefect.flow-run.{flow_run.id}",
                "prefect.resource.role": "flow-run",
                "prefect.name": flow_run.name,
            }
        ),
        RelatedResource(
            __root__={
                "prefect.resource.id": f"prefect.flow.{db_flow.id}",
                "prefect.resource.role": "flow",
                "prefect.name": db_flow.name,
            }
        ),
        RelatedResource(
            __root__={
                "prefect.resource.id": f"prefect.tag.testing",
                "prefect.resource.role": "tag",
            }
        ),
    ]


async def test_can_exclude_by_resource_id(orion_client):
    @flow
    async def test_flow():
        flow_run_context = FlowRunContext.get()
        assert flow_run_context is not None
        exclude = {f"prefect.flow-run.{flow_run_context.flow_run.id}"}

        return await related_resources_from_run_context(exclude=exclude)

    state = await test_flow._run()

    flow_run = await orion_client.read_flow_run(state.state_details.flow_run_id)

    related = await state.result()

    assert f"prefect.flow-run.{flow_run.id}" not in related


async def test_gets_flow_run_from_task_run_context(orion_client):
    @task
    async def test_task():
        # Clear the FlowRunContext to simulated a task run in a remote worker.
        FlowRunContext.__var__.set(None)
        return await related_resources_from_run_context()

    @flow
    async def test_flow():
        return await test_task()

    state = await test_flow._run()

    flow_run = await orion_client.read_flow_run(state.state_details.flow_run_id)
    db_flow = await orion_client.read_flow(flow_run.flow_id)

    related = await state.result()

    assert related == [
        RelatedResource(
            __root__={
                "prefect.resource.id": f"prefect.flow-run.{flow_run.id}",
                "prefect.resource.role": "flow-run",
                "prefect.name": flow_run.name,
            }
        ),
        RelatedResource(
            __root__={
                "prefect.resource.id": f"prefect.flow.{db_flow.id}",
                "prefect.resource.role": "flow",
                "prefect.name": db_flow.name,
            }
        ),
    ]


async def test_caches_related_objects(spy_client):
    @flow
    async def test_flow():
        flow_run_context = FlowRunContext.get()
        assert flow_run_context is not None

        with mock.patch("prefect.client.orchestration.get_client", lambda: spy_client):
            await related_resources_from_run_context()
            await related_resources_from_run_context()

    await test_flow()

    spy_client.client.read_flow.assert_called_once()


async def test_caches_from_task_run_context(spy_client):
    @task
    async def test_task():
        FlowRunContext.__var__.set(None)
        task_run_context = TaskRunContext.get()
        assert task_run_context is not None
        with mock.patch("prefect.client.orchestration.get_client", lambda: spy_client):
            await related_resources_from_run_context()
            await related_resources_from_run_context()

    @flow
    async def test_flow():
        return await test_task()

    await test_flow()

    spy_client.client.read_flow_run.assert_called_once()
    spy_client.client.read_flow.assert_called_once()
