import uuid
import json

import pendulum
import pytest

from prefect.filesystems import LocalFileSystem
from prefect.results import DEFAULT_STORAGE_KEY_FN, PersistedResult, PersistedResultBlob
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
        storage_key_fn=DEFAULT_STORAGE_KEY_FN,
        serializer=JSONSerializer(),
        cache_object=cache_object,
    )
    if not cache_object:
        assert not result.has_cached_object()

    assert await result.get() == "test"

    # Only cached after retrieval if enabled during initialization
    assert result.has_cached_object() == cache_object


@pytest.mark.parametrize("cache_object", [True, False])
async def test_result_literal_populates_default_artifact_metadata(
    cache_object, storage_block
):
    result = await PersistedResult.create(
        "test",
        storage_block_id=storage_block._block_document_id,
        storage_block=storage_block,
        storage_key_fn=DEFAULT_STORAGE_KEY_FN,
        serializer=JSONSerializer(),
        cache_object=cache_object,
    )
    assert result.artifact_type == "result"
    assert isinstance(
        result.artifact_description, str
    ), "the artifact description should be populated, the form is block-specific"


async def test_result_reference_create_uses_storage(storage_block):
    result = await PersistedResult.create(
        "test",
        storage_block_id=storage_block._block_document_id,
        storage_block=storage_block,
        storage_key_fn=DEFAULT_STORAGE_KEY_FN,
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
        storage_key_fn=DEFAULT_STORAGE_KEY_FN,
        serializer=serializer,
    )

    assert result.serializer_type == serializer.type
    contents = await storage_block.read_path(result.storage_key)
    blob = PersistedResultBlob.model_validate_json(contents)
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
        storage_key_fn=DEFAULT_STORAGE_KEY_FN,
        serializer=serializer,
    )

    contents = await storage_block.read_path(result.storage_key)

    # Should be readable by JSON
    blob_dict = json.loads(contents)

    # Should conform to the PersistedResultBlob spec
    blob = PersistedResultBlob.model_validate(blob_dict)

    assert blob.serializer
    assert blob.data


async def test_result_reference_create_uses_storage_key_fn(storage_block):
    result = await PersistedResult.create(
        "test",
        storage_block_id=storage_block._block_document_id,
        storage_block=storage_block,
        storage_key_fn=lambda: "test",
        serializer=JSONSerializer(),
    )

    assert result.storage_key == "test"
    contents = await storage_block.read_path("test")
    assert contents


async def test_init_doesnt_error_when_doesnt_exist(storage_block):
    path = uuid.uuid4().hex

    result = PersistedResult(
        storage_block_id=storage_block._block_document_id,
        storage_key=path,
        serializer_type="json",
    )

    with pytest.raises(ValueError, match="does not exist"):
        await result.get()

    blob = PersistedResultBlob(serializer=JSONSerializer(), data=b"38")
    await storage_block.write_path(path, blob.to_bytes())
    assert await result.get() == 38


class TestCreatedAtField:
    async def test_defaults_when_created(self, storage_block):
        result = await PersistedResult.create(
            "test-value",
            storage_block_id=storage_block._block_document_id,
            storage_block=storage_block,
            storage_key_fn=DEFAULT_STORAGE_KEY_FN,
            serializer=JSONSerializer(),
        )

        assert isinstance(result.created_at, pendulum.DateTime)
        assert (
            pendulum.now("utc").subtract(seconds=10)
            <= result.created_at
            <= pendulum.now("utc")
        )

    async def test_defaults_when_loaded(self, storage_block):
        path = uuid.uuid4().hex
        timestamp = pendulum.now("utc").subtract(days=100)
        blob = PersistedResultBlob(
            serializer=JSONSerializer(), data=b"42", created_at=timestamp
        )
        await storage_block.write_path(path, blob.to_bytes())

        result = PersistedResult(
            storage_block_id=storage_block._block_document_id,
            storage_key=path,
            serializer_type="json",
        )

        assert await result.get() == 42
        assert result.created_at == timestamp
