import uuid

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
async def factory(prefect_client):
    return await ResultFactory.default_factory(
        client=prefect_client, persist_result=True
    )


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
    assert result_factory.persist_result is True
    assert result_factory.cache_result_in_memory is True
    assert result_factory.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(result_factory.storage_block, DEFAULT_STORAGE())
    assert result_factory.storage_block_id is not None


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
        return get_run_context().result_factory

    with temporary_settings({PREFECT_RESULTS_PERSIST_BY_DEFAULT: True}):
        result_factory = foo()

    assert result_factory.persist_result is False


@pytest.mark.parametrize("toggle", [True, False])
def test_root_flow_custom_persist_setting(toggle):
    @flow(persist_result=toggle)
    def foo():
        return get_run_context().result_factory

    result_factory = foo()
    assert result_factory.persist_result is toggle
    assert result_factory.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(result_factory.storage_block, DEFAULT_STORAGE())

    if toggle:
        assert isinstance(result_factory.storage_block_id, uuid.UUID)
    else:
        assert result_factory.storage_block_id is not None


@pytest.mark.parametrize("options", [{"cache_result_in_memory": False}])
def test_root_flow_persists_results_when_flow_uses_feature(options):
    @flow(**options)
    def foo():
        return get_run_context().result_factory

    result_factory = foo()
    assert result_factory.persist_result is True
    assert result_factory.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(result_factory.storage_block, DEFAULT_STORAGE())
    assert isinstance(result_factory.storage_block_id, uuid.UUID)


@pytest.mark.parametrize("options", [{"cache_result_in_memory": False}])
def test_root_flow_can_opt_out_of_persistence_when_flow_uses_feature(options):
    result_factory = None

    @flow(**options, persist_result=False)
    def foo():
        nonlocal result_factory
        result_factory = get_run_context().result_factory

    foo()
    assert result_factory.persist_result is False
    assert result_factory.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(result_factory.storage_block, DEFAULT_STORAGE())
    assert result_factory.storage_block_id is not None


@pytest.mark.parametrize("toggle", [True, False])
def test_root_flow_custom_cache_setting(toggle, default_persistence_off):
    result_factory = None

    @flow(cache_result_in_memory=toggle)
    def foo():
        nonlocal result_factory
        result_factory = get_run_context().result_factory

    foo()
    assert result_factory.cache_result_in_memory is toggle
    assert result_factory.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(result_factory.storage_block, DEFAULT_STORAGE())

    if toggle:
        assert result_factory.storage_block_id is not None
    else:
        assert isinstance(result_factory.storage_block_id, uuid.UUID)


def test_root_flow_custom_serializer_by_type_string():
    @flow(result_serializer="json", persist_result=False)
    def foo():
        return get_run_context().result_factory

    result_factory = foo()
    assert result_factory.persist_result is False
    assert result_factory.serializer == JSONSerializer()
    assert_blocks_equal(result_factory.storage_block, DEFAULT_STORAGE())
    assert result_factory.storage_block_id is not None


def test_root_flow_custom_serializer_by_instance(default_persistence_off):
    @flow(result_serializer=JSONSerializer(jsonlib="orjson"))
    def foo():
        return get_run_context().result_factory

    result_factory = foo()
    assert result_factory.persist_result is False
    assert result_factory.serializer == JSONSerializer(jsonlib="orjson")
    assert_blocks_equal(result_factory.storage_block, DEFAULT_STORAGE())
    assert result_factory.storage_block_id is not None


async def test_root_flow_custom_storage_by_slug(tmp_path, default_persistence_off):
    storage = LocalFileSystem(basepath=tmp_path / "test")
    storage_id = await storage.save("test")

    @flow(result_storage="local-file-system/test")
    def foo():
        return get_run_context().result_factory

    result_factory = foo()
    assert result_factory.persist_result is False
    assert result_factory.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(result_factory.storage_block, storage)
    assert result_factory.storage_block_id == storage_id


