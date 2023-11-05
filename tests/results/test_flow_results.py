import base64
import pickle

import pytest

from prefect import flow, task
from prefect.context import get_run_context
from prefect.exceptions import MissingResult
from prefect.filesystems import LocalFileSystem
from prefect.results import PersistedResultBlob, UnpersistedResult
from prefect.serializers import (
    CompressedSerializer,
    JSONSerializer,
    PickleSerializer,
    Serializer,
)
from prefect.server import schemas
from prefect.settings import (
    PREFECT_DEFAULT_RESULT_STORAGE_BLOCK,
    PREFECT_HOME,
    PREFECT_RESULTS_PERSIST_BY_DEFAULT,
    temporary_settings,
)
from prefect.states import Cancelled, Completed, Failed
from prefect.testing.utilities import (
    assert_blocks_equal,
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
async def test_flow_with_unpersisted_result(prefect_client, persist_result):
    @flow(persist_result=persist_result)
    def foo():
        return 1

    state = foo(return_state=True)
    assert await state.result() == 1

    api_state = (
        await prefect_client.read_flow_run(state.state_details.flow_run_id)
    ).state
    with pytest.raises(MissingResult):
        await api_state.result()


async def test_flow_with_uncached_and_unpersisted_result(prefect_client):
    @flow(persist_result=False, cache_result_in_memory=False)
    def foo():
        return 1

    state = foo(return_state=True)
    with pytest.raises(MissingResult):
        await state.result()

    api_state = (
        await prefect_client.read_flow_run(state.state_details.flow_run_id)
    ).state
    with pytest.raises(MissingResult):
        await api_state.result()


async def test_flow_with_uncached_and_unpersisted_null_result(prefect_client):
    @flow(persist_result=False, cache_result_in_memory=False)
    def foo():
        return None

    state = foo(return_state=True)
    # Nulls do not consume memory and are still available
    assert await state.result() is None

    api_state = (
        await prefect_client.read_flow_run(state.state_details.flow_run_id)
    ).state
    with pytest.raises(MissingResult):
        await api_state.result()


async def test_flow_with_uncached_but_persisted_result(prefect_client):
    @flow(persist_result=True, cache_result_in_memory=False)
    def foo():
        return 1

    state = foo(return_state=True)
    assert not state.data.has_cached_object()
    assert await state.result() == 1

    api_state = (
        await prefect_client.read_flow_run(state.state_details.flow_run_id)
    ).state
    assert await api_state.result() == 1


async def test_flow_with_uncached_but_literal_result(prefect_client):
    @flow(persist_result=True, cache_result_in_memory=False)
    def foo():
        return True

    state = foo(return_state=True)
    # Literal results are always cached
    assert state.data.has_cached_object()
    assert await state.result() is True

    api_state = (
        await prefect_client.read_flow_run(state.state_details.flow_run_id)
    ).state
    assert await api_state.result() is True


async def test_flow_result_missing_with_null_return(prefect_client):
    @flow
    def foo():
        return None

    state = foo(return_state=True)
    assert await state.result() is None

    api_state = (
        await prefect_client.read_flow_run(state.state_details.flow_run_id)
    ).state
    with pytest.raises(MissingResult):
        await api_state.result()


@pytest.mark.parametrize("value", [True, False, None])
async def test_flow_literal_result_is_available_but_not_serialized_or_persisted(
    prefect_client, value
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
        await prefect_client.read_flow_run(state.state_details.flow_run_id)
    ).state
    assert await api_state.result() is value


async def test_flow_exception_is_persisted(prefect_client):
    @flow(persist_result=True)
    def foo():
        raise ValueError("Hello world")

    state = foo(return_state=True)
    with pytest.raises(ValueError, match="Hello world"):
        await state.result()

    api_state = (
        await prefect_client.read_flow_run(state.state_details.flow_run_id)
    ).state
    with pytest.raises(ValueError, match="Hello world"):
        await api_state.result()


@pytest.mark.parametrize(
    "serializer",
    [
        "json",
        "pickle",
        JSONSerializer(),
        PickleSerializer(),
        MyIntSerializer(),
        "int-custom",
        "compressed/pickle",
        "compressed/json",
        CompressedSerializer(serializer=MyIntSerializer()),
    ],
)
async def test_flow_result_serializer(serializer, prefect_client):
    @flow(result_serializer=serializer, persist_result=True)
    def foo():
        return 1

    state = foo(return_state=True)
    assert await state.result() == 1
    await assert_uses_result_serializer(state, serializer)

    api_state = (
        await prefect_client.read_flow_run(state.state_details.flow_run_id)
    ).state
    assert await api_state.result() == 1
    await assert_uses_result_serializer(api_state, serializer)


async def test_flow_result_storage_by_instance(prefect_client):
    storage = LocalFileSystem(basepath=PREFECT_HOME.value() / "test-storage")

    @flow(result_storage=storage, persist_result=True)
    def foo():
        return 1

    state = foo(return_state=True)
    assert await state.result() == 1
    await assert_uses_result_storage(state, storage)

    api_state = (
        await prefect_client.read_flow_run(state.state_details.flow_run_id)
    ).state
    assert await api_state.result() == 1
    await assert_uses_result_storage(api_state, storage)


async def test_flow_result_storage_by_slug(prefect_client):
    await LocalFileSystem(basepath=PREFECT_HOME.value() / "test-storage").save("test")
    slug = LocalFileSystem.get_block_type_slug() + "/test"

    @flow(result_storage=slug, persist_result=True)
    def foo():
        return 1

    state = foo(return_state=True)
    assert await state.result() == 1
    await assert_uses_result_storage(state, slug, client=prefect_client)

    api_state = (
        await prefect_client.read_flow_run(state.state_details.flow_run_id)
    ).state
    assert await api_state.result() == 1
    await assert_uses_result_storage(api_state, slug, client=prefect_client)


@pytest.mark.parametrize("options", [{"retries": 3}])
async def test_child_flow_persisted_result_due_to_parent_feature(
    prefect_client, options
):
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
        await prefect_client.read_flow_run(child_state.state_details.flow_run_id)
    ).state
    assert await api_state.result() == 1


