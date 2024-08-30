import pytest

import prefect.exceptions
import prefect.results
from prefect import flow, task
from prefect.context import FlowRunContext, get_run_context
from prefect.filesystems import LocalFileSystem
from prefect.results import (
    PersistedResult,
    ResultFactory,
)
from prefect.serializers import JSONSerializer, PickleSerializer
from prefect.settings import (
    PREFECT_LOCAL_STORAGE_PATH,
    PREFECT_RESULTS_DEFAULT_SERIALIZER,
    PREFECT_RESULTS_PERSIST_BY_DEFAULT,
    temporary_settings,
)
from prefect.testing.utilities import assert_blocks_equal

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
async def factory():
    return ResultFactory(persist_result=True)


async def test_create_result_reference(factory):
    result = await factory.create_result({"foo": "bar"})
    assert isinstance(result, PersistedResult)
    assert result.serializer_type == factory.serializer.type
    assert result.storage_block_id == factory.storage_block_id
    assert await result.get() == {"foo": "bar"}


async def test_create_result_reference_has_cached_object(factory):
    result = await factory.create_result({"foo": "bar"})
    assert result.has_cached_object()


def test_root_flow_default_result_factory():
    @flow
    def foo():
        return get_run_context().result_factory

    result_factory = foo()
    assert result_factory.persist_result is False
    assert result_factory.cache_result_in_memory is True
    assert result_factory.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(result_factory.storage_block, DEFAULT_STORAGE())
    assert result_factory.storage_block_id is None


def test_root_flow_default_result_serializer_can_be_overriden_by_setting():
    @flow(persist_result=False)
    def foo():
        return get_run_context().result_factory

    with temporary_settings({PREFECT_RESULTS_DEFAULT_SERIALIZER: "json"}):
        result_factory = foo()
    assert result_factory.serializer == JSONSerializer()


def test_root_flow_default_persist_result_can_be_overriden_by_setting():
    @flow
    def foo():
        return get_run_context().result_factory

    with temporary_settings({PREFECT_RESULTS_PERSIST_BY_DEFAULT: True}):
        result_factory = foo()
    assert result_factory.persist_result is True


def test_root_flow_can_opt_out_when_persist_result_default_is_overriden_by_setting():
    @flow(persist_result=False)
    def foo():
        return get_run_context().result_factory.persist_result

    with temporary_settings({PREFECT_RESULTS_PERSIST_BY_DEFAULT: True}):
        persist_result = foo()

    assert persist_result is False


@pytest.mark.parametrize("toggle", [True, False])
def test_root_flow_custom_persist_setting(toggle):
    @flow(persist_result=toggle)
    def foo():
        result_factory = get_run_context().result_factory
        return (
            result_factory.persist_result,
            result_factory.serializer,
            result_factory.storage_block,
        )

    persist_result, serializer, storage_block = foo()
    assert persist_result is toggle
    assert serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(storage_block, DEFAULT_STORAGE())


def test_root_flow_persists_results_when_flow_uses_feature():
    @flow(cache_result_in_memory=False, persist_result=True)
    def foo():
        result_factory = get_run_context().result_factory
        return (
            result_factory.persist_result,
            result_factory.serializer,
            result_factory.storage_block,
        )

    persist_result, serializer, storage_block = foo()
    assert persist_result is True
    assert serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(storage_block, DEFAULT_STORAGE())


def test_root_flow_can_opt_out_of_persistence_when_flow_uses_feature():
    @flow(cache_result_in_memory=False, persist_result=False)
    def foo():
        result_factory = get_run_context().result_factory
        return (
            result_factory.persist_result,
            result_factory.serializer,
            result_factory.storage_block,
            result_factory.storage_block_id,
        )

    persist_result, serializer, storage_block, storage_block_id = foo()
    assert persist_result is False
    assert serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(storage_block, DEFAULT_STORAGE())
    assert storage_block_id is None


@pytest.mark.parametrize("toggle", [True, False])
def test_root_flow_custom_cache_setting(toggle, default_persistence_off):
    cache_result_in_memory = None
    serializer = None
    storage_block = None

    @flow(cache_result_in_memory=toggle)
    def foo():
        nonlocal cache_result_in_memory, serializer, storage_block
        result_factory = get_run_context().result_factory
        cache_result_in_memory = result_factory.cache_result_in_memory
        serializer = result_factory.serializer
        storage_block = result_factory.storage_block

    foo()
    assert cache_result_in_memory is toggle
    assert serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(storage_block, DEFAULT_STORAGE())


