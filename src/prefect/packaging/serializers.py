import base64
import importlib
import inspect
import json
import warnings
from typing import Any

import pydantic

from prefect.packaging.base import Serializer


def to_qualified_name(obj: Any) -> str:
    return obj.__module__ + "." + obj.__qualname__


def from_qualified_name(name: str) -> Any:
    # Try importing the path directly to support "module" or "module.sub_module"
    try:
        module = importlib.import_module(name)
        return module
    except ImportError:
        # If no subitem was included raise the import error
        if "." not in name:
            raise

    # Otherwise, we'll try to load it as an attribute of a module
    mod_name, attr_name = name.rsplit(".", 1)
    module = importlib.import_module(mod_name)
    return getattr(module, attr_name)


class PickleSerializer(Serializer):
    """
    Serializes objects using the pickle protocol.

    Wraps pickles in base64 for safe transmission.
    """

    picklelib: str = "cloudpickle"
    picklelib_version: str = None

    @pydantic.validator("picklelib")
    def check_picklelib(cls, value):
        """
        Check that the given pickle library is importable and has dumps/loads methods.
        """
        try:
            pickler = from_qualified_name(value)
        except (ImportError, AttributeError) as exc:
            raise ValueError(
                f"Failed to import requested pickle library: {value!r}."
            ) from exc

        if not hasattr(pickler, "dumps"):
            raise ValueError(
                f"Pickle library at {value!r} does not have a 'dumps' method."
            )

        if not hasattr(pickler, "loads"):
            raise ValueError(
                f"Pickle library at {value!r} does not have a 'loads' method."
            )

        return value

    @pydantic.root_validator
    def check_picklelib_version(cls, values):
        """
        Infers a default value for `picklelib_version` if null or ensures it matches
        the version retrieved from the `pickelib`.
        """
        picklelib = values["picklelib"]
        picklelib_version = values.get("picklelib_version")

        pickler = from_qualified_name(picklelib)
        pickler_version = getattr(pickler, "__version__")

        if not picklelib_version:
            values["picklelib_version"] = pickler_version
        elif picklelib_version != pickler_version:
            warnings.warn(
                f"Mismatched {picklelib!r} versions. Found {pickler_version} in the "
                f"environment but {picklelib_version} was requested. This may cause "
                "the serializer to fail.",
                RuntimeWarning,
                stacklevel=3,
            )

        return values

    def dumps(self, obj: Any) -> bytes:
        pickler = from_qualified_name(self.picklelib)
        blob = pickler.dumps(obj)

        return base64.encodebytes(blob)

    def loads(self, blob: bytes) -> Any:
        pickler = from_qualified_name(self.picklelib)
        return pickler.loads(base64.decodebytes(blob))


class SourceSerializer(Serializer):
    """
    Serializes objects by retrieving their source code.

    Creates a JSON blob with keys:
        source: The source code
        symbol_name: The name of the object to extract from the source code

    Deserialization requires the code to run with `exec`.
    """

    def dumps(self, obj: Any) -> bytes:
        return json.dumps(
            {
                # TODO: This will just get the source code for the flow itself but not
                #       all of the relevant context in its file
                "source": inspect.getsource(obj),
                "symbol_name": obj.__name__,
            }
        )

    def loads(self, blob: bytes) -> Any:
        document = json.loads(blob)
        if not isinstance(document, dict) or set(document.keys()) != {
            "source",
            "symbol_name",
        }:
            raise ValueError(
                "Invalid serialized data. "
                "Expected dictionary with keys 'source' and 'symbol_name'. "
                f"Got: {document}"
            )

        exec_globals, exec_locals = {}, {}
        exec(document["source"], exec_globals, exec_locals)
        symbols = {**exec_globals, **exec_locals}

        return symbols[document["symbol_name"]]


class ImportSerializer(Serializer):
    """
    Serializes objects by storing their importable path.
    """

    def dumps(self, obj: Any) -> bytes:
        return to_qualified_name(obj).encode()

    def loads(self, blob: bytes) -> Any:
        return from_qualified_name(blob.decode())
