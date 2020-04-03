"""
Results represent Prefect Task inputs and outputs.  In particular, anytime a Task runs, its output
is encapsulated in a `Result` object.  This object retains information about what the data is, and how to "handle" it
if it needs to be saved / retrieved at a later time (for example, if this Task requests for its outputs to be cached or checkpointed).

An instantiated Result object has the following attributes:

- a `value`: the value of a Result represents a single piece of data
- a `safe_value`: this attribute maintains a reference to a `SafeResult` object
    which contains a "safe" representation of the `value`; for example, the `value` of a `SafeResult`
    might be a URI or filename pointing to where the raw data lives
- a `result_handler` that holds onto the `ResultHandler` used to read /
    write the value to / from its handled representation

To distinguish between a Task that runs but does not return output from a Task that has yet to run, Prefect
also provides a `NoResult` object representing the _absence_ of computation / data.  This is in contrast to a `Result`
whose value is `None`.
"""
import base64
import copy
import datetime
from typing import Any, Callable, Iterable, Optional, Union

import cloudpickle

from prefect.engine.cache_validators import duration_only
from prefect.engine.result_handlers import ResultHandler
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
        If no result handler provided, returns self.  If a ResultHandler is provided, however,
        it will become the new result handler for this result.

        Args:
            - result_handler (optional): an optional result handler to override the current handler

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
    A representation of the result of a Prefect task; this class contains information about
    the value of a task's result, a result handler specifying how to serialize or store this value securely,
    and a `safe_value` attribute which holds information about the current "safe" representation of this result.

    Args:
        - value (Any, optional): the value of the result
        - result_handler (ResultHandler, optional): the result handler to use
            when storing / serializing this result's value; required if you intend on persisting this result in some way
        - validators (Iterable[Callable], optional): Iterable of validation functions to apply to
            the result to ensure it is `valid`.
        - run_validators (bool): Whether the result value should be validated.
        - cache_for (timedelta, optional): The amount of time to maintain a cache
            of this result.  Useful for situations where the containing Flow
            will be rerun multiple times, but this task doesn't need to be.
        - cache_validator (Callable, optional): Validator that will determine
            whether the cache for this result is still valid (only required if `cache_for`
            is provided; defaults to `prefect.engine.cache_validators.duration_only`)
        - filepath_template (str, optional): Template file path to be used for saving the
            result to the destination.
    """

    def __init__(
        self,
        value: Any = None,
        result_handler: ResultHandler = None,
        validators: Iterable[Callable] = None,
        run_validators: bool = True,
        cache_for: datetime.timedelta = None,
        cache_validator: Callable = None,
        filepath_template: str = None,
    ):
        self.value = value
        self.safe_value = NoResult  # type: SafeResult
        self.result_handler = result_handler  # type: ignore
        self.validators = validators
        self.run_validators = run_validators
        if cache_for is not None and cache_validator is None:
            cache_validator = duration_only
        self.cache_for = cache_for
        self.cache_validator = cache_validator
        self.filepath_template = filepath_template
        self._rendered_filepath = None  # type: Optional[str]
        self.logger = logging.get_logger(type(self).__name__)

    def store_safe_value(self) -> None:
        """
        Populate the `safe_value` attribute with a `SafeResult` using the result handler
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

    def validate(self) -> bool:
        """
        Run any validator functions associated with this result and return whether the result is valid or not.
        All individual validator functions must return True for this method to return True.
        Emits a warning log if run_validators isn't true, and proceeds to run validation functions anyway.


        Returns:
            - bool: whether or not the Result passed all validation functions
        """
        if not self.run_validators:
            self.logger.warning(
                "A Result's validate method has been called, but its run_validators attribute is False. "
                "Prefect will not honor the validators without run_validators=True, so please change it "
                "if you expect validation to occur automatically for this Result in your pipeline."
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

    def serialize(self) -> bytes:
        """
        Serializes the result value into bytes.

        Returns:
            - bytes: the serialized result value
        """
        return base64.b64encode(cloudpickle.dumps(self.value))

    @classmethod
    def deserialize(cls, serialized_value: Union[str, bytes]) -> Any:
        """
        Takes a given serialized result value and returns a deserialized value.

        Args:
            - serialized_value (str): The serialized result value

        Returns:
            - Any: the deserialized result value
        """
        return cloudpickle.loads(base64.b64decode(serialized_value))

    def format(self, **kwargs: Any) -> "Result":
        """
        Takes a set of string format key-value pairs and renders the result.filepath_template to a final filepath string

        Args:
            - **kwargs (Any): string format arguments for result.filepath_template

        Returns:
            - Any: the current result instance
        """
        new = self.copy()

        if not new.filepath_template:
            raise ValueError("No filepath_template provided")

        new._rendered_filepath = new.filepath_template.format(**kwargs)
        return new

    def exists(self) -> bool:
        """
        Checks whether the target result exists.

        Does not validate whether the result is `valid`, only that it is present.

        Returns:
            - bool: whether or not the target result exists.
        """
        raise NotImplementedError()

    def read(self, loc: str = None) -> Any:
        """
        Reads from the target result.

        Args:
            - loc (str): Location of the result in the specific result target.

        Returns:
            - Any: The value saved to the result.
        """
        raise NotImplementedError()

    def write(self) -> Any:
        """
        Serialize and write the result to the target location.

        Returns:
            - Any: Result specific metadata about the written data.
        """
        raise NotImplementedError()


class SafeResult(ResultInterface):
    """
    A _safe_ representation of the result of a Prefect task; this class contains information about
    the serialized value of a task's result, and a result handler specifying how to deserialize this value

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
