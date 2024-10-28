from pathlib import Path

import pytest

from prefect.cache_policies import Inputs
from prefect.filesystems import LocalFileSystem
from prefect.flows import flow
from prefect.results import get_result_store
from prefect.serializers import JSONSerializer, PickleSerializer
from prefect.settings import (
    PREFECT_HOME,
)
from prefect.tasks import task
from prefect.testing.utilities import (
    assert_uses_result_serializer,
    assert_uses_result_storage,
)
from prefect.utilities.annotations import quote


@pytest.mark.parametrize("options", [{"retries": 3}])
async def test_task_persisted_result_due_to_flow_feature(
    prefect_client, options, events_pipeline
):
    @flow(**options)
    def foo():
        return bar(return_state=True)

    @task(persist_result=True)
    def bar():
        return 1

    flow_state = foo(return_state=True)
    task_state = await flow_state.result()
    assert await task_state.result() == 1

    await events_pipeline.process_events()

    api_state = (
        await prefect_client.read_task_run(task_state.state_details.task_run_id)
    ).state
    assert await api_state.result() == 1


@pytest.mark.parametrize("options", [{"cache_key_fn": lambda *_: "xyz"}])
async def test_task_persisted_result_due_to_task_feature(
    prefect_client, options, events_pipeline
):
    @flow()
    def foo():
        return bar(return_state=True)

    @task(**options, persist_result=True)
    def bar():
        return 1

    flow_state = foo(return_state=True)
    task_state = await flow_state.result()
    assert await task_state.result() == 1

    await events_pipeline.process_events()

    api_state = (
        await prefect_client.read_task_run(task_state.state_details.task_run_id)
    ).state
    assert await api_state.result() == 1


async def test_task_persisted_result_due_to_opt_in(prefect_client, events_pipeline):
    @flow
    def foo():
        return bar(return_state=True)

    @task(persist_result=True)
    def bar():
        return 1

    flow_state = foo(return_state=True)
    task_state = await flow_state.result()
    assert await task_state.result() == 1

    await events_pipeline.process_events()

    api_state = (
        await prefect_client.read_task_run(task_state.state_details.task_run_id)
    ).state
    assert await api_state.result() == 1


async def test_task_result_is_cached_in_memory_by_default(prefect_client):
    store = None

    @flow
    def foo():
        return bar(return_state=True)

    @task(persist_result=True)
    def bar():
        nonlocal store
        store = get_result_store()
        return 1

    flow_state = foo(return_state=True)
    task_state = await flow_state.result()
    assert task_state.data.metadata.storage_key in store.cache
    assert await task_state.result() == 1


async def test_task_with_uncached_but_persisted_result(prefect_client, events_pipeline):
    store = None

    @flow
    def foo():
        return bar(return_state=True)

    @task(persist_result=True, cache_result_in_memory=False)
    def bar():
        nonlocal store
        store = get_result_store()
        return 1

    flow_state = foo(return_state=True)
    task_state = await flow_state.result()
    assert task_state.data.metadata.storage_key not in store.cache
    assert await task_state.result() == 1

    await events_pipeline.process_events()

    api_state = (
        await prefect_client.read_task_run(task_state.state_details.task_run_id)
    ).state
    assert await api_state.result() == 1


async def test_task_with_uncached_but_persisted_result_not_cached_during_flow(
    prefect_client, events_pipeline
):
    store = None

    @flow
    def foo():
        state = bar(return_state=True)
        nonlocal store
        store = get_result_store()
        assert state.data.metadata.storage_key not in store.cache
        assert state.result() == 1
        assert state.data.metadata.storage_key not in store.cache
        assert state.result() == 1
        return state

    @task(persist_result=True, cache_result_in_memory=False)
    def bar():
        return 1

    flow_state = foo(return_state=True)
    task_state = await flow_state.result()
    assert task_state.data.metadata.storage_key not in store.cache
    assert await task_state.result() == 1

    await events_pipeline.process_events()


@pytest.mark.parametrize(
    "serializer",
    [
        "json",
        "pickle",
        JSONSerializer(),
        PickleSerializer(),
        "compressed/pickle",
        "compressed/json",
    ],
)
@pytest.mark.parametrize("source", ["child", "parent"])
async def test_task_result_serializer(
    prefect_client, events_pipeline, source, serializer, tmp_path: Path
):
    storage = LocalFileSystem(basepath=tmp_path)
    await storage.save("tmp-test")

    @flow(
        result_serializer=serializer if source == "parent" else None,
        result_storage=storage,
    )
    def foo():
        return bar(return_state=True)

    @task(
        result_serializer=serializer if source == "child" else None,
        result_storage=storage,
        persist_result=True,
    )
    def bar():
        return 1

    flow_state = foo(return_state=True)
    task_state = await flow_state.result()
    assert await task_state.result() == 1
    await assert_uses_result_serializer(task_state, serializer, prefect_client)

    await events_pipeline.process_events()

    api_state = (
        await prefect_client.read_task_run(task_state.state_details.task_run_id)
    ).state
    assert await api_state.result() == 1
    await assert_uses_result_serializer(api_state, serializer, prefect_client)


@pytest.mark.parametrize("source", ["child", "parent"])
async def test_task_result_storage(prefect_client, source, events_pipeline):
    storage = LocalFileSystem(basepath=PREFECT_HOME.value() / "test-storage")
    await storage.save("tmp-test-storage")

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

    await events_pipeline.process_events()

    api_state = (
        await prefect_client.read_task_run(task_state.state_details.task_run_id)
    ).state
    assert await api_state.result() == 1
    await assert_uses_result_storage(api_state, storage)