def test_root_flow_custom_serializer_by_type_string():
    @flow(result_serializer="json", persist_result=False)
    def foo():
        result_factory = get_run_context().result_factory
        return (
            result_factory.persist_result,
            result_factory.serializer,
            result_factory.storage_block,
            result_factory.storage_block_id,
        )

    persist_result, serializer, storage_block, storage_block_id = foo()
    assert persist_result is False
    assert serializer == JSONSerializer()
    assert_blocks_equal(storage_block, DEFAULT_STORAGE())
    assert storage_block_id is None


def test_root_flow_custom_serializer_by_instance(default_persistence_off):
    @flow(persist_result=False, result_serializer=JSONSerializer(jsonlib="orjson"))
    def foo():
        result_factory = get_run_context().result_factory
        return (
            result_factory.persist_result,
            result_factory.serializer,
            result_factory.storage_block,
            result_factory.storage_block_id,
        )

    persist_result, serializer, storage_block, storage_block_id = foo()
    assert persist_result is False
    assert serializer == JSONSerializer(jsonlib="orjson")
    assert_blocks_equal(storage_block, DEFAULT_STORAGE())
    assert storage_block_id is None


async def test_root_flow_custom_storage_by_slug(tmp_path, default_persistence_off):
    storage = LocalFileSystem(basepath=tmp_path / "test")
    storage_id = await storage.save("test")

    @flow(result_storage="local-file-system/test")
    def foo():
        result_factory = get_run_context().result_factory
        return (
            result_factory.persist_result,
            result_factory.serializer,
            result_factory.storage_block,
            result_factory.storage_block_id,
        )

    persist_result, serializer, storage_block, storage_block_id = foo()
    assert persist_result is True  # inferred from the storage
    assert serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(storage_block, storage)
    assert storage_block_id == storage_id


async def test_root_flow_custom_storage_by_instance_presaved(
    tmp_path, default_persistence_off
):
    storage = LocalFileSystem(basepath=tmp_path / "test")
    storage_id = await storage.save("test")

    @flow(result_storage=storage)
    def foo():
        result_factory = get_run_context().result_factory
        return (
            result_factory.persist_result,
            result_factory.serializer,
            result_factory.storage_block,
            result_factory.storage_block_id,
        )

    persist_result, serializer, storage_block, storage_block_id = foo()
    assert persist_result is True  # inferred from the storage
    assert serializer == DEFAULT_SERIALIZER()
    assert storage_block == storage
    assert storage_block._is_anonymous is False
    assert storage_block_id == storage_id


def test_child_flow_inherits_default_result_settings(default_persistence_off):
    @flow
    def foo():
        return bar()

    @flow
    def bar():
        result_factory = get_run_context().result_factory
        return (
            result_factory.persist_result,
            result_factory.serializer,
            result_factory.storage_block,
            result_factory.storage_block_id,
        )

    persist_result, serializer, storage_block, storage_block_id = foo()
    assert persist_result is False
    assert serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(storage_block, DEFAULT_STORAGE())
    assert storage_block_id is None


def test_child_flow_default_result_serializer_can_be_overriden_by_setting(
    default_persistence_off,
):
    @flow
    def foo():
        return bar()

    @flow
    def bar():
        result_factory = get_run_context().result_factory
        return result_factory.serializer

    with temporary_settings({PREFECT_RESULTS_DEFAULT_SERIALIZER: "json"}):
        serializer = foo()

    assert serializer == JSONSerializer()


def test_child_flow_default_persist_result_can_be_overriden_by_setting():
    @flow
    def foo():
        return bar()

    @flow
    def bar():
        result_factory = get_run_context().result_factory
        return result_factory.persist_result

    with temporary_settings({PREFECT_RESULTS_PERSIST_BY_DEFAULT: True}):
        persist_result = foo()

    assert persist_result is True