async def test_root_flow_custom_storage_by_instance_presaved(
    tmp_path, default_persistence_off
):
    storage = LocalFileSystem(basepath=tmp_path / "test")
    storage_id = await storage.save("test")

    @flow(result_storage=storage)
    def foo():
        return get_run_context().result_factory

    result_factory = foo()
    assert result_factory.persist_result is False
    assert result_factory.serializer == DEFAULT_SERIALIZER()
    assert result_factory.storage_block == storage
    assert result_factory.storage_block._is_anonymous is False
    assert result_factory.storage_block_id == storage_id


async def test_root_flow_custom_storage_by_instance_unsaved(prefect_client, tmp_path):
    storage = LocalFileSystem(basepath=tmp_path / "test")

    @flow(
        result_storage=storage, cache_result_in_memory=False
    )  # use a feature that requires persistence
    def foo():
        return get_run_context().result_factory

    result_factory = foo()
    assert result_factory.persist_result is True
    assert result_factory.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(result_factory.storage_block, storage)
    assert result_factory.storage_block._is_anonymous is True
    assert isinstance(result_factory.storage_block_id, uuid.UUID)

    # Check that the block is matching in the API
    storage_block_document = await prefect_client.read_block_document(
        result_factory.storage_block_id
    )
    assert_blocks_equal(
        LocalFileSystem._from_block_document(storage_block_document), storage
    )


def test_child_flow_inherits_default_result_settings(default_persistence_off):
    @flow
    def foo():
        return get_run_context().result_factory, bar()

    @flow
    def bar():
        return get_run_context().result_factory

    _, child_factory = foo()
    assert child_factory.persist_result is False
    assert child_factory.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(child_factory.storage_block, DEFAULT_STORAGE())
    assert child_factory.storage_block_id is not None


def test_child_flow_default_result_serializer_can_be_overriden_by_setting(
    default_persistence_off,
):
    @flow
    def foo():
        return get_run_context().result_factory, bar()

    @flow
    def bar():
        return get_run_context().result_factory

    with temporary_settings({PREFECT_RESULTS_DEFAULT_SERIALIZER: "json"}):
        _, child_factory = foo()

    assert child_factory.serializer == JSONSerializer()


def test_child_flow_default_persist_result_can_be_overriden_by_setting():
    @flow
    def foo():
        return get_run_context().result_factory, bar()

    @flow
    def bar():
        return get_run_context().result_factory

    with temporary_settings({PREFECT_RESULTS_PERSIST_BY_DEFAULT: True}):
        _, child_factory = foo()

    assert child_factory.persist_result is True


def test_child_flow_can_opt_out_when_persist_result_default_is_overriden_by_setting():
    @flow
    def foo():
        return get_run_context().result_factory, bar()

    @flow(persist_result=False)
    def bar():
        return get_run_context().result_factory

    with temporary_settings({PREFECT_RESULTS_PERSIST_BY_DEFAULT: True}):
        _, child_factory = foo()

    assert child_factory.persist_result is False


def test_child_flow_custom_persist_setting(default_persistence_off):
    @flow
    def foo():
        return get_run_context().result_factory, bar()

    @flow(persist_result=True)
    def bar():
        return get_run_context().result_factory

    parent_factory, child_factory = foo()
    assert parent_factory.persist_result is False
    assert child_factory.persist_result is True
    assert child_factory.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(child_factory.storage_block, DEFAULT_STORAGE())
    assert isinstance(child_factory.storage_block_id, uuid.UUID)


@pytest.mark.parametrize("toggle", [True, False])
def test_child_flow_custom_cache_setting(toggle, default_persistence_off):
    child_factory = None

    @flow
    def foo():
        bar(return_state=True)
        return get_run_context().result_factory

    @flow(cache_result_in_memory=toggle)
    def bar():
        nonlocal child_factory
        child_factory = get_run_context().result_factory

    parent_factory = foo()
    assert parent_factory.cache_result_in_memory is True
    assert child_factory.cache_result_in_memory is toggle
    assert child_factory.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(child_factory.storage_block, DEFAULT_STORAGE())

    assert isinstance(child_factory.storage_block_id, uuid.UUID)


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
    assert child_factory.storage_block_id is not None


def test_child_flow_inherits_custom_serializer(default_persistence_off):
    @flow(result_serializer="json")
    def foo():
        return get_run_context().result_factory, bar()

    @flow()
    def bar():
        return get_run_context().result_factory

    parent_factory, child_factory = foo()
    assert child_factory.persist_result is False
    assert child_factory.serializer == parent_factory.serializer
    assert_blocks_equal(child_factory.storage_block, DEFAULT_STORAGE())
    assert child_factory.storage_block_id is not None


