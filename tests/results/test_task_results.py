import pytest

from prefect.filesystems import LocalFileSystem
from prefect.flows import flow
from prefect.results import LiteralResult
from prefect.serializers import JSONSerializer, PickleSerializer
from prefect.settings import PREFECT_HOME
from prefect.tasks import task
from prefect.testing.utilities import (
    assert_uses_result_serializer,
    assert_uses_result_storage,
)
from prefect.utilities.annotations import quote


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


async def test_task_result_not_missing_with_null_return(orion_client):
    @flow
    def foo():
        return bar(return_state=True)

    @task
    def bar():
        return None

    flow_state = foo(return_state=True)
    task_state = await flow_state.result()
    assert await task_state.result() is None

    api_state = (
        await orion_client.read_task_run(task_state.state_details.task_run_id)
    ).state
    assert await api_state.result() is None


@pytest.mark.parametrize("value", [True, False, None])
async def test_task_literal_result_is_available_but_not_serialized_or_persisted(
    orion_client, value
):
    @flow
    def foo():
        return bar(return_state=True)

    @task(
        persist_result=True,
        result_serializer="pickle",
        result_storage=LocalFileSystem(basepath=PREFECT_HOME.value()),
    )
    def bar():
        return value

    flow_state = foo(return_state=True)
    task_state = await flow_state.result()
    assert isinstance(task_state.data, LiteralResult)
    assert await task_state.result() is value

    api_state = (
        await orion_client.read_task_run(task_state.state_details.task_run_id)
    ).state
    assert await api_state.result() is value


async def test_task_exception_is_persisted(orion_client):
    @flow
    def foo():
        return quote(bar(return_state=True))

    @task(persist_result=True)
    def bar():
        raise ValueError("Hello world")

    flow_state = foo(return_state=True)
    task_state = (await flow_state.result()).unquote()
    with pytest.raises(ValueError, match="Hello world"):
        await task_state.result()

    api_state = (
        await orion_client.read_task_run(task_state.state_details.task_run_id)
    ).state
    with pytest.raises(ValueError, match="Hello world"):
        await api_state.result()
