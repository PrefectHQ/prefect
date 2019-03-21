"""
Results represent Prefect Task inputs and outputs.  In particular, anytime a Task runs, its output
is encapsulated in a `Result` object.  This object retains information about what the data is, and how to "handle" it
if it needs to be saved / retrieved at a later time (for example, if this Task requests for its outputs to be cached or checkpointed).

An instantiated Result object has the following attributes:

- a `value`: the value of a Result represents a single piece of data
- a `safe_value`: this attribute maintains a reference to a `SafeResult` object
    which contains a "safe" representation of the `value`; for example, the `value` of a `SafeResult`
    might be a URI or filename pointing to where the raw data lives
- a `result_handler` which holds onto the `ResultHandler` used to read /
    write the value to / from its handled representation

To distinguish between a Task which runs but does not return output from a Task which has yet to run, Prefect
also provides a `NoResult` object representing the _absence_ of computation / data.  This is in contrast to a `Result`
whose value is `None`.
"""

from typing import Any, Union

from prefect.engine.result_handlers import ResultHandler


class ResultInterface:
    """
    A necessary evil so that Results can store SafeResults and NoResults
    in its attributes without pickle recursion problems.
    """

    def __eq__(self, other: Any) -> bool:
        if type(self) == type(other):
            eq = True
            for attr in self.__dict__:
                if attr.startswith("_"):
                    continue
                eq &= getattr(self, attr, object()) == getattr(other, attr, object())
            return eq
        return False

    def __repr__(self) -> str:
        val = self.value  # type: ignore
        return "<{type}: {val}>".format(type=type(self).__name__, val=repr(val))

    def to_result(self) -> "ResultInterface":
        """Performs no computation and returns self."""
        return self

    def store_safe_value(self) -> None:
        """Performs no computation."""
        pass


class Result(ResultInterface):
    """
    A representation of the result of a Prefect task; this class contains information about
    the value of a task's result, a result handler specifying how to serialize or store this value securely,
    and a `safe_value` attribute which holds information about the current "safe" representation of this result.

    Args:
        - value (Any): the value of the result
        - result_handler (ResultHandler, optional): the result handler to use
            when storing / serializing this result's value; required if you intend on persisting this result in some way
    """

    def __init__(self, value: Any, result_handler: ResultHandler = None):
        self.value = value
        self.safe_value = NoResult  # type: SafeResult
        self.result_handler = result_handler

    def store_safe_value(self) -> None:
        """
        Populate the `safe_value` attribute with a `SafeResult` using the result handler
        """
        if self.safe_value == NoResult:
            assert isinstance(
                self.result_handler, ResultHandler
            ), "Result has no ResultHandler"  # mypy assert
            value = self.result_handler.write(self.value)
            self.safe_value = SafeResult(
                value=value, result_handler=self.result_handler
            )


class SafeResult(ResultInterface):
    """
    A _safe_ representation of the result of a Prefect task; this class contains information about
    the serialized value of a task's result, and a result handler specifying how to deserialize this value

    Args:
        - value (Any): the safe represenation of a value
        - result_handler (ResultHandler): the result handler to use when reading this result's value
    """

    def __init__(self, value: Any, result_handler: ResultHandler):
        self.value = value
        self.result_handler = result_handler

    @property
    def safe_value(self) -> "SafeResult":
        return self

    def to_result(self) -> "ResultInterface":
        """
        Read the value of this result using the result handler and return a fully hydrated Result.
        """
        value = self.result_handler.read(self.value)
        res = Result(value=value, result_handler=self.result_handler)
        res.safe_value = self
        return res


class NoResultType(SafeResult):
    """
    A `SafeResult` subclass representing the _absence_ of computation / output.  A `NoResult` object
    simply returns itself for its `value` and its `safe_value`.
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

    def __str__(self) -> str:
        return "NoResult"

    @property
    def value(self) -> "ResultInterface":
        return self

    def to_result(self) -> "ResultInterface":
        """Performs no computation and returns self."""
        return self


NoResult = NoResultType()
