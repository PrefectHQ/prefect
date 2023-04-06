from unittest import mock

from prefect import flow, tags, task
from prefect.context import FlowRunContext, TaskRunContext
from prefect.events.related import related_resources_from_run_context
from prefect.events.schemas import RelatedResource


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


async def test_caches_related_objects():
    @flow
    async def test_flow():
        flow_run_context = FlowRunContext.get()
        assert flow_run_context is not None
        with mock.patch.object(
            flow_run_context.client,
            "read_flow",
            wraps=flow_run_context.client.read_flow,
        ) as read_flow_mock:
            await related_resources_from_run_context()
            await related_resources_from_run_context()

        return read_flow_mock

    read_flow_mock = await test_flow()

    read_flow_mock.assert_called_once()


async def test_caches_from_task_run_context():
    @task
    async def test_task():
        FlowRunContext.__var__.set(None)
        task_run_context = TaskRunContext.get()
        assert task_run_context is not None
        with mock.patch.object(
            task_run_context.client,
            "read_flow_run",
            wraps=task_run_context.client.read_flow_run,
        ) as read_flow_run_mock:
            with mock.patch.object(
                task_run_context.client,
                "read_flow",
                wraps=task_run_context.client.read_flow,
            ) as read_flow_mock:
                await related_resources_from_run_context()
                await related_resources_from_run_context()

        return read_flow_run_mock, read_flow_mock

    @flow
    async def test_flow():
        return await test_task()

    state = await test_flow._run()
    read_flow_run_mock, read_flow_mock = await state.result()

    read_flow_run_mock.assert_called_once()
    read_flow_mock.assert_called_once()