async def test_child_flow_inherits_custom_storage(tmp_path, default_persistence_off):
    storage = LocalFileSystem(basepath=tmp_path / "test")
    storage_id = await storage.save("test")

    @flow(result_storage="local-file-system/test")
    def foo():
        return get_run_context().result_factory, bar()

    @flow
    def bar():
        return get_run_context().result_factory

    parent_factory, child_factory = foo()
    assert child_factory.persist_result is False
    assert child_factory.serializer == DEFAULT_SERIALIZER()
    assert child_factory.storage_block == parent_factory.storage_block
    assert child_factory.storage_block_id == storage_id


def test_child_flow_custom_serializer(default_persistence_off):
    @flow
    def foo():
        return get_run_context().result_factory, bar()

    @flow(result_serializer="json")
    def bar():
        return get_run_context().result_factory

    parent_factory, child_factory = foo()
    assert parent_factory.serializer == DEFAULT_SERIALIZER()
    assert child_factory.persist_result is False
    assert child_factory.serializer == JSONSerializer()
    assert_blocks_equal(child_factory.storage_block, DEFAULT_STORAGE())
    assert child_factory.storage_block_id is not None


async def test_child_flow_custom_storage(tmp_path, default_persistence_off):
    storage = LocalFileSystem(basepath=tmp_path / "test")
    storage_id = await storage.save("test")

    @flow()
    def foo():
        return get_run_context().result_factory, bar()

    @flow(result_storage="local-file-system/test")
    def bar():
        return get_run_context().result_factory

    parent_factory, child_factory = foo()
    assert_blocks_equal(parent_factory.storage_block, DEFAULT_STORAGE())
    assert child_factory.persist_result is False
    assert child_factory.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(child_factory.storage_block, storage)
    assert child_factory.storage_block_id == storage_id


async def test_child_flow_custom_storage_by_instance_unsaved(prefect_client, tmp_path):
    storage = LocalFileSystem(basepath=tmp_path / "test")

    @flow(cache_result_in_memory=False)  # use a feature that requires persistence
    def foo():
        print(f"In parent, persist={get_run_context().result_factory.persist_result}")
        return get_run_context().result_factory, bar()

    @flow(result_storage=storage, cache_result_in_memory=False)
    def bar():
        print(f"In child, persist={get_run_context().result_factory.persist_result}")
        return get_run_context().result_factory

    parent_factory, child_factory = foo()

    # The parent should be unchanged
    assert_blocks_equal(parent_factory.storage_block, DEFAULT_STORAGE())
    assert parent_factory.storage_block_id != child_factory.storage_block_id

    # The child should have a saved custom storage
    assert_blocks_equal(child_factory.storage_block, storage)
    assert child_factory.storage_block._is_anonymous is True
    assert isinstance(child_factory.storage_block_id, uuid.UUID)

    # Check that the block is matching in the API
    storage_block_document = await prefect_client.read_block_document(
        child_factory.storage_block_id
    )
    assert_blocks_equal(
        LocalFileSystem._from_block_document(storage_block_document), storage
    )

    # Other settings should not be changed
    assert child_factory.persist_result is True
    assert child_factory.serializer == DEFAULT_SERIALIZER()


def test_task_inherits_default_result_settings():
    @flow
    def foo():
        return get_run_context().result_factory, bar()

    @task
    def bar():
        return get_run_context().result_factory

    _, task_factory = foo()
    assert task_factory.persist_result
    assert task_factory.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(task_factory.storage_block, DEFAULT_STORAGE())
    assert task_factory.storage_block_id is not None


def test_task_default_result_serializer_can_be_overriden_by_setting():
    @task(persist_result=False)
    def bar():
        return get_run_context().result_factory

    with temporary_settings({PREFECT_RESULTS_DEFAULT_SERIALIZER: "json"}):
        task_factory = bar()

    assert task_factory.serializer == JSONSerializer()


