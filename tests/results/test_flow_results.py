import pytest

from prefect.exceptions import MissingResult
from prefect.filesystems import LocalFileSystem
from prefect.flows import flow
from prefect.results import LiteralResult
from prefect.serializers import JSONSerializer, PickleSerializer, Serializer
from prefect.settings import PREFECT_HOME
from prefect.testing.utilities import (
    assert_uses_result_serializer,
    assert_uses_result_storage,
)


class MyIntSerializer(Serializer):
    """
    Custom serializer for test coverage of user-defined serializers
    """

    type = "int-custom"

    def dumps(self, obj: int):
        return obj.to_bytes(8, byteorder="little")

    def loads(self, blob):
        return int.from_bytes(blob, byteorder="little")


@pytest.mark.parametrize("persist_result", [False, None])
async def test_flow_with_unpersisted_result(orion_client, persist_result):
    @flow(persist_result=persist_result)
    def foo():
        return 1

    state = foo(return_state=True)
    assert await state.result() == 1

    api_state = (
        await orion_client.read_flow_run(state.state_details.flow_run_id)
    ).state
    with pytest.raises(MissingResult):
        await api_state.result()


async def test_flow_result_not_missing_with_null_return(orion_client):
    @flow
    def foo():
        return None

    state = foo(return_state=True)
    assert await state.result() is None

    api_state = (
        await orion_client.read_flow_run(state.state_details.flow_run_id)
    ).state
    assert await api_state.result() is None


@pytest.mark.parametrize("value", [True, False, None])
async def test_flow_literal_result_is_available_but_not_serialized_or_persisted(
    orion_client, value
):
    @flow(
        persist_result=True,
        result_serializer="pickle",
        result_storage=LocalFileSystem(basepath=PREFECT_HOME.value()),
    )
    def foo():
        return value

    state = foo(return_state=True)
    assert await state.result() is value

    api_state = (
        await orion_client.read_flow_run(state.state_details.flow_run_id)
    ).state
    assert await api_state.result() is value


async def test_flow_exception_is_persisted(orion_client):
    @flow(persist_result=True)
    def foo():
        raise ValueError("Hello world")

    state = foo(return_state=True)
    with pytest.raises(ValueError, match="Hello world"):
        await state.result()

    api_state = (
        await orion_client.read_flow_run(state.state_details.flow_run_id)
    ).state
    with pytest.raises(ValueError, match="Hello world"):
        await api_state.result()


@pytest.mark.parametrize(
    "serializer",
    ["json", "pickle", JSONSerializer(), PickleSerializer(), MyIntSerializer()],
)
async def test_flow_result_serializer(serializer, orion_client):
    @flow(result_serializer=serializer, persist_result=True)
    def foo():
        return 1

    state = foo(return_state=True)
    assert await state.result() == 1
    await assert_uses_result_serializer(state, serializer)

    api_state = (
        await orion_client.read_flow_run(state.state_details.flow_run_id)
    ).state
    assert await api_state.result() == 1
    await assert_uses_result_serializer(api_state, serializer)


async def test_flow_result_storage_by_instance(orion_client):
    storage = LocalFileSystem(basepath=PREFECT_HOME.value() / "test-storage")

    @flow(result_storage=storage, persist_result=True)
    def foo():
        return 1

    state = foo(return_state=True)
    assert await state.result() == 1
    await assert_uses_result_storage(state, storage)

    api_state = (
        await orion_client.read_flow_run(state.state_details.flow_run_id)
    ).state
    assert await api_state.result() == 1
    await assert_uses_result_storage(api_state, storage)


async def test_flow_result_storage_by_slug(orion_client):
    await LocalFileSystem(basepath=PREFECT_HOME.value() / "test-storage").save("test")
    slug = LocalFileSystem.get_block_type_slug() + "/test"

    @flow(result_storage=slug, persist_result=True)
    def foo():
        return 1

    state = foo(return_state=True)
    assert await state.result() == 1
    await assert_uses_result_storage(state, slug, client=orion_client)

    api_state = (
        await orion_client.read_flow_run(state.state_details.flow_run_id)
    ).state
    assert await api_state.result() == 1
    await assert_uses_result_storage(api_state, slug, client=orion_client)


