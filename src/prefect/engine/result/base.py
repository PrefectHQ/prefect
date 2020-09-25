"""
Results represent Prefect Task inputs and outputs.  In particular, anytime a
Task runs, its output is encapsulated in a `Result` object.  This object retains
information about what the data is, and how to "handle" it if it needs to be
saved / retrieved at a later time (for example, if this Task requests for its
outputs to be cached or checkpointed).

An instantiated Result object has the following attributes:

- a `value`: the value of a Result represents a single piece of data
- a `safe_value`: this attribute maintains a reference to a `SafeResult` object
    which contains a "safe" representation of the `value`; for example, the
    `value` of a `SafeResult` might be a URI or filename pointing to where the
    raw data lives
- a `serializer`: an object that can serialize Python objects to bytes and
  recover them later
- a `result_handler` that holds onto the `ResultHandler` used to read / write
    the value to / from its handled representation

To distinguish between a Task that runs but does not return output from a Task
that has yet to run, Prefect also provides a `NoResult` object representing the
_absence_ of computation / data.  This is in contrast to a `Result` whose value
is `None`.
"""
import copy
import pendulum
import uuid
from typing import Any, Callable, Iterable

from prefect.engine.result_handlers import ResultHandler
from prefect.engine.serializers import PickleSerializer, Serializer
from prefect.utilities import logging


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

    def to_result(self, result_handler: ResultHandler = None) -> "ResultInterface":
        """
        If no result handler provided, returns self.  If a ResultHandler is
        provided, however, it will become the new result handler for this
        result.

        Args:
            - result_handler (optional): an optional result handler to override
                the current handler

        Returns:
            - ResultInterface: a potentially new Result object
        """
        if result_handler is not None:
            self.result_handler = result_handler
        return self

    def store_safe_value(self) -> None:
        """Performs no computation."""


class Result(ResultInterface):
    """
    A representation of the result of a Prefect task; this class contains
    information about the value of a task's result, a result handler specifying
    how to serialize or store this value securely, and a `safe_value` attribute
    which holds information about the current "safe" representation of this
    result.

    Args:
        - value (Any, optional): the value of the result
        - result_handler (ResultHandler, optional): the result handler to use
            when storing / serializing this result's value; required if you intend
            on persisting this result in some way
        - validators (Iterable[Callable], optional): Iterable of validation
            functions to apply to the result to ensure it is `valid`.
        - run_validators (bool): Whether the result value should be validated.
        - location (Union[str, Callable], optional): Possibly templated location
            to be used for saving the result to the destination. If a callable
            function is provided, it should have signature `callable(**kwargs) ->
            str` and at write time all formatting kwargs will be passed and a fully
            formatted location is expected as the return value.  Can be used for
            string formatting logic that `.format(**kwargs)` doesn't support
        - serializer (Serializer): a serializer that can transform Python
            objects to bytes and recover them. The serializer is used whenever the
            `Result` is writing to or reading from storage. Defaults to
            `PickleSerializer`.
    """

    def __init__(
        self,
        value: Any = None,
        result_handler: ResultHandler = None,
        validators: Iterable[Callable] = None,
        run_validators: bool = True,
        location: str = None,
        serializer: Serializer = None,
    ):
        self.value = value
        self.safe_value = NoResult  # type: SafeResult
        self.result_handler = result_handler  # type: ignore
        self.validators = validators
        self.run_validators = run_validators
        if serializer is None:
            serializer = PickleSerializer()
        self.serializer = serializer
        if isinstance(location, (str, type(None))):
            self.location = location
            self._formatter = None
        else:
            self._formatter = location
            self.location = None
        self.logger = logging.get_logger(type(self).__name__)

    def store_safe_value(self) -> None:
        """
        Populate the `safe_value` attribute with a `SafeResult` using the result
        handler
        """
        # don't bother with `None` values
        if self.value is None:
            return
        if self.safe_value == NoResult:
            assert isinstance(
                self.result_handler, ResultHandler
            ), "Result has no ResultHandler"  # mypy assert
            value = self.result_handler.write(self.value)
            self.safe_value = SafeResult(
                value=value, result_handler=self.result_handler
            )

    def from_value(self, value: Any) -> "Result":
        """
        Create a new copy of the result object with the provided value.

        Args:
            - value (Any): the value to use

        Returns:
            - Result: a new Result instance with the given value
        """
        new = self.copy()
        new.location = None
        new.value = value
        return new

    def validate(self) -> bool:
        """
        Run any validator functions associated with this result and return whether the result
        is valid or not.  All individual validator functions must return True for this method
        to return True.  Emits a warning log if run_validators isn't true, and proceeds to run
        validation functions anyway.


        Returns:
            - bool: whether or not the Result passed all validation functions
        """
        if not self.run_validators:
            self.logger.warning(
                "A Result's validate method has been called, but its run_validators "
                "attribute is False. Prefect will not honor the validators without "
                "run_validators=True, so please change it if you expect validation "
                "to occur automatically for this Result in your pipeline."
            )

        if self.validators:
            for validation_fn in self.validators:
                is_valid = validation_fn(self)
                if not is_valid:
                    # once a validator is found to be false, this result is invalid
                    return False

        # if all validators passed or we had none, this result is valid
        return True

    def copy(self) -> "Result":
        """
        Return a copy of the current result object.
        """
        return copy.copy(self)

    @property
    def default_location(self) -> str:
        date = pendulum.now("utc").format("Y/M/D")  # type: ignore
        location = f"{date}/{uuid.uuid4()}.prefect_result"
        return location

    def format(self, **kwargs: Any) -> "Result":
        """
        Takes a set of string format key-value pairs and renders the result.location to a final
        location string

        Args:
            - **kwargs (Any): string format arguments for result.location

        Returns:
            - Result: a new result instance with the appropriately formatted location
        """
        new = self.copy()
        if isinstance(new.location, str):
            assert new.location is not None
            new.location = new.location.format(**kwargs)
        elif new._formatter is not None:
            new.location = new._formatter(**kwargs)
        else:
            new.location = new.default_location
        return new

    def exists(self, location: str, **kwargs: Any) -> bool:
        """
        Checks whether the target result exists.

        Does not validate whether the result is `valid`, only that it is present.

        Args:
            - location (str, optional): Location of the result in the specific result target.
                If provided, will check whether the provided location exists;
                otherwise, will use `self.location`
            - **kwargs (Any): string format arguments for `location`

        Returns:
            - bool: whether or not the target result exists.
        """
        raise NotImplementedError(
            "Not implemented on the base Result class - if you are seeing this error you "
            "might be trying to use features that require choosing a Result subclass; "
            "see https://docs.prefect.io/core/concepts/results.html"
        )

    def read(self, location: str) -> "Result":
        """
        Reads from the target result and returns a corresponding `Result` instance.

        Args:
            - location (str): Location of the result in the specific result target.

        Returns:
            - Any: The value saved to the result.
        """
        raise NotImplementedError(
            "Not implemented on the base Result class - if you are seeing this error you "
            "might be trying to use features that require choosing a Result subclass; "
            "see https://docs.prefect.io/core/concepts/results.html"
        )

    def write(self, value_: Any, **kwargs: Any) -> "Result":
        """
        Serialize and write the result to the target location.

        Args:
            - value_ (Any): the value to write; will then be stored as the `value` attribute
                of the returned `Result` instance
            - **kwargs (optional): if provided, will be used to format the location template
                to determine the location to write to

        Returns:
            - Result: a new result object with the appropriately formatted location destination
        """
        raise NotImplementedError(
            "Not implemented on the base Result class - if you are seeing this error you "
            "might be trying to use features that require choosing a Result subclass; "
            "see https://docs.prefect.io/core/concepts/results.html"
        )