def test_child_flow_can_opt_out_when_persist_result_default_is_overriden_by_setting():
    @flow
    def foo():
        return bar()

    @flow(persist_result=False)
    def bar():
        result_factory = get_run_context().result_factory
        return result_factory.persist_result

    with temporary_settings({PREFECT_RESULTS_PERSIST_BY_DEFAULT: True}):
        persist_result = foo()

    assert persist_result is False


def test_child_flow_custom_persist_setting(default_persistence_off):
    @flow
    def foo():
        result_factory = get_run_context().result_factory
        child_persist_result, child_serializer, child_storage_block = bar()
        return (
            result_factory.persist_result,
            child_persist_result,
            child_serializer,
            child_storage_block,
        )

    @flow(persist_result=True)
    def bar():
        result_factory = get_run_context().result_factory
        return (
            result_factory.persist_result,
            result_factory.serializer,
            result_factory.storage_block,
        )

    (
        parent_persist_result,
        child_persist_result,
        child_serializer,
        child_storage_block,
    ) = foo()
    assert parent_persist_result is False
    assert child_persist_result is True
    assert child_serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(child_storage_block, DEFAULT_STORAGE())


@pytest.mark.parametrize("toggle", [True, False])
def test_child_flow_custom_cache_setting(toggle, default_persistence_off):
    @flow
    def foo():
        result_factory = get_run_context().result_factory
        child_cache_result_in_memory, child_serializer, child_storage_block = bar()
        return (
            result_factory.cache_result_in_memory,
            child_cache_result_in_memory,
            child_serializer,
            child_storage_block,
        )

    @flow(cache_result_in_memory=toggle)
    def bar():
        result_factory = get_run_context().result_factory
        child_cache_result_in_memory = result_factory.cache_result_in_memory
        child_serializer = result_factory.serializer
        child_storage_block = result_factory.storage_block
        return child_cache_result_in_memory, child_serializer, child_storage_block

    (
        parent_cache_result_in_memory,
        child_cache_result_in_memory,
        child_serializer,
        child_storage_block,
    ) = foo()
    assert parent_cache_result_in_memory is True
    assert child_cache_result_in_memory is toggle
    assert child_serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(child_storage_block, DEFAULT_STORAGE())


def test_child_flow_can_opt_out_of_result_persistence_when_parent_uses_feature(
    default_persistence_off,
):
    @flow(retries=3)
    def foo():
        return get_run_context().result_factory, bar()

    @flow(persist_result=False)
    def bar():
        return get_run_context().result_factory

    parent_factory, child_factory = foo()
    assert parent_factory.persist_result is False
    assert child_factory.persist_result is False
    assert child_factory.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(child_factory.storage_block, DEFAULT_STORAGE())
    assert child_factory.storage_block_id is None


def test_child_flow_inherits_custom_serializer(default_persistence_off):
    @flow(persist_result=False, result_serializer="json")
    def foo():
        result_factory = get_run_context().result_factory
        (
            child_persist_result,
            child_serializer,
            child_storage_block,
            child_storage_block_id,
        ) = bar()
        return (
            result_factory.serializer,
            child_persist_result,
            child_serializer,
            child_storage_block,
            child_storage_block_id,
        )

    @flow()
    def bar():
        result_factory = get_run_context().result_factory
        return (
            result_factory.persist_result,
            result_factory.serializer,
            result_factory.storage_block,
            result_factory.storage_block_id,
        )

    (
        parent_serializer,
        child_persist_result,
        child_serializer,
        child_storage_block,
        child_storage_block_id,
    ) = foo()
    assert child_persist_result is False
    assert child_serializer == parent_serializer
    assert_blocks_equal(child_storage_block, DEFAULT_STORAGE())
    assert child_storage_block_id is None


async def test_child_flow_inherits_custom_storage(tmp_path, default_persistence_off):
    storage = LocalFileSystem(basepath=tmp_path / "test")
    storage_id = await storage.save("test")

    @flow(result_storage="local-file-system/test")
    def foo():
        result_factory = get_run_context().result_factory
        (
            child_persist_result,
            child_serializer,
            child_storage_block,
            child_storage_block_id,
        ) = bar()
        return (
            result_factory.serializer,
            child_persist_result,
            child_serializer,
            child_storage_block,
            child_storage_block_id,
        )

    @flow
    def bar():
        result_factory = get_run_context().result_factory
        return (
            result_factory.persist_result,
            result_factory.serializer,
            result_factory.storage_block,
            result_factory.storage_block_id,
        )

    (
        parent_serializer,
        child_persist_result,
        child_serializer,
        child_storage_block,
        child_storage_block_id,
    ) = foo()
    assert child_persist_result is True
    assert child_serializer == parent_serializer
    assert_blocks_equal(child_storage_block, storage)
    assert child_storage_block_id == storage_id


