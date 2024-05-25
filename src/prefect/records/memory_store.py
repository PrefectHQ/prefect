from pydantic.v1 import Field

from .store import RecordStore


class MemoryStore(RecordStore):
    store: dict = Field(default_factory=dict)

    def exists(self, key: str) -> bool:
        return key in self.store

    def read(self, key: str) -> dict:
        return self.store.get(key)

    def write(self, key: str, value: dict) -> None:
        self.store[key] = value
