import pytest

import prefect.exceptions
import prefect.results
from prefect import flow, task
from prefect.context import FlowRunContext, get_run_context
from prefect.filesystems import LocalFileSystem
from prefect.locking.memory import MemoryLockManager
from prefect.results import (
    ResultRecord,
    ResultStore,
    should_persist_result,
)
from prefect.serializers import JSONSerializer, PickleSerializer
from prefect.settings import (
    PREFECT_LOCAL_STORAGE_PATH,
    PREFECT_RESULTS_DEFAULT_SERIALIZER,
    PREFECT_RESULTS_PERSIST_BY_DEFAULT,
    temporary_settings,
)
from prefect.testing.utilities import assert_blocks_equal
from prefect.transactions import IsolationLevel

DEFAULT_SERIALIZER = PickleSerializer


def DEFAULT_STORAGE():
    return LocalFileSystem(basepath=PREFECT_LOCAL_STORAGE_PATH.value())


@pytest.fixture
def default_persistence_off():
    """
    Many tests return result factories, which aren't serialiable.
    When we switched the default persistence setting to True, this caused tests to fail.
    """
    with temporary_settings({PREFECT_RESULTS_PERSIST_BY_DEFAULT: False}):
        yield


@pytest.fixture
async def store(prefect_client):
    return ResultStore()


async def test_create_result_record(store):
    record = store.create_result_record({"foo": "bar"})
    assert isinstance(record, ResultRecord)
    assert record.metadata.serializer.type == store.serializer.type
    assert record.metadata.storage_block_id == store.result_storage_block_id
    assert record.result == {"foo": "bar"}


def test_root_flow_default_result_store():
    @flow
    def foo():
        return get_run_context().result_store, should_persist_result()

    result_store, persist_result = foo()
    assert persist_result is False
    assert result_store.cache_result_in_memory is True
    assert result_store.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(result_store.result_storage, DEFAULT_STORAGE())
    assert result_store.result_storage_block_id is None


def test_root_flow_default_result_serializer_can_be_overriden_by_setting():
    @flow(persist_result=False)
    def foo():
        return get_run_context().result_store

    with temporary_settings({PREFECT_RESULTS_DEFAULT_SERIALIZER: "json"}):
        result_store = foo()
    assert result_store.serializer == JSONSerializer()


def test_root_flow_default_persist_result_can_be_overriden_by_setting():
    @flow
    def foo():
        return should_persist_result()

    with temporary_settings({PREFECT_RESULTS_PERSIST_BY_DEFAULT: True}):
        persist_result = foo()
    assert persist_result is True


def test_root_flow_can_opt_out_when_persist_result_default_is_overriden_by_setting():
    @flow(persist_result=False)
    def foo():
        return should_persist_result()

    with temporary_settings({PREFECT_RESULTS_PERSIST_BY_DEFAULT: True}):
        persist_result = foo()

    assert persist_result is False


@pytest.mark.parametrize("toggle", [True, False])
def test_root_flow_custom_persist_setting(toggle):
    @flow(persist_result=toggle)
    def foo():
        return get_run_context().result_store, should_persist_result()

    result_store, persist_result = foo()
    assert persist_result is toggle
    assert result_store.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(result_store.result_storage, DEFAULT_STORAGE())


def test_root_flow_persists_results_when_flow_uses_feature():
    @flow(cache_result_in_memory=False, persist_result=True)
    def foo():
        return get_run_context().result_store, should_persist_result()

    result_store, persist_result = foo()
    assert persist_result is True
    assert result_store.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(result_store.result_storage, DEFAULT_STORAGE())


def test_root_flow_can_opt_out_of_persistence_when_flow_uses_feature():
    result_store = None
    persist_result = None

    @flow(cache_result_in_memory=False, persist_result=False)
    def foo():
        nonlocal result_store
        nonlocal persist_result
        persist_result = should_persist_result()
        result_store = get_run_context().result_store

    foo()
    assert persist_result is False
    assert result_store.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(result_store.result_storage, DEFAULT_STORAGE())
    assert result_store.result_storage_block_id is None


