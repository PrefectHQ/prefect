"""
Schemas for interacting with the Orion Data API.
"""

from typing import Any, Generic, Type, TypeVar

from typing_extensions import Literal

from prefect import settings
from prefect.orion.serializers import lookup_serializer
from prefect.orion.utilities.filesystem import FILE_SYSTEM_SCHEMES
from prefect.orion.utilities.schemas import PrefectBaseModel


T = TypeVar("T", bound="DataDocument")  # Generic for DataDocument class types
D = TypeVar("D", bound=Any)  # Generic for DataDocument data types


class DataDocument(PrefectBaseModel, Generic[D]):
    """
    A data document includes an encoding string and a blob of encoded data

    Subclasses can define the expected type for the blob's underlying type using the
    generic variable `D`.

    For example `DataDocument[str]` indicates that a string should be passed when
    creating the document and a string will be returned when it is decoded.
    """

    encoding: str
    blob: bytes

    # A cache for the decoded data, see `DataDocument.decode`
    _data: D
    __slots__ = ["_data"]

    @classmethod
    def encode(
        cls: Type["DataDocument"], encoding: str, data: D, **kwargs: Any
    ) -> "DataDocument[D]":
        """
        Create a new data document

        A serializer must be registered for the given `encoding`
        """
        # Dispatch encoding
        blob = lookup_serializer(encoding).dumps(data, **kwargs)

        inst = cls(blob=blob, encoding=encoding)
        inst._cache_data(data)
        return inst

    def decode(self) -> D:
        """
        Get the data from a data document

        A serializer must be registered for the document's encoding
        """
        if self.has_cached_data():
            return self._data

        # Dispatch decoding
        data = lookup_serializer(self.encoding).loads(self.blob)

        self._cache_data(data)
        return data

    def _cache_data(self, data) -> None:
        # Use object's setattr to avoid a pydantic 'field does not exist' error
        # See https://github.com/samuelcolvin/pydantic/issues/655
        object.__setattr__(self, "_data", data)

    def has_cached_data(self):
        return hasattr(self, "_data")

    def __str__(self) -> str:
        if self.has_cached_data():
            return repr(self._data)
        else:
            return repr(self)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(encoding={self.encoding!r})"

    def __rich_repr__(self):
        yield "encoding", self.encoding


class DataLocation(PrefectBaseModel):
    """Represents the location of data stored in a file"""

    name: str
    # TODO: Consider using `FILE_SYSTEM_SCHEMES` which would need to be an Enum
    scheme: Literal["file", "s3"] = "file"
    base_path: str = "/tmp"


def get_instance_data_location() -> DataLocation:
    """
    Return the current data location configured for this Orion instance
    """
    return DataLocation(
        name=settings.orion.data.name,
        base_path=settings.orion.data.base_path,
        scheme=settings.orion.data.scheme.lower(),
    )
