import uuid

from prefect import flow
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


def test_root_flow_default_result_settings():
    @flow
    def foo():
        return get_run_context().result_factory

    result_factory = foo()
    assert result_factory.persist_result == False
    assert result_factory.serializer == DEFAULT_SERIALIZER()
    assert_blocks_equal(result_factory.storage_block, DEFAULT_STORAGE())
    assert isinstance(result_factory.storage_block_id, uuid.UUID)


def test_root_flow_custom_serializer_by_type_string():
    @flow(result_serializer="json")
    def foo():
        return get_run_context().result_factory

    result_factory = foo()
    assert result_factory.persist_result == False
    assert result_factory.serializer == JSONSerializer()
    assert_blocks_equal(result_factory.storage_block, DEFAULT_STORAGE())
    assert isinstance(result_factory.storage_block_id, uuid.UUID)


def test_root_flow_custom_serializer_by_instance():
    @flow(result_serializer=JSONSerializer(jsonlib="orjson"))
    def foo():
        return get_run_context().result_factory

    result_factory = foo()
    assert result_factory.persist_result == False
    assert result_factory.serializer == JSONSerializer(jsonlib="orjson")
    assert_blocks_equal(result_factory.storage_block, DEFAULT_STORAGE())
    assert isinstance(result_factory.storage_block_id, uuid.UUID)


def test_root_flow_custom_storage_by_slug(tmp_path):
    storage = LocalFileSystem(basepath=tmp_path)
    storage_id = storage.save("test")

    @flow(result_storage="local-file-system/test")
    def foo():
        return get_run_context().result_factory

    result_factory = foo()
    assert result_factory.persist_result == False
    assert result_factory.serializer == DEFAULT_SERIALIZER()
    assert result_factory.storage_block == storage
    assert result_factory.storage_block_id == storage_id


def test_root_flow_custom_storage_by_instance_presaved(tmp_path):
    storage = LocalFileSystem(basepath=tmp_path)
    storage_id = storage.save("test")

    @flow(result_storage=storage)
    def foo():
        return get_run_context().result_factory

    result_factory = foo()
    assert result_factory.persist_result == False
    assert result_factory.serializer == DEFAULT_SERIALIZER()
    assert result_factory.storage_block == storage
    assert result_factory.storage_block._is_anonymous is False
    assert result_factory.storage_block_id == storage_id


async def test_root_flow_custom_storage_by_instance_unsaved(orion_client, tmp_path):
    storage = LocalFileSystem(basepath=tmp_path)

    @flow(result_storage=storage)
    def foo():
        return get_run_context().result_factory

    result_factory = foo()
    assert result_factory.persist_result == False
    assert result_factory.serializer == DEFAULT_SERIALIZER()
    assert result_factory.storage_block == storage
    assert result_factory.storage_block._is_anonymous is True
    assert isinstance(result_factory.storage_block_id, uuid.UUID)

    storage_block_document = await orion_client.read_block_document(
        result_factory.storage_block_id
    )
    assert LocalFileSystem._from_block_document(storage_block_document) == storage