@pytest.mark.parametrize("toggle", [True, False])
def test_root_flow_custom_cache_setting(toggle, default_persistence_off):
    result_store = None

    @flow(cache_result_in_memory=toggle)
    def foo():
        nonlocal result_store
        result_store = get_run_context().result_store

    foo()
    assert result_store.cache_result_in_memory is toggle
    assert result_store.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(result_store.result_storage, DEFAULT_STORAGE())


def test_root_flow_custom_serializer_by_type_string():
    @flow(result_serializer="json", persist_result=False)
    def foo():
        return get_run_context().result_store, should_persist_result()

    result_store, persist_result = foo()
    assert persist_result is False
    assert result_store.serializer == JSONSerializer()
    assert_blocks_equal(result_store.result_storage, DEFAULT_STORAGE())
    assert result_store.result_storage_block_id is None


def test_root_flow_custom_serializer_by_instance(default_persistence_off):
    @flow(persist_result=False, result_serializer=JSONSerializer(jsonlib="orjson"))
    def foo():
        return get_run_context().result_store, should_persist_result()

    result_store, persist_result = foo()
    assert persist_result is False
    assert result_store.serializer == JSONSerializer(jsonlib="orjson")
    assert_blocks_equal(result_store.result_storage, DEFAULT_STORAGE())
    assert result_store.result_storage_block_id is None


async def test_root_flow_custom_storage_by_slug(tmp_path, default_persistence_off):
    storage = LocalFileSystem(basepath=tmp_path / "test")
    storage_id = await storage.save("test")

    @flow(result_storage="local-file-system/test")
    def foo():
        return get_run_context().result_store, should_persist_result()

    result_store, persist_result = foo()
    assert persist_result is True  # inferred from the storage
    assert result_store.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(result_store.result_storage, storage)
    assert result_store.result_storage_block_id == storage_id


async def test_root_flow_custom_storage_by_instance_presaved(
    tmp_path, default_persistence_off
):
    storage = LocalFileSystem(basepath=tmp_path / "test")
    storage_id = await storage.save("test")

    @flow(result_storage=storage)
    def foo():
        return get_run_context().result_store, should_persist_result()

    result_store, persist_result = foo()
    assert persist_result is True  # inferred from the storage
    assert result_store.serializer == DEFAULT_SERIALIZER()
    assert result_store.result_storage == storage
    assert result_store.result_storage._is_anonymous is False
    assert result_store.result_storage_block_id == storage_id


def test_child_flow_inherits_default_result_settings(default_persistence_off):
    @flow
    def foo():
        child_store, persist_result = bar()
        return child_store, persist_result

    @flow
    def bar():
        return get_run_context().result_store, should_persist_result()

    child_store, persist_result = foo()
    assert persist_result is False
    assert child_store.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(child_store.result_storage, DEFAULT_STORAGE())
    assert child_store.result_storage_block_id is None


def test_child_flow_default_result_serializer_can_be_overriden_by_setting(
    default_persistence_off,
):
    @flow
    def foo():
        return get_run_context().result_store, bar()

    @flow
    def bar():
        return get_run_context().result_store

    with temporary_settings({PREFECT_RESULTS_DEFAULT_SERIALIZER: "json"}):
        _, child_store = foo()

    assert child_store.serializer == JSONSerializer()


def test_child_flow_default_persist_result_can_be_overriden_by_setting():
    @flow
    def foo():
        return bar()

    @flow
    def bar():
        return get_run_context().result_store, should_persist_result()

    with temporary_settings({PREFECT_RESULTS_PERSIST_BY_DEFAULT: True}):
        child_store, persist_result = foo()

    assert persist_result is True


def test_child_flow_can_opt_out_when_persist_result_default_is_overriden_by_setting():
    @flow
    def foo():
        return bar()

    @flow(persist_result=False)
    def bar():
        return get_run_context().result_store, should_persist_result()

    with temporary_settings({PREFECT_RESULTS_PERSIST_BY_DEFAULT: True}):
        child_store, persist_result = foo()

    assert persist_result is False