def test_task_default_persist_result_can_be_overriden_by_setting():
    @flow
    def foo():
        return get_run_context().result_factory, bar()

    @task
    def bar():
        return get_run_context().result_factory

    with temporary_settings({PREFECT_RESULTS_PERSIST_BY_DEFAULT: True}):
        _, task_factory = foo()

    assert task_factory.persist_result is True


def test_task_custom_persist_setting():
    @flow
    def foo():
        return get_run_context().result_factory, bar()

    @flow(persist_result=False)
    def bar():
        return get_run_context().result_factory

    flow_factory, task_factory = foo()
    assert flow_factory.persist_result is True
    assert task_factory.persist_result is False
    assert task_factory.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(task_factory.storage_block, DEFAULT_STORAGE())
    assert isinstance(task_factory.storage_block_id, uuid.UUID)


@pytest.mark.parametrize("toggle", [True, False])
def test_task_custom_cache_setting(toggle):
    task_factory = None

    @flow
    def foo():
        bar()
        return get_run_context().result_factory

    @task(cache_result_in_memory=toggle)
    def bar():
        nonlocal task_factory
        task_factory = get_run_context().result_factory

    flow_factory = foo()
    assert flow_factory.cache_result_in_memory is True
    assert task_factory.persist_result  # Persistence on unless explicitly turned off
    assert task_factory.cache_result_in_memory is toggle
    assert task_factory.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(task_factory.storage_block, DEFAULT_STORAGE())

    if toggle:
        assert task_factory.storage_block_id is not None
    else:
        assert isinstance(task_factory.storage_block_id, uuid.UUID)


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
    assert task_factory.storage_block_id is not None


def test_task_can_opt_out_when_persist_result_default_is_overriden_by_setting():
    @flow
    def foo():
        return get_run_context().result_factory, bar()

    @task(persist_result=False)
    def bar():
        return get_run_context().result_factory

    with temporary_settings({PREFECT_RESULTS_PERSIST_BY_DEFAULT: True}):
        _, task_factory = foo()

    assert task_factory.persist_result is False


def test_task_inherits_custom_serializer(default_persistence_off):
    @flow(result_serializer="json", persist_result=False)
    def foo():
        return get_run_context().result_factory, bar()

    @flow()
    def bar():
        return get_run_context().result_factory

    flow_factory, task_factory = foo()
    assert task_factory.persist_result is False
    assert task_factory.serializer == flow_factory.serializer
    assert_blocks_equal(task_factory.storage_block, DEFAULT_STORAGE())
    assert task_factory.storage_block_id is not None


async def test_task_inherits_custom_storage(tmp_path):
    storage = LocalFileSystem(basepath=tmp_path / "test")
    storage_id = await storage.save("test")

    @flow(result_storage="local-file-system/test")
    def foo():
        return get_run_context().result_factory, bar()

    @task
    def bar():
        return get_run_context().result_factory

    flow_factory, task_factory = foo()
    assert task_factory.persist_result
    assert task_factory.serializer == DEFAULT_SERIALIZER()
    assert task_factory.storage_block == flow_factory.storage_block
    assert task_factory.storage_block_id == storage_id


def test_task_custom_serializer(default_persistence_off):
    @flow
    def foo():
        return get_run_context().result_factory, bar()

    @flow(result_serializer="json", persist_result=False)
    def bar():
        return get_run_context().result_factory

    flow_factory, task_factory = foo()
    assert flow_factory.serializer == DEFAULT_SERIALIZER()
    assert task_factory.persist_result is False
    assert task_factory.serializer == JSONSerializer()
    assert_blocks_equal(task_factory.storage_block, DEFAULT_STORAGE())
    assert task_factory.storage_block_id is not None


async def test_task_custom_storage(tmp_path):
    storage = LocalFileSystem(basepath=tmp_path / "test")
    storage_id = await storage.save("test")

    @flow()
    def foo():
        return get_run_context().result_factory, bar()

    @flow(result_storage="local-file-system/test")
    def bar():
        return get_run_context().result_factory

    flow_factory, task_factory = foo()
    assert_blocks_equal(flow_factory.storage_block, DEFAULT_STORAGE())
    assert_blocks_equal(task_factory.storage_block, storage)
    assert task_factory.persist_result is True
    assert task_factory.serializer == DEFAULT_SERIALIZER()
    assert task_factory.storage_block_id == storage_id


