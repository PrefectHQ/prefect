# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

from typing import Any, Union

from prefect.engine.result_handlers import ResultHandler


ResultType = Union["Result", "NoResult"]


class Result:
    def __init__(
        self, value: Any, handled: bool = False, result_handler: ResultHandler = None
    ):
        self.value = value
        if handled is True and result_handler is None:
            raise ValueError(
                "If value has been handled, a result_handler must be provided."
            )

        self.handled = handled
        self.result_handler = result_handler

    def write(self) -> "Result":
        if not self.handled:
            assert isinstance(
                self.result_handler, ResultHandler
            ), "Result has no ResultHandler"
            value = self.result_handler.write(self.value)
            return Result(value=value, handled=True, result_handler=self.result_handler)
        else:
            return self

    def read(self) -> "Result":
        if self.handled:
            assert isinstance(
                self.result_handler, ResultHandler
            ), "Result has no ResultHandler"
            value = self.result_handler.read(self.value)
            return Result(
                value=value, handled=False, result_handler=self.result_handler
            )
        else:
            return self


class NoResult:
    def __init__(self) -> None:
        pass
