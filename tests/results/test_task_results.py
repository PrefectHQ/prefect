import pytest

from prefect.exceptions import MissingResult
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


async def test_task_with_uncached_and_unpersisted_result(orion_client):
    @flow
    def foo():
        return bar(return_state=True)

    @task(persist_result=False, cache_result_in_memory=False)
    def bar():
        return 1

    flow_state = foo(return_state=True)
    task_state = await flow_state.result()
    with pytest.raises(MissingResult):
        await task_state.result()

    api_state = (
        await orion_client.read_task_run(task_state.state_details.task_run_id)
    ).state
    with pytest.raises(MissingResult):
        await api_state.result()


async def test_task_with_uncached_but_persisted_result(orion_client):
    @flow
    def foo():
        return bar(return_state=True)

    @task(persist_result=True, cache_result_in_memory=False)
    def bar():
        return 1

    flow_state = foo(return_state=True)
    task_state = await flow_state.result()
    assert not task_state.data.has_cached_object()
    assert await task_state.result() == 1

    api_state = (
        await orion_client.read_task_run(task_state.state_details.task_run_id)
    ).state
    assert await api_state.result() == 1


async def test_task_with_uncached_but_literal_result(orion_client):
    @flow
    def foo():
        return bar(return_state=True)

    @task(persist_result=True, cache_result_in_memory=False)
    def bar():
        return True

    flow_state = foo(return_state=True)
    task_state = await flow_state.result()
    # Literal results are _always_ cached
    assert task_state.data.has_cached_object()
    assert await task_state.result() is True

    api_state = (
        await orion_client.read_task_run(task_state.state_details.task_run_id)
    ).state
    assert await api_state.result() is True


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