def test_child_flow_custom_persist_setting(default_persistence_off):
    @flow
    def foo():
        child_store, persist_result = bar()
        return (
            get_run_context().result_store,
            should_persist_result(),
            child_store,
            persist_result,
        )

    @flow(persist_result=True)
    def bar():
        return get_run_context().result_store, should_persist_result()

    parent_store, parent_persist_result, child_store, child_persist_result = foo()
    assert parent_persist_result is False
    assert child_persist_result is True
    assert child_store.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(child_store.result_storage, DEFAULT_STORAGE())


@pytest.mark.parametrize("toggle", [True, False])
def test_child_flow_custom_cache_setting(toggle, default_persistence_off):
    child_store = None

    @flow
    def foo():
        bar(return_state=True)
        return get_run_context().result_store

    @flow(cache_result_in_memory=toggle)
    def bar():
        nonlocal child_store
        child_store = get_run_context().result_store

    parent_store = foo()
    assert parent_store.cache_result_in_memory is True
    assert child_store.cache_result_in_memory is toggle
    assert child_store.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(child_store.result_storage, DEFAULT_STORAGE())


def test_child_flow_can_opt_out_of_result_persistence_when_parent_uses_feature(
    default_persistence_off,
):
    @flow(retries=3)
    def foo():
        child_store, child_persist_result = bar()
        return (
            get_run_context().result_store,
            should_persist_result(),
            child_persist_result,
            child_store,
        )

    @flow(persist_result=False)
    def bar():
        return get_run_context().result_store, should_persist_result()

    parent_store, parent_persist_result, child_persist_result, child_store = foo()
    assert parent_persist_result is False
    assert child_persist_result is False
    assert child_store.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(child_store.result_storage, DEFAULT_STORAGE())
    assert child_store.result_storage_block_id is None


def test_child_flow_inherits_custom_serializer(default_persistence_off):
    @flow(persist_result=False, result_serializer="json")
    def foo():
        child_store, child_persist_result = bar()
        return get_run_context().result_store, child_persist_result, child_store

    @flow(persist_result=False, result_serializer="json")
    def bar():
        return get_run_context().result_store, should_persist_result()

    parent_store, child_persist_result, child_store = foo()
    assert child_persist_result is False
    assert child_store.serializer == parent_store.serializer
    assert_blocks_equal(child_store.result_storage, DEFAULT_STORAGE())
    assert child_store.result_storage_block_id is None


async def test_child_flow_inherits_custom_storage(tmp_path, default_persistence_off):
    storage = LocalFileSystem(basepath=tmp_path / "test")
    storage_id = await storage.save("test")

    @flow(result_storage="local-file-system/test")
    def foo():
        child_store, child_persist_result = bar()
        return get_run_context().result_store, child_persist_result, child_store

    @flow
    def bar():
        return get_run_context().result_store, should_persist_result()

    parent_store, child_persist_result, child_store = foo()
    assert child_persist_result is True
    assert child_store.serializer == DEFAULT_SERIALIZER()
    assert child_store.result_storage == parent_store.result_storage
    assert child_store.result_storage_block_id == storage_id


async def test_child_flow_custom_storage(tmp_path, default_persistence_off):
    storage = LocalFileSystem(basepath=tmp_path / "test")
    storage_id = await storage.save("test")

    @flow()
    def foo():
        child_store, child_persist_result = bar()
        return get_run_context().result_store, child_persist_result, child_store

    @flow(result_storage="local-file-system/test")
    def bar():
        return get_run_context().result_store, should_persist_result()

    parent_store, child_persist_result, child_store = foo()
    assert_blocks_equal(parent_store.result_storage, DEFAULT_STORAGE())
    assert child_persist_result is True  # inferred from the storage
    assert child_store.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(child_store.result_storage, storage)
    assert child_store.result_storage_block_id == storage_id


def test_task_inherits_default_result_settings():
    @flow
    def foo():
        return bar()

    @task
    def bar():
        return get_run_context().result_store, should_persist_result()

    task_store, task_persist_result = foo()
    assert task_persist_result is False
    assert task_store.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(task_store.result_storage, DEFAULT_STORAGE())
    assert task_store.result_storage_block_id is None