async def test_child_flow_persisted_result_due_to_opt_in(prefect_client):
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
        await prefect_client.read_flow_run(child_state.state_details.flow_run_id)
    ).state
    assert await api_state.result() == 1


@pytest.mark.parametrize("source", ["child", "parent"])
async def test_child_flow_result_serializer(prefect_client, source):
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
        await prefect_client.read_flow_run(child_state.state_details.flow_run_id)
    ).state
    assert await api_state.result() == 1
    await assert_uses_result_serializer(api_state, serializer)


@pytest.mark.parametrize("source", ["child", "parent"])
async def test_child_flow_result_storage(prefect_client, source):
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
        await prefect_client.read_flow_run(child_state.state_details.flow_run_id)
    ).state
    assert await api_state.result() == 1
    await assert_uses_result_storage(api_state, storage)


async def test_child_flow_result_missing_with_null_return(prefect_client):
    @flow
    def foo():
        return bar(return_state=True)

    @flow
    def bar():
        return None

    parent_state = foo(return_state=True)
    child_state = await parent_state.result()
    assert isinstance(child_state.data, UnpersistedResult)
    assert await child_state.result() is None

    api_state = (
        await prefect_client.read_flow_run(child_state.state_details.flow_run_id)
    ).state
    with pytest.raises(MissingResult):
        await api_state.result()


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
        {"type": "persisted", "value": "test"},
        {"type": "unpersisted"},
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


@pytest.mark.parametrize(
    "return_state",
    [
        Completed(data="test"),
        Completed(message="Hello!"),
        Cancelled(),
        Failed(),
    ],
)
@pytest.mark.parametrize("persist_result", [True, False])
def test_flow_state_result_is_respected(persist_result, return_state):
    @flow(persist_result=persist_result)
    def my_flow():
        return return_state

    state = my_flow(return_state=True)
    assert state.type == return_state.type

    # id, timestamp, and state details must be excluded as they are copied from
    # the API version of the state and will not match the state created for
    # this test. Data must be excluded as it will have been updated to a
    # result.
    assert state.dict(
        exclude={"id", "timestamp", "state_details", "data"}
    ) == return_state.dict(exclude={"id", "timestamp", "state_details", "data"})

    if return_state.data:
        assert state.result(raise_on_failure=False) == return_state.data


