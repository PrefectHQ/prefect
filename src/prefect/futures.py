from uuid import UUID
from typing import Any


class PrefectFuture:
    def __init__(self, run_id: UUID) -> None:
        self.run_id = run_id
        self.user_exception = False

    def result(self):
        if self.user_exception:
            raise self._result
        return self._result

    def set_result(self, result: Any, user_exception: bool = False) -> None:
        self.user_exception = user_exception
        self._result = result
