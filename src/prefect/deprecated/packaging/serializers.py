"""
DEPRECATION WARNING:
This module is deprecated as of March 2024 and will not be available after September 2024.
"""

import base64
import inspect
import json
import os.path
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, List

from prefect._internal.compatibility.deprecated import deprecated_class
from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect._internal.schemas.validators import (
    validate_picklelib,
    validate_picklelib_and_modules,
    validate_picklelib_version,
)

if HAS_PYDANTIC_V2:
    import pydantic.v1 as pydantic
else:
    import pydantic

from typing_extensions import Literal

from prefect.deprecated.packaging.base import Serializer
from prefect.utilities.importtools import (
    from_qualified_name,
    load_script_as_module,
    to_qualified_name,
)


@deprecated_class(start_date="Mar 2024")
class PickleSerializer(Serializer):
    """
    DEPRECATION WARNING:

    This class is deprecated as of version March 2024 and will not be available after September 2024.

    Serializes objects using the pickle protocol.

    If using cloudpickle, you may specify a list of 'pickle_modules'. These modules will
    be serialized by value instead of by reference, which means they do not have to be
    installed in the runtime location. This is especially useful for serializing objects
    that rely on local packages.

    Wraps pickles in base64 for safe transmission.
    """

    type: Literal["pickle"] = "pickle"

    picklelib: str = "cloudpickle"
    picklelib_version: str = None

    pickle_modules: List[str] = pydantic.Field(default_factory=list)

    @pydantic.validator("picklelib")
    def check_picklelib(cls, value):
        return validate_picklelib(value)

    @pydantic.root_validator
    def check_picklelib_and_modules(cls, values):
        return validate_picklelib_and_modules(values)

    @pydantic.root_validator
    def check_picklelib_version(cls, values):
        return validate_picklelib_version(values)

    def dumps(self, obj: Any) -> bytes:
        pickler = from_qualified_name(self.picklelib)

        for module in self.pickle_modules:
            pickler.register_pickle_by_value(from_qualified_name(module))

        blob = pickler.dumps(obj)

        for module in self.pickle_modules:
            # Restore the pickler settings
            pickler.unregister_pickle_by_value(from_qualified_name(module))

        return base64.encodebytes(blob)

    def loads(self, blob: bytes) -> Any:
        pickler = from_qualified_name(self.picklelib)
        return pickler.loads(base64.decodebytes(blob))


@deprecated_class(start_date="Mar 2024")
class SourceSerializer(Serializer):
    """
    DEPRECATION WARNING:

    This class is deprecated as of version March 2024 and will not be available after September 2024.

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


@deprecated_class(start_date="Mar 2024")
class ImportSerializer(Serializer):
    """
    DEPRECATION WARNING:

    This class is deprecated as of version March 2024 and will not be available after September 2024.

    Serializes objects by storing their importable path.
    """

    type: Literal["import"] = "import"

    def dumps(self, obj: Any) -> bytes:
        return to_qualified_name(obj).encode()

    def loads(self, blob: bytes) -> Any:
        return from_qualified_name(blob.decode())
