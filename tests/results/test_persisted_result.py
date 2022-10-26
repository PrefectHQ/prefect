import json

import pytest

from prefect.filesystems import LocalFileSystem
from prefect.results import PersistedResult, PersistedResultBlob
from prefect.serializers import JSONSerializer, PickleSerializer


@pytest.fixture
async def storage_block(tmp_path):
    block = LocalFileSystem(basepath=tmp_path)
    await block._save(is_anonymous=True)
    return block


@pytest.mark.parametrize("cache_object", [True, False])
async def test_result_reference_create_and_get(cache_object, storage_block):
    result = await PersistedResult.create(
        "test",
        storage_block_id=storage_block._block_document_id,
        storage_block=storage_block,
        serializer=JSONSerializer(),
        cache_object=cache_object,
    )
    if not cache_object:
        assert not result.has_cached_object()

    assert await result.get() == "test"

    # After retrieval, it should be cached again
    assert result.has_cached_object()


async def test_result_reference_create_uses_storage(storage_block):
    result = await PersistedResult.create(
        "test",
        storage_block_id=storage_block._block_document_id,
        storage_block=storage_block,
        serializer=JSONSerializer(),
    )

    assert result.storage_block_id == storage_block._block_document_id
    contents = await storage_block.read_path(result.storage_key)
    assert contents


async def test_result_reference_create_uses_serializer(storage_block):
    serializer = PickleSerializer(picklelib="pickle")

    result = await PersistedResult.create(
        "test",
        storage_block_id=storage_block._block_document_id,
        storage_block=storage_block,
        serializer=serializer,
    )

    assert result.serializer_type == serializer.type
    contents = await storage_block.read_path(result.storage_key)
    blob = PersistedResultBlob.parse_raw(contents)
    assert blob.serializer == serializer
    assert serializer.loads(blob.data) == "test"


async def test_result_reference_file_blob_is_json(storage_block):
    serializer = JSONSerializer(
        jsonlib="orjson", object_decoder=None, object_encoder=None
    )

    result = await PersistedResult.create(
        "test",
        storage_block_id=storage_block._block_document_id,
        storage_block=storage_block,
        serializer=serializer,
    )

    contents = await storage_block.read_path(result.storage_key)

    # Should be readable by JSON
    blob_dict = json.loads(contents)

    # Should conform to the PersistedResultBlob spec
    blob = PersistedResultBlob.parse_obj(blob_dict)

    assert blob.serializer
    assert blob.data