async def test_child_flow_custom_storage(tmp_path, default_persistence_off):
    storage = LocalFileSystem(basepath=tmp_path / "test")
    storage_id = await storage.save("test")

    @flow()
    def foo():
        result_factory = get_run_context().result_factory
        (
            child_persist_result,
            child_serializer,
            child_storage_block,
            child_storage_block_id,
        ) = bar()
        return (
            result_factory.storage_block,
            child_persist_result,
            child_serializer,
            child_storage_block,
            child_storage_block_id,
        )

    @flow(result_storage="local-file-system/test")
    def bar():
        result_factory = get_run_context().result_factory
        return (
            result_factory.persist_result,
            result_factory.serializer,
            result_factory.storage_block,
            result_factory.storage_block_id,
        )

    (
        parent_storage_block,
        child_persist_result,
        child_serializer,
        child_storage_block,
        child_storage_block_id,
    ) = foo()
    assert_blocks_equal(parent_storage_block, DEFAULT_STORAGE())
    assert child_persist_result is True  # inferred from the storage
    assert child_serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(child_storage_block, storage)
    assert child_storage_block_id == storage_id


def test_task_inherits_default_result_settings():
    @flow
    def foo():
        return get_run_context().result_factory, bar()

    @task
    def bar():
        return get_run_context().result_factory

    _, task_factory = foo()
    assert task_factory.persist_result is False
    assert task_factory.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(task_factory.storage_block, DEFAULT_STORAGE())
    assert task_factory.storage_block_id is None


def test_task_default_result_serializer_can_be_overriden_by_setting():
    @task(persist_result=False)
    def bar():
        return get_run_context().result_factory

    with temporary_settings({PREFECT_RESULTS_DEFAULT_SERIALIZER: "json"}):
        task_factory = bar()

    assert task_factory.serializer == JSONSerializer()


def test_task_default_persist_result_can_be_overriden_by_setting():
    with temporary_settings({PREFECT_RESULTS_PERSIST_BY_DEFAULT: True}):

        @flow
        def foo():
            return bar()

        @task
        def bar():
            result_factory = get_run_context().result_factory
            return result_factory.persist_result

        task_persist_result = foo()

    assert task_persist_result is True


def test_nested_flow_custom_persist_setting():
    @flow(persist_result=True)
    def foo():
        result_factory = get_run_context().result_factory
        (
            child_persist_result,
            child_serializer,
            child_storage_block,
            child_storage_block_id,
        ) = bar()
        return (
            result_factory.persist_result,
            child_persist_result,
            child_serializer,
            child_storage_block,
            child_storage_block_id,
        )

    @flow(persist_result=False)
    def bar():
        result_factory = get_run_context().result_factory
        return (
            result_factory.persist_result,
            result_factory.serializer,
            result_factory.storage_block,
            result_factory.storage_block_id,
        )

    (
        parent_persist_result,
        child_persist_result,
        child_serializer,
        child_storage_block,
        child_storage_block_id,
    ) = foo()
    assert parent_persist_result is True
    assert child_persist_result is False
    assert child_serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(child_storage_block, DEFAULT_STORAGE())
    assert child_storage_block_id is None


@pytest.mark.parametrize("toggle", [True, False])
def test_task_custom_cache_setting(toggle):
    @flow
    def foo():
        task_persist_result, task_serializer, task_storage_block = bar()
        return (
            get_run_context().result_factory.cache_result_in_memory,
            task_persist_result,
            task_serializer,
            task_storage_block,
        )

    @task(cache_result_in_memory=toggle)
    def bar():
        task_factory = get_run_context().result_factory
        return (
            task_factory.cache_result_in_memory,
            task_factory.serializer,
            task_factory.storage_block,
        )

    (
        flow_cache_result_in_memory,
        task_persist_result,
        task_serializer,
        task_storage_block,
    ) = foo()
    assert flow_cache_result_in_memory is True
    assert task_persist_result is toggle
    assert task_serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(task_storage_block, DEFAULT_STORAGE())


