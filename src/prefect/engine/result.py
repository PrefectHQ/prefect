# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula
"""
Results represent Prefect Task inputs and outputs.  In particular, anytime a Task runs, its output
is encapsulated in a `Result` object.  This object retains information about what the data is, and how to "handle" it
if it needs to be saved / retrieved at a later time (for example, if this Task requests for its outputs to be cached).

An instantiated Result object has the following attributes:

- a `value`: the value of a Result represents a single piece of data, which can be
    in raw form or compressed into a "handled" representation such as a URI or filename pointing to
    where the raw form lives
- a `handled` boolean specifying whether this `value` has been handled or not
- a `result_handler` which holds onto the `ResultHandler` used to read /
    write the value to / from its handled representation

To distinguish between a Task which runs but does not return output from a Task which has yet to run, Prefect
also provides a `NoResult` object representing the _absence_ of computation / data.  This is in contrast to a `Result`
whose value is `None`.
"""

from abc import ABCMeta, abstractmethod
from typing import Any, Union

from prefect.engine.result_handlers import ResultHandler


class ResultInterface(metaclass=ABCMeta):
    """
    A necessary evil so that Results can store SafeResults and NoResults
    in its attributes without pickle recursion problems.
    """
    @abstractmethod
    def to_result(self) -> None
        pass

    @abstractmethod
    def store_safe_value(self) -> None
        pass


class Result(metaclass=ResultInterface):
    """
    A representation of the result of a Prefect task; this class contains information about
    the value of a task's result, a result handler specifying how to serialize or store this value securely,
    and a boolean `handled` specifying whether the result has already been handled or not.

    Args:
        - value (Any): the value of the result
        - result_handler (ResultHandler, optional): the result handler to use
            when storing / serializing this result's value; required if `handled=True`
    """

    def __init__(
        self, value: Any, result_handler: ResultHandler = None
    ):
        self.value = value
        self.safe_value = NoResult
        self.result_handler = result_handler

    def __eq__(self, other: Any) -> bool:
        if type(self) == type(other):
            assert isinstance(other, Result)  # mypy assert
            eq = True
            for attr in ["value", "safe_value", "result_handler"]:
                eq &= getattr(self, attr, object()) == getattr(other, attr, object())
            return eq
        return False

    def __repr__(self) -> str:
        return "<Result: {}>".format(repr(self.value))

    def store_safe_value(self) -> None:
        """
        Write the value of this result using the result handler (if it hasn't already been handled).
        """
        if self.safe_value == NoResult:
            assert isinstance(
                self.result_handler, ResultHandler
            ), "Result has no ResultHandler"  # mypy assert
            value = self.result_handler.write(self.value)
            self.safe_value = SafeResult(value=value, result_handler=self.result_handler)

    def to_result(self) -> "Result":
        return self


class SafeResult(metaclass=ResultInterface):
    pass


class NoResultType(metaclass=ResultInterface):
    """
    A `Result` subclass representing the _absence_ of computation / output.  A `NoResult` object
    simply returns itself for its `value`, and as the output of both `read` and `write`.
    """

    def __init__(self) -> None:
        pass

    def __eq__(self, other: Any) -> bool:
        if type(self) == type(other):
            return True
        else:
            return False

    def __repr__(self) -> str:
        return "<No result>"

    @property
    def value(self) -> "NoResultType":
        return self

    def to_result(self) -> "NoResultType":
        """
        Performs no computation and returns self.
        """
        return self

    def store_safe_value(self) -> None:
        """
        Performs no computation and returns self.
        """
        pass


NoResult = NoResultType()
