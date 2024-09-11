import json
import uuid

import pendulum
import pytest

from prefect.filesystems import LocalFileSystem
from prefect.results import (
    DEFAULT_STORAGE_KEY_FN,
    PersistedResult,
    ResultRecord,
    ResultRecordMetadata,
)
from prefect.serializers import JSONSerializer, PickleSerializer


@pytest.fixture(autouse=True)
def ignore_deprecation(ignore_prefect_deprecation_warnings):
    """Remove this test file when deprecation warning period is over"""
    pass


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
    await result.write()
    if not cache_object:
        assert not result.has_cached_object()

    assert await result.get() == "test"

    # Only cached after retrieval if enabled during initialization
    assert result.has_cached_object() == cache_object


async def test_result_reference_create_uses_storage(storage_block):
    result = await PersistedResult.create(
        "test",
        storage_block_id=storage_block._block_document_id,
        storage_block=storage_block,
        storage_key_fn=DEFAULT_STORAGE_KEY_FN,
        serializer=JSONSerializer(),
    )
    await result.write()

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
    await result.write()

    assert result.serializer_type == serializer.type
    contents = await storage_block.read_path(result.storage_key)
    record = ResultRecord.deserialize(contents)
    assert record.serializer == serializer
    assert record.result == "test"


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
    await result.write()

    contents = await storage_block.read_path(result.storage_key)

    # Should be readable by JSON
    json.loads(contents)

    # Should conform to the ResultRecord spec
    blob = ResultRecord.deserialize(contents)

    assert blob.serializer
    assert blob.result


async def test_result_reference_create_uses_storage_key_fn(storage_block):
    result = await PersistedResult.create(
        "test",
        storage_block_id=storage_block._block_document_id,
        storage_block=storage_block,
        storage_key_fn=lambda: "test",
        serializer=JSONSerializer(),
    )
    await result.write()

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

    record = ResultRecord(
        metadata=ResultRecordMetadata(serializer=JSONSerializer()), result=b"38"
    )
    await storage_block.write_path(path, record.serialize())
    assert await result.get() == b"38"


class TestExpirationField:
    async def test_expiration_at_init_defaults_to_none(self, storage_block):
        """
        Setting a default on create but not init ensures that loading results with no
        expiration set will not have an expiration.
        """
        result = PersistedResult(
            storage_block_id=storage_block._block_document_id,
            storage_key="my-path",
            serializer_type="json",
        )

        assert result.expiration is None

    async def test_expiration_at_create_defaults_to_none(self, storage_block):
        result = await PersistedResult.create(
            "test-value",
            storage_block_id=storage_block._block_document_id,
            storage_block=storage_block,
            storage_key_fn=DEFAULT_STORAGE_KEY_FN,
            serializer=JSONSerializer(),
        )
        assert result.expiration is None

    async def test_setting_expiration_at_create(self, storage_block):
        expires = pendulum.now("utc").add(days=1)

        result = await PersistedResult.create(
            "test-value",
            storage_block_id=storage_block._block_document_id,
            storage_block=storage_block,
            storage_key_fn=DEFAULT_STORAGE_KEY_FN,
            serializer=JSONSerializer(),
            expiration=expires,
        )
        assert result.expiration == expires

    async def test_expiration_when_loaded(self, storage_block):
        path = uuid.uuid4().hex
        timestamp = pendulum.now("utc").subtract(days=100)
        record = ResultRecord(
            metadata=ResultRecordMetadata(
                serializer=JSONSerializer(), expiration=timestamp
            ),
            result=b"42",
        )
        await storage_block.write_path(path, record.serialize())

        result = PersistedResult(
            storage_block_id=storage_block._block_document_id,
            storage_key=path,
            serializer_type="json",
        )

        assert await result.get() == b"42"
        assert result.expiration == timestamp


async def test_write_is_idempotent(storage_block):
    result = await PersistedResult.create(
        "test-defer",
        storage_block_id=storage_block._block_document_id,
        storage_block=storage_block,
        storage_key_fn=lambda: "test-defer-path",
        serializer=JSONSerializer(),
    )

    with pytest.raises(ValueError, match="does not exist"):
        await result.get(ignore_cache=True)

    await result.write()
    obj = await result.get()
    assert obj == "test-defer"

    await result.write(obj="new-object!")
    obj = await result.get()
    assert obj == "test-defer"


async def test_lifecycle_of_deferred_persistence(storage_block):
    result = await PersistedResult.create(
        "test-defer",
        storage_block_id=storage_block._block_document_id,
        storage_block=storage_block,
        storage_key_fn=lambda: "test-defer-path",
        serializer=JSONSerializer(),
    )

    assert await result.get() == "test-defer"

    with pytest.raises(ValueError, match="does not exist"):
        await result.get(ignore_cache=True)

    await result.write()
    obj = await result.get()
    assert obj == "test-defer"


async def test_read_old_format_into_result_record():
    old_blob = {
        "serializer": {
            "type": "pickle",
            "picklelib": "cloudpickle",
            "picklelib_version": None,
        },
        "data": "gAVLCS4=\n",
        "prefect_version": "2.20.1",
        "expiration": None,
    }
    record = ResultRecord.deserialize(json.dumps(old_blob).encode())
    assert record.result == 9
    assert record.metadata.serializer == PickleSerializer(picklelib="cloudpickle")
    assert record.metadata.prefect_version == "2.20.1"
    assert record.metadata.expiration is None
