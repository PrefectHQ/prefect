from uuid import UUID


class PrefectFuture:
    def __init__(self, run_id: UUID, result=None) -> None:
        self.run_id = run_id
        self._result = result

    def result(self):
        return self._result