class SafeResult(ResultInterface):
    """
    A _safe_ representation of the result of a Prefect task; this class contains information
    about the serialized value of a task's result, and a result handler specifying how to
    deserialize this value

    Args:
        - value (Any): the safe representation of a value
        - result_handler (ResultHandler): the result handler to use when reading this result's value
    """

    def __init__(self, value: Any, result_handler: ResultHandler):
        self.value = value
        self.result_handler = result_handler

    @property
    def safe_value(self) -> "SafeResult":
        return self

    def to_result(self, result_handler: ResultHandler = None) -> "ResultInterface":
        """
        Read the value of this result using the result handler and return a fully hydrated Result.
        If a new ResultHandler is provided, it will instead be used to read the underlying value
        and the `result_handler` attribute of this result will be reset accordingly.

        Args:
            - result_handler (optional): an optional result handler to override the current handler

        Returns:
            - ResultInterface: a potentially new Result object
        """
        if result_handler is not None:
            self.result_handler = result_handler
        value = self.result_handler.read(self.value)
        res = Result(value=value, result_handler=self.result_handler)
        res.safe_value = self
        return res


class NoResultType(SafeResult):
    """
    A `SafeResult` subclass representing the _absence_ of computation / output.  A `NoResult` object
    returns itself for its `value` and its `safe_value`.
    """

    def __init__(self) -> None:
        self.location = None
        super().__init__(value=None, result_handler=ResultHandler())

    def __eq__(self, other: Any) -> bool:
        if type(self) == type(other):
            return True
        else:
            return False

    def __repr__(self) -> str:
        return "<No result>"

    def __str__(self) -> str:
        return "NoResult"

    def to_result(self, result_handler: ResultHandler = None) -> "ResultInterface":
        """
        Performs no computation and returns self.

        Args:
            - result_handler (optional): a passthrough for interface compatibility
        """
        return self


NoResult = NoResultType()