def test_task_default_result_serializer_can_be_overriden_by_setting():
    @task(persist_result=False)
    def bar():
        return get_run_context().result_store

    with temporary_settings({PREFECT_RESULTS_DEFAULT_SERIALIZER: "json"}):
        task_store = bar()

    assert task_store.serializer == JSONSerializer()


def test_task_default_persist_result_can_be_overriden_by_setting():
    with temporary_settings({PREFECT_RESULTS_PERSIST_BY_DEFAULT: True}):

        @flow
        def foo():
            return bar()

        @task
        def bar():
            return should_persist_result()

        persist_result = foo()

    assert persist_result is True


def test_nested_flow_custom_persist_setting():
    @flow(persist_result=True)
    def foo():
        child_store, child_persist_result = bar()
        return should_persist_result(), child_persist_result, child_store

    @flow(persist_result=False)
    def bar():
        return get_run_context().result_store, should_persist_result()

    flow_persist_result, task_persist_result, task_store = foo()
    assert flow_persist_result is True
    assert task_persist_result is False
    assert task_store.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(task_store.result_storage, DEFAULT_STORAGE())
    assert task_store.result_storage_block_id is None


@pytest.mark.parametrize("toggle", [True, False])
def test_task_custom_cache_setting(toggle):
    task_store = None

    @flow
    def foo():
        bar()
        return get_run_context().result_store

    @task(cache_result_in_memory=toggle)
    def bar():
        nonlocal task_store
        task_store = get_run_context().result_store

    flow_store = foo()
    assert flow_store.cache_result_in_memory is True
    assert task_store.cache_result_in_memory is toggle
    assert task_store.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(task_store.result_storage, DEFAULT_STORAGE())


def test_task_can_opt_out_of_result_persistence_when_flow_uses_feature(
    default_persistence_off,
):
    @flow(retries=3)
    def foo():
        child_store, child_persist_result = bar()
        return should_persist_result(), child_persist_result, child_store

    @flow(persist_result=False)
    def bar():
        return get_run_context().result_store, should_persist_result()

    flow_persist_result, task_persist_result, task_store = foo()
    assert flow_persist_result is False
    assert task_persist_result is False
    assert task_store.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(task_store.result_storage, DEFAULT_STORAGE())
    assert task_store.result_storage_block_id is None


def test_task_can_opt_out_when_persist_result_default_is_overriden_by_setting():
    @flow
    def foo():
        return bar()

    @task(persist_result=False)
    def bar():
        return should_persist_result()

    with temporary_settings({PREFECT_RESULTS_PERSIST_BY_DEFAULT: True}):
        persist_result = foo()

    assert persist_result is False


def test_task_inherits_custom_serializer(default_persistence_off):
    @flow(result_serializer="json", persist_result=False)
    def foo():
        child_store, child_persist_result = bar()
        return get_run_context().result_store, child_persist_result, child_store

    @flow()
    def bar():
        return get_run_context().result_store, should_persist_result()

    flow_store, task_persist_result, task_store = foo()
    assert task_persist_result is False
    assert task_store.serializer == flow_store.serializer
    assert_blocks_equal(task_store.result_storage, DEFAULT_STORAGE())
    assert task_store.result_storage_block_id is None


async def test_task_inherits_custom_storage(tmp_path):
    storage = LocalFileSystem(basepath=tmp_path / "test")
    storage_id = await storage.save("test")

    @flow(result_storage="local-file-system/test", persist_result=True)
    def foo():
        child_store, child_persist_result = bar()
        return get_run_context().result_store, child_persist_result, child_store

    @task(persist_result=True)
    def bar():
        return get_run_context().result_store, should_persist_result()

    flow_store, task_persist_result, task_store = foo()
    assert task_persist_result is True
    assert task_store.serializer == DEFAULT_SERIALIZER()
    assert task_store.result_storage == flow_store.result_storage
    assert task_store.result_storage_block_id == storage_id


