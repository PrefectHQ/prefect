import uuid

import pytest

from prefect import flow, task
from prefect.context import get_run_context
from prefect.filesystems import LocalFileSystem
from prefect.serializers import JSONSerializer, PickleSerializer
from prefect.settings import PREFECT_LOCAL_STORAGE_PATH

DEFAULT_SERIALIZER = PickleSerializer
DEFAULT_STORAGE = lambda: LocalFileSystem(basepath=PREFECT_LOCAL_STORAGE_PATH.value())


def assert_blocks_equal(
    found, expected, exclude_private: bool = True, **kwargs
) -> bool:
    assert isinstance(
        found, type(expected)
    ), f"Unexpected type {type(found).__name__}, expected {type(expected).__name__}"

    if exclude_private:
        exclude = set(kwargs.pop("exclude", set()))
        for attr, _ in found._iter():
            if attr.startswith("_"):
                exclude.add(attr)

    assert found.dict(exclude=exclude, **kwargs) == expected.dict(
        exclude=exclude, **kwargs
    )


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
    assert isinstance(task_factory.storage_block_id, uuid.UUID)


def test_task_custom_persist_setting():
    @flow
    def foo():
        return get_run_context().result_factory, bar()

    @flow(persist_result=True)
    def bar():
        return get_run_context().result_factory

    flow_factory, task_factory = foo()
    assert flow_factory.persist_result is False
    assert task_factory.persist_result is True
    assert task_factory.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(task_factory.storage_block, DEFAULT_STORAGE())
    assert isinstance(task_factory.storage_block_id, uuid.UUID)


@pytest.mark.parametrize("options", [{"retries": 3}])
def test_task_persists_result_when_flow_uses_feature(options):
    @flow(**options)
    def foo():
        return get_run_context().result_factory, bar()

    @task
    def bar():
        return get_run_context().result_factory

    flow_factory, task_factory = foo()
    assert flow_factory.persist_result is False
    assert task_factory.persist_result is True
    assert task_factory.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(task_factory.storage_block, DEFAULT_STORAGE())
    assert isinstance(task_factory.storage_block_id, uuid.UUID)


@pytest.mark.parametrize("options", [{"cache_key_fn": lambda *_: "foo"}])
def test_task_persists_result_when_task_uses_feature(options):
    @flow
    def foo():
        return get_run_context().result_factory, bar()

    @task(**options)
    def bar():
        return get_run_context().result_factory

    flow_factory, task_factory = foo()
    assert flow_factory.persist_result is False
    assert task_factory.persist_result is True
    assert task_factory.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(task_factory.storage_block, DEFAULT_STORAGE())
    assert isinstance(task_factory.storage_block_id, uuid.UUID)


def test_task_can_opt_out_of_result_persistence_when_flow_uses_feature():
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
    assert isinstance(task_factory.storage_block_id, uuid.UUID)


def test_task_inherits_custom_serializer():
    @flow(result_serializer="json")
    def foo():
        return get_run_context().result_factory, bar()

    @flow()
    def bar():
        return get_run_context().result_factory

    flow_factory, task_factory = foo()
    assert task_factory.persist_result is False
    assert task_factory.serializer == flow_factory.serializer
    assert_blocks_equal(task_factory.storage_block, DEFAULT_STORAGE())
    assert isinstance(task_factory.storage_block_id, uuid.UUID)


def test_task_inherits_custom_storage(tmp_path):
    storage = LocalFileSystem(basepath=tmp_path)
    storage_id = storage.save("test")

    @flow(result_storage="local-file-system/test")
    def foo():
        return get_run_context().result_factory, bar()

    @task
    def bar():
        return get_run_context().result_factory

    flow_factory, task_factory = foo()
    assert task_factory.persist_result is False
    assert task_factory.serializer == DEFAULT_SERIALIZER()
    assert task_factory.storage_block == flow_factory.storage_block
    assert task_factory.storage_block_id == storage_id


def test_task_custom_serializer():
    @flow
    def foo():
        return get_run_context().result_factory, bar()

    @flow(result_serializer="json")
    def bar():
        return get_run_context().result_factory

    flow_factory, task_factory = foo()
    assert flow_factory.serializer == DEFAULT_SERIALIZER()
    assert task_factory.persist_result is False
    assert task_factory.serializer == JSONSerializer()
    assert_blocks_equal(task_factory.storage_block, DEFAULT_STORAGE())
    assert isinstance(task_factory.storage_block_id, uuid.UUID)


def test_task_custom_storage(tmp_path):
    storage = LocalFileSystem(basepath=tmp_path)
    storage_id = storage.save("test")

    @flow()
    def foo():
        return get_run_context().result_factory, bar()

    @flow(result_storage="local-file-system/test")
    def bar():
        return get_run_context().result_factory

    flow_factory, task_factory = foo()
    assert_blocks_equal(flow_factory.storage_block, DEFAULT_STORAGE())
    assert task_factory.persist_result is False
    assert task_factory.serializer == DEFAULT_SERIALIZER()
    assert task_factory.storage_block == storage
    assert task_factory.storage_block_id == storage_id


async def test_task_custom_storage_by_instance_unsaved(orion_client, tmp_path):
    storage = LocalFileSystem(basepath=tmp_path)

    @flow()
    def foo():
        return get_run_context().result_factory, bar()

    @flow(result_storage=storage)
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
    storage_block_document = await orion_client.read_block_document(
        task_factory.storage_block_id
    )
    assert LocalFileSystem._from_block_document(storage_block_document) == storage

    # Other settings should not be changed
    assert task_factory.persist_result is False
    assert task_factory.serializer == DEFAULT_SERIALIZER()
