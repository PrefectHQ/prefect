import base64
import json
from io import BytesIO, StringIO
from typing import Any, Dict

import cloudpickle
import pandas as pd

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


class DataFrameSerializer(Serializer):
    """
    A Serializer that uses the Pandas DataFrame API to serialize objects.

    Args:
        - format (str): the serialization format (i.e. CSV, Parquet)
        - serialize_kwargs: (Dict[str, Any]): Extra kwargs to pass to the Pandas API
        - deserialize_kwargs: (Dict[str, Any]): Extra kwargs to pass to the Pandas API
    """

    def _to_csv(df: pd.DataFrame, **kwargs) -> bytes:
        s = StringIO()
        df.to_csv(s, **kwargs)
        return bytes(s.getvalue().encode())

    def _read_csv(value: bytes, **kwargs) -> pd.DataFrame:
        b = BytesIO(value)
        return pd.read_csv(b, **kwargs)

    def _to_parquet(df: pd.DataFrame, **kwargs) -> bytes:
        b = BytesIO()
        df.to_parquet(b, **kwargs)
        return b.getvalue()

    def _read_parquet(value: bytes, **kwargs) -> pd.DataFrame:
        b = BytesIO(value)
        return pd.read_parquet(b, **kwargs)

    FORMAT_SERDES_LUT = {
        "csv": {
            "serialize": _to_csv,
            "deserialize": _read_csv,
        },
        "parquet": {
            "serialize": _to_parquet,
            "deserialize": _read_parquet,
        },
    }

    def __init__(
        self,
        format: str = "csv",
        serialize_kwargs: Dict[str, Any] = {},
        deserialize_kwargs: Dict[str, Any] = {},
    ):
        super().__init__()

        # Check that the format is in the lookup table
        if format not in self.FORMAT_SERDES_LUT:
            raise TypeError(
                f"Unsupported file format for DataFrameSerializer."
                f"Provided: {format}. Support formats: {FORMAT_SERDES_LUT.keys()}"
            )

        # Store format and kwargs
        self.format_io = self.FORMAT_SERDES_LUT[format]
        self.serialize_kwargs = serialize_kwargs
        self.deserialize_kwargs = deserialize_kwargs

    def serialize(self, value: pd.DataFrame) -> bytes:
        """
        Serialize the DataFrame to the bytes for the specified format.

        Args:
            - value (pd.DataFrame): the dataframe to serialize

        Returns:
            - bytes: the serialized value
        """
        return self.format_io["serialize"](value, **self.serialize_kwargs)


    def deserialize(self, value: bytes) -> pd.DataFrame:
        """
        Deserialize bytes to a DataFrame for the specified format.

        Args:
            - value (bytes): the value to deserialize

        Returns:
            - Any: the deserialized DataFrame
        """
        return self.format_io["deserialize"](value, **self.deserialize_kwargs)
