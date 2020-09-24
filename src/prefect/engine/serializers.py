import base64
import io
import json
from typing import TYPE_CHECKING, Any, Callable

import cloudpickle
import pendulum

if TYPE_CHECKING:
    import pandas as pd

__all__ = (
    "Serializer",
    "PickleSerializer",
    "JSONSerializer",
    "DateTimeSerializer",
    "PandasSerializer",
)


class Serializer:
    """
    Serializers are used by Results to handle the transformation of Python
    objects to and from bytes.

    Subclasses should implement `serialize` and `deserialize`.
    """

    def __eq__(self, other: Any) -> bool:
        return type(self) == type(other)

    def serialize(self, value: Any) -> bytes:
        """
        Serialize an object to bytes.

        Args:
            - value (Any): the value to serialize

        Returns:
            - bytes: the serialized value
        """
        raise NotImplementedError

    def deserialize(self, value: bytes) -> Any:
        """
        Deserialize an object from bytes.

        Args:
            - value (bytes): the value to deserialize

        Returns:
            - Any: the deserialized value
        """
        raise NotImplementedError


class PickleSerializer(Serializer):
    """A `Serializer` that uses cloudpickle to serialize Python objects."""

    def serialize(self, value: Any) -> bytes:
        """
        Serialize an object to bytes using cloudpickle.

        Args:
            - value (Any): the value to serialize

        Returns:
            - bytes: the serialized value
        """
        return cloudpickle.dumps(value)

    def deserialize(self, value: bytes) -> Any:
        """
        Deserialize an object from bytes using cloudpickle.

        Args:
            - value (bytes): the value to deserialize

        Returns:
            - Any: the deserialized value
        """
        try:
            return cloudpickle.loads(value)
        except Exception as exc:
            try:
                # old versions of Core encoded pickles with base64
                return cloudpickle.loads(base64.b64decode(value))
            except Exception:
                # if there's an error with the backwards-compatible step,
                # reraise the original exception
                raise exc


class JSONSerializer(Serializer):
    """A Serializer that uses JSON to serialize objects"""

    def serialize(self, value: Any) -> bytes:
        """
        Serialize an object to JSON

        Args:
            - value (Any): the value to serialize

        Returns:
            - bytes: the serialized value
        """
        return json.dumps(value).encode()

    def deserialize(self, value: bytes) -> Any:
        """
        Deserialize an object from JSON

        Args:
            - value (bytes): the value to deserialize

        Returns:
            - Any: the deserialized value
        """
        return json.loads(value)


class DateTimeSerializer(Serializer):
    """A Serializer for working with human-readable datetimes"""

    def serialize(self, value: Any) -> bytes:
        """
        Serialize a datetime to human-readable bytes

        Args:
            - value (Any): the value to serialize

        Returns:
            - bytes: the serialized value
        """
        return pendulum.instance(value).to_iso8601_string().encode()

    def deserialize(self, value: bytes) -> Any:
        """
        Deserialize an datetime from human-readable bytes

        Args:
            - value (bytes): the value to deserialize

        Returns:
            - Any: the deserialized value
        """
        return pendulum.parse(value.decode())


class PandasSerializer(Serializer):
    """A Serializer for Pandas DataFrames.

    Args:
        - file_type (str): The type you want the resulting file to be
            saved as, e.g. "csv" or "parquet". Must match a type used
            in a `DataFrame.to_` method and a `pd.read_` function.
        - deserialize_kwargs (dict, optional): Keyword arguments to pass to the
            serialization method.
        - serialize_kwargs (dict, optional): Keyword arguments to pass to the
            deserialization method.
    """

    def __init__(
        self,
        file_type: str,
        deserialize_kwargs: dict = None,
        serialize_kwargs: dict = None,
    ) -> None:
        self.file_type = file_type

        # Fails fast if user specifies a format that Pandas can't deal with.
        self._get_deserialize_method()
        self._get_serialize_method()

        self.deserialize_kwargs = (
            {} if deserialize_kwargs is None else deserialize_kwargs
        )
        self.serialize_kwargs = {} if serialize_kwargs is None else serialize_kwargs

    def serialize(self, value: "pd.DataFrame") -> bytes:  # noqa: F821
        """
        Serialize a Pandas DataFrame to bytes.

        Args:
            - value (DataFrame): the DataFrame to serialize

        Returns:
            - bytes: the serialized value
        """
        serialization_method = self._get_serialize_method(dataframe=value)
        buffer = io.BytesIO()
        try:
            serialization_method(buffer, **self.serialize_kwargs)
            return buffer.getvalue()
        except TypeError:
            # there are some weird bugs with several of the Pandas serialization
            # methods when trying to serialize to bytes directly. This is a
            # workaround. See https://github.com/pandas-dev/pandas/pull/35129
            string_buffer = io.StringIO()
            serialization_method(string_buffer, **self.serialize_kwargs)
            return string_buffer.getvalue().encode()

    def deserialize(self, value: bytes) -> "pd.DataFrame":  # noqa: F821
        """
        Deserialize an object to a Pandas DataFrame

        Args:
            - value (bytes): the value to deserialize

        Returns:
            - DataFrame: the deserialized DataFrame
        """
        deserialization_method = self._get_deserialize_method()
        buffer = io.BytesIO(value)
        deserialized_data = deserialization_method(buffer, **self.deserialize_kwargs)
        return deserialized_data

    def __eq__(self, other: Any) -> bool:
        if type(self) == type(other):
            return (
                self.file_type == other.file_type
                and self.serialize_kwargs == other.serialize_kwargs
                and self.deserialize_kwargs == other.deserialize_kwargs
            )
        return False

    # _get_read_method and _get_write_method are constructed as they are both to
    # limit copy/paste but also to make it easier for potential future extension to serialization
    # methods that do not map to the "to_{}/read_{}" interface.
    def _get_deserialize_method(self) -> Callable:
        import pandas as pd

        try:
            return getattr(pd, "read_{}".format(self.file_type))
        except AttributeError as exc:
            raise ValueError(
                "Could not find deserialization methods for {}".format(self.file_type)
            ) from exc

    def _get_serialize_method(self, dataframe: "pd.DataFrame" = None) -> Callable:
        import pandas as pd

        if dataframe is None:
            # If you just want to test if the method exists, create an empty dataframe
            dataframe = pd.DataFrame()
        try:
            return getattr(dataframe, "to_{}".format(self.file_type))
        except AttributeError as exc:
            raise ValueError(
                "Could not find serialization methods for {}".format(self.file_type)
            ) from exc
