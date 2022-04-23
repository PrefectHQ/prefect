import importlib
import os
import runpy
from tempfile import NamedTemporaryFile
from typing import Any, Dict, Union

import fsspec

from prefect.exceptions import ScriptError
from prefect.utilities.filesystem import filename, is_local_path, tmpchdir


def import_object(name: str) -> Any:
    """
    Import an object given a fully-qualified name.

    Args:
        name: The fully-qualified name of the object to import.

    Returns:
        the imported object

    Example:
        >>> obj = import_object("random.randint")
        >>> import random
        >>> obj == random.randint
        True
    """

    # Try importing it first so we support "module" or "module.sub_module"
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


def objects_from_script(path: str, text: Union[str, bytes] = None) -> Dict[str, Any]:
    """
    Run a python script and return all the global variables

    Supports remote paths by copying to a local temporary file.

    Args:
        path: The path to the script to run
        text: Optionally, the text of the script. Skips loading the contents if given.

    Returns:
        A dictionary mapping variable name to value

    Raises:
        ScriptError: if the script raises an exception during execution
    """

    def run_script(run_path: str):
        # Cast to an absolute path before changing directories to ensure relative paths
        # are not broken
        abs_run_path = os.path.abspath(run_path)
        with tmpchdir(run_path):
            try:
                return runpy.run_path(abs_run_path)
            except Exception as exc:
                raise ScriptError(user_exc=exc, path=path) from exc

    if text:
        with NamedTemporaryFile(
            mode="wt" if isinstance(text, str) else "wb",
            prefix=f"run-{filename(path)}",
            suffix=".py",
        ) as tmpfile:
            tmpfile.write(text)
            tmpfile.flush()
            return run_script(tmpfile.name)

    else:
        if not is_local_path(path):
            # Remote paths need to be local to run
            with fsspec.open(path) as f:
                contents = f.read()
            return objects_from_script(path, contents)
        else:
            return run_script(path)
