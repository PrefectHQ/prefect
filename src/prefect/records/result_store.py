from dataclasses import dataclass, field
from typing import Any, Optional

import pendulum

from prefect.context import FlowRunContext, TaskRunContext
from prefect.results import (
    BaseResult,
    PersistedResult,
    ResultFactory,
    get_default_result_storage,
)
from prefect.transactions import IsolationLevel
from prefect.utilities.asyncutils import run_coro_as_sync

from .base import RecordStore, TransactionRecord


def create_default_result_factory() -> ResultFactory:
    flow_run_context = FlowRunContext.get()
    task_run_context = TaskRunContext.get()
    existing_factory = getattr(task_run_context, "result_factory", None) or getattr(
        flow_run_context, "result_factory", None
    )

    new_factory: ResultFactory
    if existing_factory and existing_factory.storage_block_id:
        new_factory = existing_factory.model_copy(
            update={
                "persist_result": True,
            }
        )
    else:
        default_storage = get_default_result_storage(_sync=True)
        if existing_factory:
            new_factory = existing_factory.model_copy(
                update={
                    "persist_result": True,
                    "storage_block": default_storage,
                    "storage_block_id": default_storage._block_document_id,
                }
            )
        else:
            new_factory = run_coro_as_sync(
                ResultFactory.default_factory(
                    persist_result=True,
                    result_storage=default_storage,
                )
            )

    return new_factory


@dataclass
class ResultFactoryStore(RecordStore):
    result_factory: ResultFactory = field(default_factory=create_default_result_factory)
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
                serializer_type=self.result_factory.serializer.type,
                storage_block_id=self.result_factory.storage_block_id,
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
            run_coro_as_sync(self.result_factory.create_result(obj=result, key=key))

    def supports_isolation_level(self, isolation_level: IsolationLevel) -> bool:
        return isolation_level == IsolationLevel.READ_COMMITTED
