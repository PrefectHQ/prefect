from dataclasses import dataclass
from typing import Any

from prefect.exceptions import ObjectNotFound
from prefect.results import BaseResult, PersistedResult, ResultFactory
from prefect.utilities.asyncutils import run_coro_as_sync

from .store import RecordStore


@dataclass
class ResultFactoryStore(RecordStore):
    result_factory: ResultFactory
    cache: PersistedResult = None

    def exists(self, key: str) -> bool:
        try:
            result = self.read(key)
            result.get(_sync=True)
            self.cache = result
            return True
        except (ObjectNotFound, ValueError):
            return False

    def read(self, key: str) -> BaseResult:
        if self.cache:
            return self.cache
        try:
            result = PersistedResult(
                serializer_type=self.result_factory.serializer.type,
                storage_block_id=self.result_factory.storage_block_id,
                storage_key=key,
            )
            return result
        except Exception:
            # this is a bit of a bandaid for functionality
            raise ValueError("Result could not be read")

    def write(self, key: str, value: Any) -> BaseResult:
        if isinstance(value, BaseResult):
            return value
        return run_coro_as_sync(self.result_factory.create_result(obj=value, key=key))