async def test_task_result_static_storage_key(
    prefect_client, tmp_path, events_pipeline
):
    storage = LocalFileSystem(basepath=tmp_path / "test-storage")
    await storage.save("tmp-test-storage")

    @flow
    def foo():
        return bar(return_state=True)

    @task(result_storage=storage, persist_result=True, result_storage_key="test")
    def bar():
        return 1

    flow_state = foo(return_state=True)
    task_state = await flow_state.result()
    assert await task_state.result() == 1
    assert task_state.data.metadata.storage_key == "test"

    await events_pipeline.process_events()

    api_state = (
        await prefect_client.read_task_run(task_state.state_details.task_run_id)
    ).state
    assert await api_state.result() == 1
    assert task_state.data.metadata.storage_key == "test"


async def test_task_result_parameter_formatted_storage_key(
    prefect_client, tmp_path, events_pipeline
):
    storage = LocalFileSystem(basepath=tmp_path / "test-storage")
    await storage.save("tmp-test-storage-again")

    @flow
    def foo():
        return bar(y="foo", return_state=True)

    @task(
        result_storage=storage,
        persist_result=True,
        result_storage_key="{parameters[x]}-{parameters[y]}-bar",
    )
    def bar(x: int = 1, y: str = "test"):
        return 1

    flow_state = foo(return_state=True)
    task_state = await flow_state.result()
    assert await task_state.result() == 1
    assert task_state.data.metadata.storage_key == "1-foo-bar"

    await events_pipeline.process_events()

    api_state = (
        await prefect_client.read_task_run(task_state.state_details.task_run_id)
    ).state
    assert await api_state.result() == 1
    assert task_state.data.metadata.storage_key == "1-foo-bar"


async def test_task_result_flow_run_formatted_storage_key(
    prefect_client, tmp_path, events_pipeline
):
    storage = LocalFileSystem(basepath=tmp_path / "test-storage")
    await storage.save("tmp-test-storage-again")

    @flow
    def foo():
        return bar(y="foo", return_state=True)

    @task(
        result_storage=storage,
        persist_result=True,
        result_storage_key="{flow_run.flow_name}__bar",
    )
    def bar(x: int = 1, y: str = "test"):
        return 1

    flow_state = foo(return_state=True)
    task_state = await flow_state.result()
    assert await task_state.result() == 1
    assert task_state.data.metadata.storage_key == "foo__bar"

    await events_pipeline.process_events()

    api_state = (
        await prefect_client.read_task_run(task_state.state_details.task_run_id)
    ).state
    assert await api_state.result() == 1
    assert task_state.data.metadata.storage_key == "foo__bar"


async def test_task_result_with_null_return(prefect_client, events_pipeline):
    @flow
    def foo():
        return bar(return_state=True)

    @task(persist_result=True)
    def bar():
        return None

    flow_state = foo(return_state=True)
    task_state = await flow_state.result()
    assert await task_state.result() is None

    await events_pipeline.process_events()

    api_state = (
        await prefect_client.read_task_run(task_state.state_details.task_run_id)
    ).state
    assert await api_state.result() is None


@pytest.mark.parametrize("value", [True, False, None])
async def test_task_literal_result_is_handled_the_same(
    prefect_client, value, events_pipeline
):
    @flow
    def foo():
        return bar(return_state=True)

    @task(
        persist_result=True,
        result_serializer="pickle",
    )
    def bar():
        return value

    flow_state = foo(return_state=True)
    task_state = await flow_state.result()
    assert await task_state.result() is value

    await events_pipeline.process_events()

    api_state = (
        await prefect_client.read_task_run(task_state.state_details.task_run_id)
    ).state
    assert await api_state.result() is value


async def test_task_exception_is_persisted(prefect_client, events_pipeline):
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

    await events_pipeline.process_events()

    api_state = (
        await prefect_client.read_task_run(task_state.state_details.task_run_id)
    ).state
    with pytest.raises(ValueError, match="Hello world"):
        await api_state.result()


async def test_result_store_correctly_receives_metadata_storage(tmp_path):
    @task(persist_result=True, cache_policy=Inputs().configure(key_storage=tmp_path))
    def bar():
        return get_result_store()

    result_store = bar()
    assert result_store.metadata_storage == LocalFileSystem(basepath=tmp_path)
    assert result_store.result_storage != result_store.metadata_storage


@pytest.mark.parametrize("empty_type", [dict, list])
@pytest.mark.parametrize("persist_result", [True, False])
def test_task_empty_result_is_retained(persist_result, empty_type):
    @task(persist_result=persist_result)
    def my_task():
        return empty_type()

    @flow
    def my_flow():
        return quote(my_task())

    result = my_flow().unquote()
    assert result == empty_type()


@pytest.mark.parametrize(
    "resultlike",
    [
        {"type": "foo"},
        {"type": "literal", "user-stuff": "bar"},
        {"type": "persisted"},
    ],
)
@pytest.mark.parametrize("persist_result", [True, False])
def test_task_resultlike_result_is_retained(persist_result, resultlike):
    """
    Since Pydantic will coerce dictionaries into `BaseResult` types, we need to be sure
    that user dicts that look like a bit like results do not cause problems
    """

    @task(persist_result=persist_result)
    def my_task():
        return resultlike

    @flow
    def my_flow():
        return quote(my_task())

    result = my_flow().unquote()
    assert result == resultlike
