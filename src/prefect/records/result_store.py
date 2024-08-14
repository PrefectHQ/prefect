from dataclasses import dataclass
from typing import Any, Optional

import pendulum

from prefect.results import BaseResult, PersistedResult, ResultFactory
from prefect.transactions import IsolationLevel
from prefect.utilities.asyncutils import run_coro_as_sync

from .base import RecordStore, TransactionRecord


@dataclass
class ResultFactoryStore(RecordStore):
    result_factory: ResultFactory
    cache: Optional[PersistedResult] = None

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

    def read(self, key: str) -> TransactionRecord:
        if self.cache:
            return TransactionRecord(key=key, result=self.cache)
        try:
            result = PersistedResult(
                serializer_type=self.result_factory.serializer.type,
                storage_block_id=self.result_factory.storage_block_id,
                storage_key=key,
            )
            return TransactionRecord(key=key, result=result)
        except Exception:
            # this is a bit of a bandaid for functionality
            raise ValueError("Result could not be read")

    def write(self, key: str, result: Any):
        if isinstance(result, PersistedResult):
            # if the value is already a persisted result, write it
            result.write(_sync=True)
            return result
        elif isinstance(result, BaseResult):
            return result
        run_coro_as_sync(self.result_factory.create_result(obj=result, key=key))

    def supports_isolation_level(self, isolation_level: IsolationLevel) -> bool:
        return isolation_level == IsolationLevel.READ_COMMITTED
