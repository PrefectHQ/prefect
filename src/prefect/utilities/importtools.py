import importlib
import importlib.util
import inspect
import os
import runpy
import sys
from tempfile import NamedTemporaryFile
from types import ModuleType
from typing import Any, Dict, Union

import fsspec

from prefect.exceptions import ScriptError
from prefect.utilities.filesystem import filename, is_local_path, tmpchdir


def to_qualified_name(obj: Any) -> str:
    """
    Given an object, returns its fully-qualified name: a string that represents its
    Python import path.

    Args:
        obj (Any): an importable Python object

    Returns:
        str: the qualified name
    """
    return obj.__module__ + "." + obj.__qualname__


def from_qualified_name(name: str) -> Any:
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

    WARNING: The Python documentation does not recommend using runpy for this pattern.

    > Furthermore, any functions and classes defined by the executed code are not
    > guaranteed to work correctly after a runpy function has returned. If that
    > limitation is not acceptable for a given use case, importlib is likely to be a
    > more suitable choice than this module.

    The function `load_script_as_module` uses importlib instead and should be used
    instead for loading objects from scripts.

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


def load_script_as_module(path: str) -> ModuleType:
    """
    Execute a script at the given path.

    Sets the module name to `__prefect_loader__`.

    If an exception occurs during execution of the script, a
    `prefect.exceptions.ScriptError` is created to wrap the exception and raised.

    See https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly
    """
    spec = importlib.util.spec_from_file_location("__prefect_loader__", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["__prefect_loader__"] = module

    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise ScriptError(user_exc=exc, path=path) from exc

    return module


class DelayedImportErrorModule(ModuleType):
    """
    A fake module returned by `lazy_import` when the module cannot be found. When any
    of the module's attributes are accessed, we will throw a `ModuleNotFoundError`.

    Adapted from [lazy_loader][1]

    [1]: https://github.com/scientific-python/lazy_loader
    """

    def __init__(self, frame_data, help_message, *args, **kwargs):
        self.__frame_data = frame_data
        self.__help_message = (
            help_message
            or f"Import errors for this module are only reported when used."
        )
        super().__init__(*args, **kwargs)

    def __getattr__(self, attr):
        if attr in ("__class__", "__file__", "__frame_data", "__help_message"):
            super().__getattr__(attr)
        else:
            fd = self.__frame_data
            raise ModuleNotFoundError(
                f"No module named '{fd['spec']}'\n\n"
                "This module was originally imported at:\n"
                f'  File "{fd["filename"]}", line {fd["lineno"]}, in {fd["function"]}\n\n'
                f'    {"".join(fd["code_context"]).strip()}\n' + self.__help_message
            )


def lazy_import(
    name: str, error_on_import: bool = False, help_message: str = ""
) -> ModuleType:
    """
    Create a lazily-imported module to use in place of the module of the given name.
    Use this to retain module-level imports for libraries that we don't want to
    actually import until they are needed.

    Adapted from the [Python documentation][1] and [lazy_loader][2]

    [1]: https://docs.python.org/3/library/importlib.html#implementing-lazy-imports
    [2]: https://github.com/scientific-python/lazy_loader
    """

    try:
        return sys.modules[name]
    except KeyError:
        pass

    spec = importlib.util.find_spec(name)
    if spec is None:
        if error_on_import:
            raise ModuleNotFoundError(f"No module named '{name}'.\n{help_message}")
        else:
            try:
                parent = inspect.stack()[1]
                frame_data = {
                    "spec": name,
                    "filename": parent.filename,
                    "lineno": parent.lineno,
                    "function": parent.function,
                    "code_context": parent.code_context,
                }
                return DelayedImportErrorModule(
                    frame_data, help_message, "DelayedImportErrorModule"
                )
            finally:
                del parent

    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module

    loader = importlib.util.LazyLoader(spec.loader)
    loader.exec_module(module)

    return module
