import base64
import inspect
import json
import os.path
import runpy
import warnings
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pydantic
from typing_extensions import Literal

from prefect.packaging.base import Serializer
from prefect.utilities.dispatch import register_type
from prefect.utilities.importtools import from_qualified_name, to_qualified_name


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


@register_type
class SourceSerializer(Serializer):
    """
    Serializes objects by retrieving the source code of the module they are defined in.

    Creates a JSON blob with keys:
        source: The source code
        symbol_name: The name of the object to extract from the source code

    Deserialization requires the code to run with `exec`.
    """

    type: Literal["source"] = "source"

    def dumps(self, obj: Any) -> bytes:
        module = inspect.getmodule(obj)

        if module is None:
            raise ValueError(
                f"Cannot determine module for object: {obj!r}. "
                "Its source code cannot be found."
            )

        if not module.__file__:
            raise ValueError(
                f"Found module {module!r} without source code file while serializing "
                f"object: {obj!r}."
            )

        source = inspect.getsource(module)

        return json.dumps(
            {
                "source": source,
                "module_filename": os.path.basename(module.__file__),
                "symbol_name": obj.__name__,
            }
        )

    def loads(self, blob: bytes) -> Any:
        document = json.loads(blob)
        if not isinstance(document, dict) or set(document.keys()) != {
            "source",
            "module_filename",
            "symbol_name",
        }:
            raise ValueError(
                "Invalid serialized data. "
                "Expected dictionary with keys 'source', 'module_filename', and "
                "'symbol_name'. "
                f"Got: {document}"
            )

        with TemporaryDirectory() as tmpdir:
            temp_script = Path(tmpdir) / document["module_filename"]
            temp_script.write_text(document["source"])
            symbols = runpy.run_path(str(temp_script))

        return symbols[document["symbol_name"]]


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
