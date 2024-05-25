from typing import Any, Dict

from pydantic.v1 import Field

from .records import NOTSET, Record
from .store import RecordStore


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
    store: Dict[str, MemoryRecord] = Field(default_factory=dict)

    def read(self, key: str) -> dict:
        record = self.store.get(key, MemoryRecord(key=key))
        return record.read()

    def write(self, key: str, value: dict) -> MemoryRecord:
        self.store[key] = MemoryRecord(key=key, _cache=value)
        return self.store[key]

    def get_record(self, key: str) -> MemoryRecord:
        return self.store.get(key, MemoryRecord(key=key))
