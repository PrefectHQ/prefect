import base64
import json
from io import BytesIO
from typing import Any

import cloudpickle


__all__ = ("Serializer", "PickleSerializer", "JSONSerializer")


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
        breakpoint()
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


class PandasSerializer(Serializer):
    """A Serializer for Pandas DataFrames.

    Args:
        - file_type (str): The type you want the resulting file to be
            saved as, e.g. "csv" or "parquet". Must match a type used
            in a `DataFrame.to_` method and a `pd.read_` function.
        - read_kwargs (dict, optional): Keyword arguments to pass to the
            serialization method.
        - write_kwargs (dict, optional): Keyword arguments to pass to the
            deserialization method.
    """

    def __init__(
        self, file_type: str, read_kwargs: dict = None, write_kwargs: dict = None
    ) -> None:
        self.file_type = file_type

        # Fails fast if user specifies a format that Pandas can't deal with.
        self._get_read_method()
        self._get_write_method()

        self.read_kwargs = {} if read_kwargs is None else read_kwargs
        self.write_kwargs = {} if write_kwargs is None else write_kwargs

    def serialize(self, value: "pandas.DataFrame") -> bytes:  # noqa: F821
        """
        Serialize a Pandas DataFrame to bytes
        Args:
            value (DataFrame): the DataFrame to serialize

        Returns:
            - bytes: the serialized value
        """
        serialization_method = self._get_write_method(dataframe=value)
        buffer = BytesIO()
        serialization_method(buffer, **self.write_kwargs)
        return buffer.getvalue()

    def deserialize(self, value: bytes) -> "pandas.DataFrame":  # noqa: F821
        """
        Deserialize an object to a Pandas DataFrame

        Args:
            - value (bytes): the value to deserialize

        Returns:
            - DataFrame: the deserialized DataFrame
        """
        deserialization_method = self._get_read_method()
        buffer = BytesIO(bytes)
        deserialized_data = deserialization_method(buffer, **self.read_kwargs)
        return deserialized_data

    def __eq__(self, other: Any) -> bool:
        if type(self) == type(other):
            return (
                self.file_type == other.file_type
                and self.write_kwargs == other.write_kwargs
                and self.read_kwargs == other.read_kwargs
            )
        return False

    # _get_read_method and _get_write_method are constructed as they are both to
    # limit copy/paste but also to make it easier for potential future extension to serialization
    # methods that do not map to the "to_{}/read_{}" interface.
    def _get_read_method(self):
        import pandas as pd

        try:
            return getattr(pd, "read_{}".format(self.file_type))
        except AttributeError:
            raise ValueError(
                "Could not find deserialization methods for {}".format(self.file_type)
            )

    def _get_write_method(self, dataframe: "pandas.DataFrame" = None):  # noqa: F821
        import pandas as pd

        if dataframe is None:
            # If you just want to test if the method exists, create an empty dataframe
            dataframe = pd.DataFrame()
        try:
            return getattr(dataframe, "to_{}".format(self.file_type))
        except AttributeError:
            raise ValueError(
                "Could not find serialization methods for {}".format(self.file_type)
            )
