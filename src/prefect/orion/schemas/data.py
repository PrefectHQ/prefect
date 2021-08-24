from typing import Any, Generic, Tuple, Type, TypeVar

import fsspec
import base64
from typing_extensions import Literal

from prefect import settings
from prefect.orion.utilities.schemas import PrefectBaseModel

# File storage schemes for `DataLocation` and `FileSystemDataDocument`
FileSystemScheme = Literal["s3", "file"]

T = TypeVar("T", bound="DataDocument")  # Generic for DataDocument class types
D = TypeVar("D", bound=Any)  # Generic for DataDocument data types


class Base64String(PrefectBaseModel):
    data: str

    def to_bytes(self) -> bytes:
        return base64.decodebytes(self.data.encode())

    @classmethod
    def from_bytes(cls, raw_data: bytes) -> "Base64String":
        return Base64String(data=base64.encodebytes(raw_data).decode())


class DataLocation(PrefectBaseModel):
    name: str
    scheme: FileSystemScheme = "file"
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


def create_datadoc(encoding: str, data: D) -> "DataDocument[D]":
    """
    Create an encoded data document given an object
    """
    return get_datadoc_subclass(encoding).create(data)


def get_datadoc_subclass(encoding: str) -> Type["DataDocument"]:
    encoding_to_cls = {
        subclass.supported_encodings(): subclass
        for subclass in DataDocument.__subclasses__()
    }

    for cls_encodings, cls in encoding_to_cls.items():
        if encoding in cls_encodings:
            return cls

    raise ValueError(f"Unknown document encoding {encoding!r}")


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

    # A cache for the decoded data, see `DataDocument.read`
    _data_cache: D
    __slots__ = ["_data_cache"]

    @classmethod
    def create(cls: Type[T], data: D, encoding: str = None) -> T:
        if encoding is None:
            encoding = cls.__fields__["encoding"].get_default()

        if encoding not in cls.supported_encodings():
            raise ValueError(f"Unsupported encoding for {cls.__name__!r}: {encoding!r}")

        # Get an encoded blob
        blob = cls.encode(data)

        inst = cls(blob=blob, encoding=encoding)
        inst._cache_data(data)
        return inst

    def to_subtype(self) -> "DataDocument[D]":
        # Check if already a subtype
        if not type(self) == DataDocument:
            return self

        # Otherwise, lookup the subtype based on the encoding and return an instance
        subtype = get_datadoc_subclass(self.encoding)
        return subtype.parse_obj(self)

    def read(self) -> D:
        if hasattr(self, "_data_cache"):
            return self._data_cache

        data = self.decode(self.blob)
        self._cache_data(data)
        return data

    def _cache_data(self, data) -> None:
        # Use object's setattr to avoid a pydantic 'field does not exist' error
        # See https://github.com/samuelcolvin/pydantic/issues/655
        object.__setattr__(self, "_data_cache", data)

    @classmethod
    def supported_encodings(cls) -> Tuple[str, ...]:
        """
        Determine which encodings are supported by a data document subtype
        by examining the `Literal` type annotation on `encoding`
        """
        annotation = cls.__fields__["encoding"].type_

        # Only supports `Literal` right now
        if hasattr(annotation, "__origin__") and annotation.__origin__ == Literal:
            return annotation.__args__

        return tuple()

    @staticmethod
    def decode(blob: bytes) -> D:
        raise NotImplementedError

    @staticmethod
    def encode(data: D) -> bytes:
        raise NotImplementedError


class FileSystemDataDocument(DataDocument[Tuple[str, bytes]]):
    """
    Persists bytes to a file system and creates a data document with the path to the
    data
    """

    encoding: FileSystemScheme

    @staticmethod
    def decode(blob: bytes) -> Tuple[str, bytes]:
        path = blob.decode()
        # Read the file bytes
        return (path, FileSystemDataDocument.read_blob(path))

    @staticmethod
    def encode(data: Tuple[str, bytes]) -> bytes:
        path, file_blob = data

        # Write the bytes to `path`
        FileSystemDataDocument.write_blob(file_blob, path)

        # Save the path as bytes to conform to the spec
        return path.encode()

    @staticmethod
    def write_blob(blob: bytes, path: str) -> bool:
        with fsspec.open(path, mode="wb") as fp:
            fp.write(blob)

        return True

    @staticmethod
    def read_blob(path: str) -> bytes:
        with fsspec.open(path, mode="rb") as fp:
            blob = fp.read()

        return blob


class OrionDataDocument(DataDocument[FileSystemDataDocument]):
    encoding: Literal["orion"] = "orion"

    @staticmethod
    def decode(blob: bytes) -> FileSystemDataDocument:
        return FileSystemDataDocument.parse_raw(blob)

    @staticmethod
    def encode(data: FileSystemDataDocument) -> bytes:
        return data.json().encode()
