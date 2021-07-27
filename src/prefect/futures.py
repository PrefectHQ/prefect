from uuid import UUID
from typing import Any


class _empty:
    """Marker object for distinguishing set/unset values"""


class PrefectFuture:
    empty = _empty

    def __init__(self, run_id: UUID) -> None:
        self.run_id = run_id
        self.user_exception = False
        self._result = _empty

    def result(self):
        if self._result is _empty:
            # TODO: Hang and retrieve the result instead of erroring
            raise ValueError("The result has not been set.")

        if self.user_exception:
            raise self._result
        return self._result

    def set_result(self, result: Any, user_exception: bool = False) -> None:
        if self._result is not _empty:
            raise ValueError("The result has already been set.")

        self.user_exception = user_exception
        self._result = result
