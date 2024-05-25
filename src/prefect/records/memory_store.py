from .records import Record, NOTSET
from .store import RecordStore
from typing import Any, Optional, Dict

if HAS_PYDANTIC_V2:
    from pydantic.v1 import Field
else:
    from pydantic import Field


class MemoryRecord(Record):
    def exists(self) -> bool:
        if self._cache is NOTSET:
            return False
        return True

    def save(self) -> None:
        pass

    def read(self) -> dict:
        if self._cache is NOTSET:
            raise FileNotFoundError("Record does not exist.")
        return self._cache

    def write(self, payload: Any) -> None:
        self._cache = payload


class MemoryStore(RecordStore):
    record_type: Record = MemoryRecord
    _store: Dict[str, MemoryRecord] = Field(default_factory=dict)

    def read(self, key: str) -> dict:
        record = self._store.get(key, MemoryRecord(key=key))
        return record.read()

    def write(self, key: str, value: dict) -> MemoryRecord:
        self._store[key] = MemoryRecord(key=key, _cache=value)
        return self._store[key]

    def get_record(self, key: str) -> MemoryRecord:
        return self._store.get(key, MemoryRecord(key=key))
