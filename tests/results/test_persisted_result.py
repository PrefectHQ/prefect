import json
import time
import uuid
from unittest import mock

import pendulum
import pytest

import prefect.results
from prefect.filesystems import LocalFileSystem, WritableFileSystem
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
        blob = PersistedResultBlob(
            serializer=JSONSerializer(), data=b"42", expiration=timestamp
        )
        await storage_block.write_path(path, blob.to_bytes())

        result = PersistedResult(
            storage_block_id=storage_block._block_document_id,
            storage_key=path,
            serializer_type="json",
        )

        assert await result.get() == 42
        assert result.expiration == timestamp


async def test_write_is_idempotent(storage_block):
    result = await PersistedResult.create(
        "test-defer",
        storage_block_id=storage_block._block_document_id,
        storage_block=storage_block,
        storage_key_fn=lambda: "test-defer-path",
        serializer=JSONSerializer(),
        defer_persistence=True,
    )

    with pytest.raises(ValueError, match="does not exist"):
        await result._read_blob()

    await result.write()
    blob = await result._read_blob()
    assert blob.load() == "test-defer"

    await result.write(obj="new-object!")
    blob = await result._read_blob()
    assert blob.load() == "test-defer"


async def test_lifecycle_of_defer_persistence(storage_block):
    result = await PersistedResult.create(
        "test-defer",
        storage_block_id=storage_block._block_document_id,
        storage_block=storage_block,
        storage_key_fn=lambda: "test-defer-path",
        serializer=JSONSerializer(),
        defer_persistence=True,
    )

    assert await result.get() == "test-defer"

    with pytest.raises(ValueError, match="does not exist"):
        await result._read_blob()

    await result.write()
    blob = await result._read_blob()
    assert blob.load() == "test-defer"


@pytest.fixture
def shorter_result_retries(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(prefect.results, "RESULT_READ_RETRIES", 3)
    monkeypatch.setattr(prefect.results, "RESULT_READ_RETRY_DELAY", 0.01)


@pytest.fixture
async def a_real_result(storage_block: WritableFileSystem) -> PersistedResult:
    return await PersistedResult.create(
        "test-graceful-retry",
        storage_block_id=storage_block._block_document_id,
        storage_block=storage_block,
        storage_key_fn=lambda: "test-graceful-retry-path",
        serializer=JSONSerializer(),
        defer_persistence=True,
    )


async def test_graceful_retries_are_finite_while_retrieving_missing_results(
    shorter_result_retries: None,
    a_real_result: PersistedResult,
):
    now = time.monotonic()

    # it should raise if the result has not been written
    with pytest.raises(ValueError, match="does not exist"):
        await a_real_result._read_blob()

    # it should have taken ~3 retries for this to raise
    expected_sleep = (
        prefect.results.RESULT_READ_RETRIES * prefect.results.RESULT_READ_RETRY_DELAY
    )
    assert expected_sleep <= time.monotonic() - now <= expected_sleep * 5


async def test_graceful_retries_reraise_last_error_while_retrieving_missing_results(
    shorter_result_retries: None,
    a_real_result: PersistedResult,
):
    # if it strikes out 3 times, we should re-raise
    now = time.monotonic()
    with pytest.raises(FileNotFoundError):
        with mock.patch(
            "prefect.filesystems.LocalFileSystem.read_path",
            new=mock.AsyncMock(
                side_effect=[
                    OSError,
                    TimeoutError,
                    FileNotFoundError,
                ]
            ),
        ) as m:
            await a_real_result._read_blob()

    # the loop should have failed three times, sleeping 0.01s per error
    assert m.call_count == prefect.results.RESULT_READ_RETRIES
    expected_sleep = (
        prefect.results.RESULT_READ_RETRIES * prefect.results.RESULT_READ_RETRY_DELAY
    )
    assert expected_sleep <= time.monotonic() - now <= expected_sleep * 5


async def test_graceful_retries_eventually_succeed_while(
    shorter_result_retries: None,
    a_real_result: PersistedResult,
):
    # now write the result so it's available
    await a_real_result.write()
    expected_blob = await a_real_result._read_blob()

    # even if it misses a couple times, it will eventually return the data
    now = time.monotonic()
    with mock.patch(
        "prefect.filesystems.LocalFileSystem.read_path",
        new=mock.AsyncMock(
            side_effect=[
                FileNotFoundError,
                TimeoutError,
                expected_blob.model_dump_json().encode(),
            ]
        ),
    ) as m:
        blob = await a_real_result._read_blob()
        assert blob.load() == "test-graceful-retry"

    # the loop should have failed twice, then succeeded, sleeping 0.01s per failure
    assert m.call_count == prefect.results.RESULT_READ_RETRIES
    expected_sleep = 2 * prefect.results.RESULT_READ_RETRY_DELAY
    assert expected_sleep <= time.monotonic() - now <= expected_sleep * 5