def test_task_custom_serializer(default_persistence_off):
    @flow
    def foo():
        child_store, child_persist_result = bar()
        return get_run_context().result_store, child_persist_result, child_store

    @flow(result_serializer="json", persist_result=False)
    def bar():
        return get_run_context().result_store, should_persist_result()

    parent_store, child_persist_result, child_store = foo()
    assert parent_store.serializer == DEFAULT_SERIALIZER()
    assert child_persist_result is False
    assert child_store.serializer == JSONSerializer()
    assert_blocks_equal(child_store.result_storage, DEFAULT_STORAGE())
    assert child_store.result_storage_block_id is None


async def test_nested_flow_custom_storage(tmp_path):
    storage = LocalFileSystem(basepath=tmp_path / "test")
    storage_id = await storage.save("test")

    @flow(persist_result=True)
    def foo():
        child_store, child_persist_result = bar()
        return get_run_context().result_store, child_persist_result, child_store

    @flow(result_storage="local-file-system/test", persist_result=True)
    def bar():
        return get_run_context().result_store, should_persist_result()

    parent_store, child_persist_result, child_store = foo()
    assert_blocks_equal(parent_store.result_storage, DEFAULT_STORAGE())
    assert_blocks_equal(child_store.result_storage, storage)
    assert child_persist_result is True
    assert child_store.serializer == DEFAULT_SERIALIZER()
    assert child_store.result_storage_block_id == storage_id


async def _verify_default_storage_creation_with_persistence(
    prefect_client,
    result_store: prefect.results.ResultStore,
):
    # check that the default block was created
    assert result_store.result_storage is not None
    assert_blocks_equal(result_store.result_storage, DEFAULT_STORAGE())

    # verify storage settings are correctly set
    assert result_store.result_storage_block_id is None


async def _verify_default_storage_creation_without_persistence(
    result_store: prefect.results.ResultStore,
):
    # check that the default block was created
    assert_blocks_equal(result_store.result_storage, DEFAULT_STORAGE())

    # verify storage settings are correctly set
    assert result_store.result_storage_block_id is None


async def test_default_storage_creation_for_flow_with_persistence_features(
    prefect_client,
):
    @flow(persist_result=True)
    def foo():
        return get_run_context().result_store

    result_store = foo()
    await _verify_default_storage_creation_with_persistence(
        prefect_client, result_store
    )


async def test_default_storage_creation_for_flow_without_persistence_features():
    @flow(persist_result=False)
    def foo():
        return get_run_context().result_store

    result_store = foo()
    await _verify_default_storage_creation_without_persistence(result_store)


async def test_default_storage_creation_for_task_with_persistence_features(
    prefect_client,
):
    @task(persist_result=True)
    def my_task_1():
        return get_run_context().result_store

    @flow(retries=2, persist_result=True)
    def my_flow_1():
        return my_task_1()

    result_store = my_flow_1()
    await _verify_default_storage_creation_with_persistence(
        prefect_client, result_store
    )

    @task(cache_key_fn=lambda *_: "always", persist_result=True)
    def my_task_2():
        return get_run_context().result_store

    @flow(persist_result=True)
    def my_flow_2():
        return my_task_2()

    result_store = my_flow_2()
    await _verify_default_storage_creation_with_persistence(
        prefect_client, result_store
    )


async def test_default_storage_creation_for_task_without_persistence_features():
    @task(persist_result=False)
    def my_task():
        return get_run_context().result_store

    @flow()
    def my_flow():
        return my_task()

    result_store = my_flow()
    await _verify_default_storage_creation_without_persistence(result_store)


@pytest.mark.parametrize(
    "options,expected",
    [
        (
            {
                "persist_result": True,
                "cache_result_in_memory": False,
                "result_serializer": "json",
            },
            {
                "persist_result": True,
                "cache_result_in_memory": False,
                "serializer": JSONSerializer(),
            },
        ),
        (
            {
                "persist_result": False,
                "cache_result_in_memory": True,
                "result_serializer": "json",
            },
            {
                "persist_result": False,
                "cache_result_in_memory": True,
                "serializer": JSONSerializer(),
            },
        ),
    ],
)
async def test_result_store_from_task_with_no_flow_run_context(options, expected):
    @task(**options)
    def my_task():
        pass

    assert FlowRunContext.get() is None

    result_store = await ResultStore().update_for_task(task=my_task)

    assert result_store.cache_result_in_memory == expected["cache_result_in_memory"]
    assert result_store.serializer == expected["serializer"]
    assert_blocks_equal(result_store.result_storage, DEFAULT_STORAGE())


