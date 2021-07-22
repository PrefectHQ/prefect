class PrefectFuture:
    def __init__(self, run_id: str, result=None) -> None:
        self.run_id = run_id
        self._result = result

    def result(self):
        return self._result