@pytest.mark.parametrize("options", [{"retries": 3}])
async def test_child_flow_persisted_result_due_to_parent_feature(orion_client, options):
    @flow(**options)
    def foo():
        return bar(return_state=True)

    @flow
    def bar():
        return 1

    parent_state = foo(return_state=True)
    child_state = await parent_state.result()
    assert await child_state.result() == 1

    api_state = (
        await orion_client.read_flow_run(child_state.state_details.flow_run_id)
    ).state
    assert await api_state.result() == 1


async def test_child_flow_persisted_result_due_to_opt_in(orion_client):
    @flow
    def foo():
        return bar(return_state=True)

    @flow(persist_result=True)
    def bar():
        return 1

    parent_state = foo(return_state=True)
    child_state = await parent_state.result()
    assert await child_state.result() == 1

    api_state = (
        await orion_client.read_flow_run(child_state.state_details.flow_run_id)
    ).state
    assert await api_state.result() == 1


@pytest.mark.parametrize("source", ["child", "parent"])
async def test_child_flow_result_serializer(orion_client, source):
    serializer = "json"

    @flow(result_serializer=serializer if source == "parent" else None)
    def foo():
        return bar(return_state=True)

    @flow(
        result_serializer=serializer if source == "child" else None,
        persist_result=True,
    )
    def bar():
        return 1

    parent_state = foo(return_state=True)
    child_state = await parent_state.result()
    assert await child_state.result() == 1
    await assert_uses_result_serializer(child_state, serializer)

    api_state = (
        await orion_client.read_flow_run(child_state.state_details.flow_run_id)
    ).state
    assert await api_state.result() == 1
    await assert_uses_result_serializer(api_state, serializer)


@pytest.mark.parametrize("source", ["child", "parent"])
async def test_child_flow_result_storage(orion_client, source):
    storage = LocalFileSystem(basepath=PREFECT_HOME.value() / "test-storage")

    @flow(result_storage=storage if source == "parent" else None)
    def foo():
        return bar(return_state=True)

    @flow(result_storage=storage if source == "child" else None, persist_result=True)
    def bar():
        return 1

    parent_state = foo(return_state=True)
    child_state = await parent_state.result()
    assert await child_state.result() == 1
    await assert_uses_result_storage(child_state, storage)

    api_state = (
        await orion_client.read_flow_run(child_state.state_details.flow_run_id)
    ).state
    assert await api_state.result() == 1
    await assert_uses_result_storage(api_state, storage)


async def test_child_flow_result_not_missing_with_null_return(orion_client):
    @flow
    def foo():
        return bar(return_state=True)

    @flow
    def bar():
        return None

    parent_state = foo(return_state=True)
    child_state = await parent_state.result()
    assert isinstance(child_state.data, LiteralResult)
    assert await child_state.result() is None

    api_state = (
        await orion_client.read_flow_run(child_state.state_details.flow_run_id)
    ).state
    assert await api_state.result() is None


@pytest.mark.parametrize("empty_type", [dict, list])
@pytest.mark.parametrize("persist_result", [True, False])
def test_flow_empty_result_is_retained(persist_result, empty_type):
    @flow(persist_result=persist_result)
    def my_flow():
        return empty_type()

    result = my_flow()
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
def test_flow_resultlike_result_is_retained(persist_result, resultlike):
    """
    Since Pydantic will coerce dictionaries into `BaseResult` types, we need to be sure
    that user dicts that look like a bit like results do not cause problems
    """

    @flow(persist_result=persist_result)
    def my_flow():
        return resultlike

    result = my_flow()
    assert result == resultlike