def test_task_can_opt_out_of_result_persistence_when_flow_uses_feature(
    default_persistence_off,
):
    @flow(retries=3)
    def foo():
        return get_run_context().result_factory, bar()

    @flow(persist_result=False)
    def bar():
        return get_run_context().result_factory

    flow_factory, task_factory = foo()
    assert flow_factory.persist_result is False
    assert task_factory.persist_result is False
    assert task_factory.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(task_factory.storage_block, DEFAULT_STORAGE())
    assert task_factory.storage_block_id is None


def test_task_can_opt_out_when_persist_result_default_is_overriden_by_setting():
    @flow
    def foo():
        return bar()

    @task(persist_result=False)
    def bar():
        task_factory = get_run_context().result_factory
        return task_factory.persist_result

    with temporary_settings({PREFECT_RESULTS_PERSIST_BY_DEFAULT: True}):
        task_persist_result = foo()

    assert task_persist_result is False


def test_task_inherits_custom_serializer(default_persistence_off):
    @flow(result_serializer="json", persist_result=False)
    def foo():
        (
            task_persist_result,
            task_serializer,
            task_storage_block,
            task_storage_block_id,
        ) = bar()
        return (
            get_run_context().result_factory.serializer,
            task_persist_result,
            task_serializer,
            task_storage_block,
            task_storage_block_id,
        )

    @flow()
    def bar():
        child_factory = get_run_context().result_factory
        return (
            child_factory.persist_result,
            child_factory.serializer,
            child_factory.storage_block,
            child_factory.storage_block_id,
        )

    (
        flow_serializer,
        task_persist_result,
        task_serializer,
        task_storage_block,
        task_storage_block_id,
    ) = foo()
    assert task_persist_result is False
    assert task_serializer == flow_serializer
    assert_blocks_equal(task_storage_block, DEFAULT_STORAGE())
    assert task_storage_block_id is None


async def test_task_inherits_custom_storage(tmp_path):
    storage = LocalFileSystem(basepath=tmp_path / "test")
    storage_id = await storage.save("test")

    @flow(result_storage="local-file-system/test", persist_result=True)
    def foo():
        return bar()

    @task(persist_result=True)
    def bar():
        task_factory = get_run_context().result_factory
        return (
            task_factory.persist_result,
            task_factory.serializer,
            task_factory.storage_block,
            task_factory.storage_block_id,
        )

    (
        task_persist_result,
        task_serializer,
        task_storage_block,
        task_storage_block_id,
    ) = foo()
    assert task_persist_result is True
    assert task_serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(task_storage_block, storage)
    assert task_storage_block_id == storage_id


def test_task_custom_serializer(default_persistence_off):
    @flow
    def foo():
        (
            child_persist_result,
            child_serializer,
            child_storage_block,
            child_storage_block_id,
        ) = bar()
        return (
            get_run_context().result_factory.serializer,
            child_persist_result,
            child_serializer,
            child_storage_block,
            child_storage_block_id,
        )

    @flow(result_serializer="json", persist_result=False)
    def bar():
        result_factory = get_run_context().result_factory
        return (
            result_factory.persist_result,
            result_factory.serializer,
            result_factory.storage_block,
            result_factory.storage_block_id,
        )

    (
        parent_serializer,
        child_persist_result,
        child_serializer,
        child_storage_block,
        child_storage_block_id,
    ) = foo()
    assert parent_serializer == DEFAULT_SERIALIZER()
    assert child_persist_result is False
    assert child_serializer == JSONSerializer()
    assert_blocks_equal(child_storage_block, DEFAULT_STORAGE())
    assert child_storage_block_id is None


