# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

from typing import Any, Union

from prefect.engine.result_handlers import ResultHandler


class Result:
    """
    A representation of the result of a Prefect task; this class contains information about
    the value of a task's result, a result handler specifying how to serialize or store this value securely,
    and a boolean `handled` specifying whether the result has already been handled or not.

    Args:
        - value (Any): the value of the result
        - handled (boolean, optional): whether this value has already been
            handled or not; defaults to `False`
        - result_handler (ResultHandler, optional): the result handler to use
            when storing / serializing this result's value; required if `handled=True`

    Raises:
        - ValueError: if a handled value is provided without a result handler
    """

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

    def __eq__(self, other: Any) -> bool:
        if type(self) == type(other):
            assert isinstance(other, Result)  # mypy assert
            eq = True
            for attr in ["value", "handled", "result_handler"]:
                eq &= getattr(self, attr, object()) == getattr(other, attr, object())
            return eq
        return False

    def __repr__(self) -> str:
        return "Result: {}".format(repr(self.value))

    def write(self) -> "Result":
        """
        Write the value of this result using the result handler (if it hasn't already been handled).

        Returns:
            - Result: a new result containing the written representation of the value
        """
        if not self.handled:
            assert isinstance(
                self.result_handler, ResultHandler
            ), "Result has no ResultHandler"  # mypy assert
            value = self.result_handler.write(self.value)
            return Result(value=value, handled=True, result_handler=self.result_handler)
        else:
            return self

    def read(self) -> "Result":
        """
        Read the value of this result using the result handler.

        Returns:
            - Result: a new result containing the new representation of the value
        """
        if self.handled:
            assert isinstance(
                self.result_handler, ResultHandler
            ), "Result has no ResultHandler"  # mypy assert
            value = self.result_handler.read(self.value)
            return Result(
                value=value, handled=False, result_handler=self.result_handler
            )
        else:
            return self


class NoResultType:
    def __eq__(self, other: Any) -> bool:
        if type(self) == type(other):
            return True
        else:
            return False

    @property
    def value(self) -> "NoResultType":
        return self


NoResult = NoResultType()
