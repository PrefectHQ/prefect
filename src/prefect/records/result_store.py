from dataclasses import dataclass
from typing import Any

import pendulum

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
            if result.expiration:
                # if the result has an expiration,
                # check if it is still in the future
                exists = result.expiration > pendulum.now("utc")
            else:
                exists = True
            self.cache = result
            return exists
        except Exception:
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
        if isinstance(value, PersistedResult):
            # if the value is already a persisted result, write it
            value.write(_sync=True)
            return value
        elif isinstance(value, BaseResult):
            return value
        return run_coro_as_sync(self.result_factory.create_result(obj=value, key=key))