async def test_nested_flow_custom_storage(tmp_path):
    storage = LocalFileSystem(basepath=tmp_path / "test")
    storage_id = await storage.save("test")

    @flow(persist_result=True)
    def foo():
        (
            child_persist_result,
            child_serializer,
            child_storage_block,
            child_storage_block_id,
        ) = bar()
        return (
            get_run_context().result_factory.storage_block,
            child_persist_result,
            child_serializer,
            child_storage_block,
            child_storage_block_id,
        )

    @flow(result_storage="local-file-system/test", persist_result=True)
    def bar():
        result_factory = get_run_context().result_factory
        return (
            result_factory.persist_result,
            result_factory.serializer,
            result_factory.storage_block,
            result_factory.storage_block_id,
        )

    (
        parent_storage_block,
        child_persist_result,
        child_serializer,
        child_storage_block,
        child_storage_block_id,
    ) = foo()
    assert_blocks_equal(parent_storage_block, DEFAULT_STORAGE())
    assert_blocks_equal(child_storage_block, storage)
    assert child_persist_result is True
    assert child_serializer == DEFAULT_SERIALIZER()
    assert child_storage_block_id == storage_id


async def _verify_default_storage_creation_with_persistence(
    prefect_client,
    result_factory: prefect.results.ResultFactory,
):
    # check that the default block was created
    assert result_factory.storage_block is not None
    assert_blocks_equal(result_factory.storage_block, DEFAULT_STORAGE())

    # verify storage settings are correctly set
    assert result_factory.persist_result is True
    assert result_factory.storage_block_id is None


async def _verify_default_storage_creation_without_persistence(
    result_factory: prefect.results.ResultFactory,
):
    # check that the default block was created
    assert_blocks_equal(result_factory.storage_block, DEFAULT_STORAGE())

    # verify storage settings are correctly set
    assert result_factory.persist_result is False
    assert result_factory.storage_block_id is None


async def test_default_storage_creation_for_flow_with_persistence_features(
    prefect_client,
):
    @flow(persist_result=True)
    async def foo():
        await _verify_default_storage_creation_with_persistence(
            prefect_client, get_run_context().result_factory
        )

    foo()


async def test_default_storage_creation_for_flow_without_persistence_features():
    @flow(persist_result=False)
    def foo():
        _verify_default_storage_creation_without_persistence(
            get_run_context().result_factory
        )

    foo()


async def test_default_storage_creation_for_task_with_persistence_features(
    prefect_client,
):
    @task(persist_result=True)
    async def my_task_1():
        await _verify_default_storage_creation_with_persistence(
            prefect_client, get_run_context().result_factory
        )

    @flow(retries=2, persist_result=True)
    async def my_flow_1():
        await my_task_1()

    my_flow_1()

    @task(cache_key_fn=lambda *_: "always", persist_result=True)
    async def my_task_2():
        await _verify_default_storage_creation_with_persistence(
            prefect_client, get_run_context().result_factory
        )

    @flow(persist_result=True)
    async def my_flow_2():
        await my_task_2()

    my_flow_2()


async def test_default_storage_creation_for_task_without_persistence_features():
    @task(persist_result=False)
    def my_task():
        return get_run_context().result_factory

    @flow()
    def my_flow():
        return my_task()

    result_factory = my_flow()
    await _verify_default_storage_creation_without_persistence(result_factory)


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
async def test_result_factory_create_result_with_no_flow_run_context(options, expected):
    @task(**options)
    def my_task():
        result_factory = ResultFactory()
        result = result_factory.create_result("foo")
        return (
            result.serialize_to_none,
            result._should_cache_object,
            result._serializer,
            result._storage_block,
        )

    assert FlowRunContext.get() is None

    serialize_to_none, should_cache_object, serializer, storage_block = my_task()

    assert not serialize_to_none == expected["persist_result"]
    assert should_cache_object == expected["cache_result_in_memory"]
    assert serializer == expected["serializer"]
    assert_blocks_equal(storage_block, DEFAULT_STORAGE())


@pytest.mark.parametrize("persist_result", [True, False])
async def test_result_factory_from_task_loads_persist_result_from_flow_factory(
    persist_result,
):
    @task
    def my_task():
        return get_run_context().result_factory.persist_result

    @flow(persist_result=persist_result)
    def foo():
        return my_task()

    persist_result = foo()

    assert persist_result is persist_result


@pytest.mark.parametrize("persist_result", [True, False])
async def test_result_factory_from_task_takes_precedence_from_task(persist_result):
    @task(persist_result=persist_result)
    def my_task():
        return get_run_context().result_factory.persist_result

    @flow(persist_result=not persist_result)
    def foo():
        return my_task()

    persist_result = foo()

    assert persist_result is persist_result
