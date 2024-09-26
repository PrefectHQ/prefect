import pytest
from pydantic import ValidationError

from prefect.filesystems import NullFileSystem
from prefect.results import ResultRecord, ResultRecordMetadata, ResultStore
from prefect.serializers import JSONSerializer
from prefect.settings import PREFECT_LOCAL_STORAGE_PATH


class TestResultRecord:
    def test_deserialize_with_full_data(self):
        record = ResultRecord(
            result="The results are in...",
            metadata=ResultRecordMetadata(
                storage_key="my-storage-key", serializer=JSONSerializer()
            ),
        )

        serialized = record.serialize()
        deserialized = ResultRecord.deserialize(serialized)
        assert deserialized.result == "The results are in..."

    def test_deserialize_with_result_only(self):
        serialized = JSONSerializer().dumps("The results are in...")

        with pytest.raises(ValidationError):
            ResultRecord.deserialize(serialized)

        # need to pass serializer to deserialize raw result
        deserialized = ResultRecord.deserialize(
            serialized, backup_serializer=JSONSerializer()
        )
        assert deserialized.result == "The results are in..."

    async def test_from_metadata(self):
        store = ResultStore()
        result_record = store.create_result_record("The results are in...", "the-key")
        await store.apersist_result_record(result_record)

        loaded = await ResultRecord._from_metadata(result_record.metadata)
        assert loaded.result == "The results are in..."

    async def test_from_metadata_with_raw_result(self):
        # set up result store to persist a raw result with no metadata
        store = ResultStore(
            metadata_storage=NullFileSystem(), serializer=JSONSerializer()
        )
        result_record = store.create_result_record("The results are in...", "the-key")
        await store.apersist_result_record(result_record)

        loaded = await ResultRecord._from_metadata(result_record.metadata)
        assert loaded.result == "The results are in..."

        # assert that the raw result was persisted without metadata
        assert (
            JSONSerializer().loads(
                (PREFECT_LOCAL_STORAGE_PATH.value() / "the-key").read_bytes()
            )
            == "The results are in..."
        )