async def test_task_custom_storage_by_instance_unsaved(prefect_client, tmp_path):
    storage = LocalFileSystem(basepath=tmp_path / "test")

    @flow(cache_result_in_memory=False)
    def foo():
        return get_run_context().result_factory, bar()

    @flow(result_storage=storage, cache_result_in_memory=False)
    def bar():
        return get_run_context().result_factory

    flow_factory, task_factory = foo()

    # The flow should be unchanged
    assert_blocks_equal(flow_factory.storage_block, DEFAULT_STORAGE())
    assert flow_factory.storage_block_id != task_factory.storage_block_id

    # The child should have a saved custom storage
    assert task_factory.storage_block == storage
    assert task_factory.storage_block._is_anonymous is True
    assert isinstance(task_factory.storage_block_id, uuid.UUID)

    # Check that the block is matching in the API
    storage_block_document = await prefect_client.read_block_document(
        task_factory.storage_block_id
    )
    assert_blocks_equal(
        LocalFileSystem._from_block_document(storage_block_document),
        storage,
    )

    # Other settings should not be changed
    assert task_factory.persist_result is True
    assert task_factory.serializer == DEFAULT_SERIALIZER()


async def _verify_default_storage_creation_with_persistence(
    prefect_client,
    result_factory: prefect.results.ResultFactory,
):
    # check that the default block was created
    assert result_factory.storage_block is not None
    assert_blocks_equal(result_factory.storage_block, DEFAULT_STORAGE())

    # verify storage settings are correctly set
    assert result_factory.persist_result is True
    assert isinstance(result_factory.storage_block_id, uuid.UUID)

    # verify the remote block exists
    storage_block_document = await prefect_client.read_block_document(
        result_factory.storage_block_id
    )
    # unnecessary since the read_block_document call above will fail if the
    # block doesn't exist
    assert storage_block_document


async def _verify_default_storage_creation_without_persistence(
    result_factory: prefect.results.ResultFactory,
):
    # check that the default block was created
    assert result_factory.storage_block is not None
    assert_blocks_equal(result_factory.storage_block, DEFAULT_STORAGE())

    # verify storage settings are correctly set
    assert not result_factory.storage_block._is_anonymous
    assert result_factory.persist_result is False
    assert result_factory.storage_block_id is not None


@pytest.mark.parametrize(
    "options", [{"persist_result": True}, {"cache_result_in_memory": False}]
)
async def test_default_storage_creation_for_flow_with_persistence_features(
    prefect_client, options
):
    @flow(**options)
    def foo():
        return get_run_context().result_factory

    result_factory = foo()
    await _verify_default_storage_creation_with_persistence(
        prefect_client, result_factory
    )


async def test_default_storage_creation_for_flow_without_persistence_features():
    @flow(persist_result=False)
    def foo():
        return get_run_context().result_factory

    result_factory = foo()
    await _verify_default_storage_creation_without_persistence(result_factory)


async def test_default_storage_creation_for_task_with_persistence_features(
    prefect_client,
):
    @task
    def my_task_1():
        return get_run_context().result_factory

    @flow(retries=2)
    def my_flow_1():
        return my_task_1()

    result_factory = my_flow_1()
    await _verify_default_storage_creation_with_persistence(
        prefect_client, result_factory
    )

    @task(cache_key_fn=lambda *_: "always")
    def my_task_2():
        return get_run_context().result_factory

    @flow
    def my_flow_2():
        return my_task_2()

    result_factory = my_flow_2()
    await _verify_default_storage_creation_with_persistence(
        prefect_client, result_factory
    )


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
async def test_result_factory_from_task_with_no_flow_run_context(options, expected):
    @task(**options)
    def my_task():
        pass

    assert FlowRunContext.get() is None

    result_factory = await ResultFactory.from_task(task=my_task)

    assert result_factory.persist_result == expected["persist_result"]
    assert result_factory.cache_result_in_memory == expected["cache_result_in_memory"]
    assert result_factory.serializer == expected["serializer"]
    assert_blocks_equal(result_factory.storage_block, DEFAULT_STORAGE())
