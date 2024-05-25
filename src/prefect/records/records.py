from contextlib import contextmanager
from typing import Any

from pydantic.v1 import BaseModel


class NOTSET:
    """
    Sentinel value for unset caches on records.
    """


class Record(BaseModel):
    key: str = None
    cache: dict = NOTSET

    def exists(self) -> bool:
        return False

    def save(self) -> None:
        raise NotImplementedError

    def read(self) -> Any:
        raise NotImplementedError

    def write(self, payload: dict) -> None:
        # raise NotImplementedError
        pass

    @contextmanager
    def lock(self, timeout: int = None, expires_in: int = None) -> bool:
        try:
            yield self.take_lock(timeout=timeout, expires_in=expires_in)
        finally:
            self.release_lock()

    def take_lock(self, timeout: int = None, expires_in: int = None) -> bool:
        raise NotImplementedError

    def release_lock(self) -> bool:
        raise NotImplementedError