@pytest.mark.parametrize(
    "return_state",
    [
        schemas.states.Completed(data="test"),
        schemas.states.Cancelled(),
        schemas.states.Failed(),
    ],
)
@pytest.mark.parametrize("persist_result", [True, False])
def test_flow_server_state_schema_result_is_respected(persist_result, return_state):
    # Tests for backwards compatibility with server-side state return values
    @flow(persist_result=persist_result)
    def my_flow():
        return return_state

    with pytest.warns(DeprecationWarning, match="Use `prefect.states.State` instead"):
        state = my_flow(return_state=True)

    assert state.type == return_state.type

    # id, timestamp, and state details must be excluded as they are copied from
    # the API version of the state and will not match the state created for
    # this test. Data must be excluded as it will have been updated to a
    # result.
    assert state.dict(
        exclude={"id", "timestamp", "state_details", "data"}
    ) == return_state.dict(exclude={"id", "timestamp", "state_details", "data"})

    if return_state.data:
        with pytest.warns(DeprecationWarning, match="use `prefect.states.State`"):
            assert state.result(raise_on_failure=False) == return_state.data


async def test_root_flow_default_remote_storage():
    @flow
    async def foo():
        result_fac = get_run_context().result_factory
        return result_fac.storage_block

    block = LocalFileSystem()
    await block.save("my-result-storage")

    with temporary_settings(
        {
            PREFECT_RESULTS_PERSIST_BY_DEFAULT: True,
            PREFECT_DEFAULT_RESULT_STORAGE_BLOCK: "local-file-system/my-result-storage",
        }
    ):
        storage_block = await foo()

    assert_blocks_equal(storage_block, block)
    assert storage_block._is_anonymous is False


async def test_root_flow_default_remote_storage_saves_correct_result():
    await LocalFileSystem(basepath="~/.prefect/results").save("my-result-storage")

    @task(result_storage_key="my-result.pkl")
    async def bar():
        return {"foo": "bar"}

    @flow
    async def foo():
        return await bar()

    with temporary_settings(
        {
            PREFECT_RESULTS_PERSIST_BY_DEFAULT: True,
            PREFECT_DEFAULT_RESULT_STORAGE_BLOCK: "local-file-system/my-result-storage",
        }
    ):
        result = await foo()

    assert result == {"foo": "bar"}
    local_storage = await LocalFileSystem.load("my-result-storage")
    result_bytes = await local_storage.read_path("~/.prefect/results/my-result.pkl")
    saved_python_result = pickle.loads(
        base64.b64decode(PersistedResultBlob.parse_raw(result_bytes).data)
    )

    assert saved_python_result == {"foo": "bar"}


async def test_root_flow_nonexistent_default_storage_block_fails():
    @flow
    async def foo():
        result_fac = get_run_context().result_factory
        return result_fac.storage_block

    with temporary_settings(
        {
            PREFECT_RESULTS_PERSIST_BY_DEFAULT: True,
            PREFECT_DEFAULT_RESULT_STORAGE_BLOCK: "local-file-system/my-result-storage",
        }
    ):
        with pytest.raises(
            ValueError, match="Unable to find block document named my-result-storage"
        ):
            await foo()


async def test_root_flow_explicit_result_storage_settings_overrides_default():
    await LocalFileSystem(basepath="~/.prefect/results").save("explicit-storage")
    await LocalFileSystem(basepath="~/.prefect/other-results").save(
        "default-result-storage"
    )

    @flow(result_storage=await LocalFileSystem.load("explicit-storage"))
    async def foo():
        return get_run_context().result_factory.storage_block

    with temporary_settings(
        {
            PREFECT_RESULTS_PERSIST_BY_DEFAULT: True,
            PREFECT_DEFAULT_RESULT_STORAGE_BLOCK: (
                "local-file-system/default-result-storage"
            ),
        }
    ):
        result = await foo()

    assert_blocks_equal(result, await LocalFileSystem.load("explicit-storage"))
