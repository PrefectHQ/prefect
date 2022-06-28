import base64
import inspect
import json
import os.path
import warnings
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pydantic
from typing_extensions import Literal

from prefect.packaging.base import Serializer
from prefect.utilities.dispatch import register_type
from prefect.utilities.importtools import (
    from_qualified_name,
    load_script_as_module,
    to_qualified_name,
)


@register_type
class PickleSerializer(Serializer):
    """
    Serializes objects using the pickle protocol.

    Wraps pickles in base64 for safe transmission.
    """

    type: Literal["pickle"] = "pickle"

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

        if not callable(getattr(pickler, "dumps", None)):
            raise ValueError(
                f"Pickle library at {value!r} does not have a 'dumps' method."
            )

        if not callable(getattr(pickler, "loads", None)):
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
        picklelib = values.get("picklelib")
        picklelib_version = values.get("picklelib_version")

        if not picklelib:
            raise ValueError("Unable to check version of unrecognized picklelib module")

        pickler = from_qualified_name(picklelib)
        pickler_version = getattr(pickler, "__version__", None)

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


@register_type
class SourceSerializer(Serializer):
    """
    Serializes objects by retrieving the source code of the module they are defined in.

    Creates a JSON blob with keys:
        source: The source code
        file_name: The name of the file the source was in
        symbol_name: The name of the object to extract from the source code

    Deserialization requires the code to run with `exec`.
    """

    type: Literal["source"] = "source"

    def dumps(self, obj: Any) -> bytes:
        module = inspect.getmodule(obj)

        if module is None:
            raise ValueError(f"Cannot determine source module for object: {obj!r}.")

        if not getattr(module, "__file__", None):
            raise ValueError(
                f"Found module {module!r} without source code file while serializing "
                f"object: {obj!r}."
            )

        source = inspect.getsource(module)

        return json.dumps(
            {
                "source": source,
                "file_name": os.path.basename(module.__file__),
                "symbol_name": obj.__name__,
            }
        ).encode()

    def loads(self, blob: bytes) -> Any:
        document = json.loads(blob)
        if not isinstance(document, dict) or set(document.keys()) != {
            "source",
            "file_name",
            "symbol_name",
        }:
            raise ValueError(
                "Invalid serialized data. "
                "Expected dictionary with keys 'source', 'file_name', and "
                "'symbol_name'. "
                f"Got: {document}"
            )

        with TemporaryDirectory() as tmpdir:
            temp_script = Path(tmpdir) / document["file_name"]
            temp_script.write_text(document["source"])
            module = load_script_as_module(str(temp_script))

        return getattr(module, document["symbol_name"])


@register_type
class ImportSerializer(Serializer):
    """
    Serializes objects by storing their importable path.
    """

    type: Literal["import"] = "import"

    def dumps(self, obj: Any) -> bytes:
        return to_qualified_name(obj).encode()

    def loads(self, blob: bytes) -> Any:
        return from_qualified_name(blob.decode())
