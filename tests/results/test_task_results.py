import pytest

from prefect.filesystems import LocalFileSystem
from prefect.flows import flow
from prefect.serializers import JSONSerializer, PickleSerializer
from prefect.settings import PREFECT_HOME
from prefect.tasks import task
from prefect.testing.utilities import (
    assert_uses_result_serializer,
    assert_uses_result_storage,
)


@pytest.mark.parametrize("options", [{"retries": 3}])
async def test_task_persisted_result_due_to_flow_feature(orion_client, options):
    @flow(**options)
    def foo():
        return bar(return_state=True)

    @task
    def bar():
        return 1

    flow_state = foo(return_state=True)
    task_state = await flow_state.result()
    assert await task_state.result() == 1

    api_state = (
        await orion_client.read_task_run(task_state.state_details.task_run_id)
    ).state
    assert await api_state.result() == 1


@pytest.mark.parametrize("options", [{"cache_key_fn": lambda *_: "foo"}])
async def test_task_persisted_result_due_to_task_feature(orion_client, options):
    @flow()
    def foo():
        return bar(return_state=True)

    @task(**options)
    def bar():
        return 1

    flow_state = foo(return_state=True)
    task_state = await flow_state.result()
    assert await task_state.result() == 1

    api_state = (
        await orion_client.read_task_run(task_state.state_details.task_run_id)
    ).state
    assert await api_state.result() == 1


async def test_task_persisted_result_due_to_opt_in(orion_client):
    @flow
    def foo():
        return bar(return_state=True)

    @task(persist_result=True)
    def bar():
        return 1

    flow_state = foo(return_state=True)
    task_state = await flow_state.result()
    assert await task_state.result() == 1

    api_state = (
        await orion_client.read_task_run(task_state.state_details.task_run_id)
    ).state
    assert await api_state.result() == 1


@pytest.mark.parametrize(
    "serializer",
    ["json", "pickle", JSONSerializer(), PickleSerializer()],
)
@pytest.mark.parametrize("source", ["child", "parent"])
async def test_task_result_serializer(orion_client, source, serializer):
    @flow(result_serializer=serializer if source == "parent" else None)
    def foo():
        return bar(return_state=True)

    @task(
        result_serializer=serializer if source == "child" else None,
        persist_result=True,
    )
    def bar():
        return 1

    flow_state = foo(return_state=True)
    task_state = await flow_state.result()
    assert await task_state.result() == 1
    await assert_uses_result_serializer(task_state, serializer)

    api_state = (
        await orion_client.read_task_run(task_state.state_details.task_run_id)
    ).state
    assert await api_state.result() == 1
    await assert_uses_result_serializer(api_state, serializer)


@pytest.mark.parametrize("source", ["child", "parent"])
async def test_task_result_storage(orion_client, source):
    storage = LocalFileSystem(basepath=PREFECT_HOME.value() / "test-storage")

    @flow(result_storage=storage if source == "parent" else None)
    def foo():
        return bar(return_state=True)

    @task(result_storage=storage if source == "child" else None, persist_result=True)
    def bar():
        return 1

    flow_state = foo(return_state=True)
    task_state = await flow_state.result()
    assert await task_state.result() == 1
    await assert_uses_result_storage(task_state, storage)

    api_state = (
        await orion_client.read_task_run(task_state.state_details.task_run_id)
    ).state
    assert await api_state.result() == 1
    await assert_uses_result_storage(api_state, storage)
