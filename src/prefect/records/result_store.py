from dataclasses import dataclass
from typing import Any, Optional

import pendulum

from prefect._internal.compatibility import deprecated
from prefect.results import BaseResult, PersistedResult, ResultStore
from prefect.transactions import IsolationLevel
from prefect.utilities.asyncutils import run_coro_as_sync

from .base import RecordStore, TransactionRecord


@deprecated.deprecated_class(
    start_date="Sep 2024",
    end_date="Nov 2024",
    help="Use `ResultStore` directly instead.",
)
@dataclass
class ResultRecordStore(RecordStore):
    """
    A record store for result records.

    Collocates result metadata with result data.
    """

    result_store: ResultStore
    cache: Optional[PersistedResult] = None

    def exists(self, key: str) -> bool:
        try:
            record = self.read(key)
            if not record:
                return False
            result = record.result
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

    def read(self, key: str, holder: Optional[str] = None) -> TransactionRecord:
        if self.cache:
            return TransactionRecord(key=key, result=self.cache)
        try:
            result = PersistedResult(
                serializer_type=self.result_store.serializer.type,
                storage_block_id=self.result_store.result_storage_block_id,
                storage_key=key,
            )
            return TransactionRecord(key=key, result=result)
        except Exception:
            # this is a bit of a bandaid for functionality
            raise ValueError("Result could not be read")

    def write(self, key: str, result: Any, holder: Optional[str] = None) -> None:
        if isinstance(result, PersistedResult):
            # if the value is already a persisted result, write it
            result.write(_sync=True)
        elif not isinstance(result, BaseResult):
            run_coro_as_sync(self.result_store.create_result(obj=result, key=key))

    def supports_isolation_level(self, isolation_level: IsolationLevel) -> bool:
        return isolation_level == IsolationLevel.READ_COMMITTED
