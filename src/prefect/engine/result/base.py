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

To distinguish between a Task that runs but does not return output from a Task
that has yet to run, Prefect also provides a `NoResult` object representing the
_absence_ of computation / data.  This is in contrast to a `Result` whose value
is `None`.
"""
import copy
import pendulum
import uuid
from typing import Any

from prefect.engine.serializers import PickleSerializer, Serializer
from prefect.utilities import logging


# Subclass of `NotImplementedError` to make it easier to distinguish this error
# in consuming code
class ResultNotImplementedError(NotImplementedError):
    """Indicates a Result feature isn't implemented"""


class Result:
    """
    A representation of the result of a Prefect task; this class contains
    information about the value of a task's result, a result handler specifying
    how to serialize or store this value securely, and a `safe_value` attribute
    which holds information about the current "safe" representation of this
    result.

    Args:
        - value (Any, optional): the value of the result
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
        location: str = None,
        serializer: Serializer = None,
    ):
        self.value = value
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

        Args:
            - location (str, optional): Location of the result in the specific result target.
                If provided, will check whether the provided location exists;
                otherwise, will use `self.location`
            - **kwargs (Any): string format arguments for `location`

        Returns:
            - bool: whether or not the target result exists.
        """
        raise ResultNotImplementedError(
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
        raise ResultNotImplementedError(
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
        raise ResultNotImplementedError(
            "Not implemented on the base Result class - if you are seeing this error you "
            "might be trying to use features that require choosing a Result subclass; "
            "see https://docs.prefect.io/core/concepts/results.html"
        )


class NoResultType(Result):
    """
    Backwards compatible type so that states created by new versions of Core can be deserialized by
    old versions.
    """

    pass


NoResult = NoResultType()
