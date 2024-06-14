class RecordStore:
    def read(self, key: str):
        raise NotImplementedError

    def write(self, key: str, value: dict):
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        return False