@pytest.mark.parametrize("persist_result", [True, False])
async def test_result_store_from_task_loads_persist_result_from_flow_store(
    persist_result,
):
    @task
    def my_task():
        return should_persist_result()

    @flow(persist_result=persist_result)
    def foo():
        return my_task()

    persist_result = foo()

    assert persist_result is persist_result


@pytest.mark.parametrize("persist_result", [True, False])
async def test_result_store_from_task_takes_precedence_from_task(persist_result):
    @task(persist_result=persist_result)
    def my_task():
        return should_persist_result()

    @flow(persist_result=not persist_result)
    def foo():
        return my_task()

    persist_result = foo()

    assert persist_result is persist_result


async def test_result_store_read_and_write_with_metadata_storage(tmp_path):
    metadata_storage = LocalFileSystem(basepath=tmp_path / "metadata")
    result_storage = LocalFileSystem(basepath=tmp_path / "results")
    result_store = ResultStore(
        metadata_storage=metadata_storage, result_storage=result_storage
    )

    key = "test"
    value = "test"
    await result_store.awrite(key=key, obj=value)
    read_value = await result_store.aread(key=key)
    assert read_value.result == value

    # Check that the result is written to the result storage
    assert (
        result_store.serializer.loads((tmp_path / "results" / key).read_bytes())
        == value
    )

    # Check that the metadata is written to the metadata storage
    assert (
        tmp_path / "metadata" / key
    ).read_text() == read_value.metadata.model_dump_json(serialize_as_any=True)


async def test_result_store_exists_with_metadata_storage(tmp_path):
    metadata_storage = LocalFileSystem(basepath=tmp_path / "metadata")
    result_storage = LocalFileSystem(basepath=tmp_path / "results")
    result_store = ResultStore(
        metadata_storage=metadata_storage, result_storage=result_storage
    )

    key = "test"
    value = "test"
    await result_store.awrite(key=key, obj=value)

    assert await result_store.aexists(key=key)
    assert not await result_store.aexists(key="nonexistent")
    assert result_store.exists(key=key)
    assert not result_store.exists(key="nonexistent")

    # Remove the metadata file and check that the result is not found
    (tmp_path / "metadata" / key).unlink()
    assert not await result_store.aexists(key=key)
    assert not result_store.exists(key=key)


async def test_result_store_exists_with_no_metadata_storage(tmp_path):
    result_storage = LocalFileSystem(basepath=tmp_path / "results")
    result_store = ResultStore(result_storage=result_storage)

    key = "test"
    value = "test"
    await result_store.awrite(key=key, obj=value)
    assert await result_store.aexists(key=key)
    assert result_store.exists(key=key)

    # Remove the result file and check that the result is not found
    (tmp_path / "results" / key).unlink()
    assert not await result_store.aexists(key=key)
    assert not result_store.exists(key=key)


async def test_supports_isolation_level():
    store_with_lock_manager = ResultStore(lock_manager=MemoryLockManager())
    store_without_lock_manager = ResultStore()

    assert store_with_lock_manager.supports_isolation_level(
        IsolationLevel.READ_COMMITTED
    )
    assert store_with_lock_manager.supports_isolation_level(IsolationLevel.SERIALIZABLE)

    assert store_without_lock_manager.supports_isolation_level(
        IsolationLevel.READ_COMMITTED
    )
    assert not store_without_lock_manager.supports_isolation_level(
        IsolationLevel.SERIALIZABLE
    )


async def test_deprecation_warning_on_persist_result():
    with pytest.warns(DeprecationWarning):
        ResultStore(persist_result=True)

    with pytest.warns(DeprecationWarning):
        ResultStore(persist_result=False)
