from prefect.results import BaseResult, PersistedResult, ResultFactory

from .store import RecordStore


class ResultFactoryStore(RecordStore):
    result_factory: ResultFactory

    def exists(self, key: str) -> bool:
        return False

    def read(self, key: str) -> BaseResult:
        result = PersistedResult(
            serializer_type=self.result_factory.serializer.type,
            storage_block_id=self.result_factory.storage_block_id,
            storage_key=key,
        )
        return result

    def write(self, key: str, value: dict) -> BaseResult:
        return self.result_factory.create_result(obj=value, key=key)
