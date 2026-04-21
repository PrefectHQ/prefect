import pytest
from pydantic import ValidationError

from prefect._result_records import ResultRecord, ResultRecordMetadata
from prefect.filesystems import NullFileSystem
from prefect.results import ResultStore
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

    def test_result_record_metadata_tolerates_unknown_serializer_types(self):
        metadata = ResultRecordMetadata.load_bytes(
            b'{"storage_key":"my-storage-key","serializer":{"type":"custom","foo":"bar"}}'
        )

        assert metadata.serializer.type == "custom"
        assert metadata.serializer.foo == "bar"

    @pytest.mark.parametrize(
        "serializer_payload",
        [
            pytest.param(
                {"type": "pickle", "picklelib": "not_a_real_lib"},
                id="known-type-with-invalid-field-value",
            ),
            pytest.param(
                {"type": "json", "bogus_extra": "bar"},
                id="known-type-with-forbidden-extra",
            ),
        ],
    )
    def test_result_record_metadata_surfaces_invalid_known_serializer(
        self, serializer_payload: dict[str, str]
    ):
        with pytest.raises(ValidationError):
            ResultRecordMetadata.model_validate(
                {"storage_key": "my-storage-key", "serializer": serializer_payload}
            )

    async def test_from_metadata(self):
        store = ResultStore()
        result_record = store.create_result_record("The results are in...", "the-key")
        await store.apersist_result_record(result_record)

        loaded = await ResultStore._from_metadata(result_record.metadata)
        assert loaded.result == "The results are in..."

    async def test_from_metadata_with_raw_result(self):
        # set up result store to persist a raw result with no metadata
        store = ResultStore(
            metadata_storage=NullFileSystem(), serializer=JSONSerializer()
        )
        result_record = store.create_result_record("The results are in...", "the-key")
        await store.apersist_result_record(result_record)

        loaded = await ResultStore._from_metadata(result_record.metadata)
        assert loaded.result == "The results are in..."

        # assert that the raw result was persisted without metadata
        assert (
            JSONSerializer().loads(
                (PREFECT_LOCAL_STORAGE_PATH.value() / "the-key").read_bytes()
            )
            == "The results are in..."
        )
