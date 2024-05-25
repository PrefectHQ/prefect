from typing import Any, Dict

from pydantic.v1 import Field

from .records import NOTSET, Record
from .store import RecordStore


class MemoryRecord(Record):
    store: "MemoryStore"

    def exists(self) -> bool:
        if self.cache is NOTSET:
            return False
        return True

    def save(self) -> None:
        self.store[self.key] = self

    def read(self) -> dict:
        if self.cache is NOTSET:
            raise FileNotFoundError("Record does not exist.")
        return self.cache

    def write(self, payload: Any, save: bool = True) -> None:
        self.cache = payload
        if save:
            self.save()


class MemoryStore(RecordStore):
    store: Dict[str, MemoryRecord] = Field(default_factory=dict)

    def read(self, key: str) -> dict:
        record = self.store.get(key, MemoryRecord(key=key, store=self))
        return record.read()

    def write(self, key: str, value: dict) -> MemoryRecord:
        self.store[key] = MemoryRecord(key=key, cache=value, store=self)
        return self.store[key]

    def get_record(self, key: str) -> MemoryRecord:
        return self.store.get(key, MemoryRecord(key=key, store=self))


MemoryRecord.update_forward_refs()
