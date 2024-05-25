from pydantic.v1 import BaseModel

from .records import Record


class RecordStore(BaseModel):
    record_type: Record = Record

    def init(self):
        pass

    def get_record(self, key: str) -> Record:
        return self.record_type(key=key)

    def read(self, key: str) -> Record:
        pass

    def write(self, key: str) -> Record:
        pass

    def exists(self, key: str) -> bool:
        return False
