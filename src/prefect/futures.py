from uuid import UUID


class PrefectFuture:
    def __init__(self, run_id: UUID, result=None, is_exception: bool = False) -> None:
        self.run_id = run_id
        self._result = result
        self.is_exception = is_exception

    def result(self):
        if self.is_exception:
            raise self._result
        return self._result
