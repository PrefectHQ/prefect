import importlib

import pytest

from prefect._internal.compatibility.migration import MOVED_IN_V3, REMOVED_IN_V3
from prefect.exceptions import PrefectImportError


def import_from(dotted_path: str):
    """
    Import an object from a dotted path.

    This function dynamically imports an object (such as a class, function, or variable)
    from a specified module using a dotted path. The dotted path should be in the format
    "module.submodule:object_name", where "module.submodule" is the full module path and
    "object_name" is the name of the object to be imported from that module.

    Args:
        dotted_path (str): A string representing the module and object to import,
                           separated by a colon. For example, "path.to.module:object_name".

    Returns:
        object: The imported object specified by the dotted path.

    Raises:
        ModuleNotFoundError: If the module specified in the dotted path cannot be found.
        AttributeError: If the object specified in the dotted path does not exist
                        in the module.
        ValueError: If the dotted path is not in the correct format. This can happen
                    if the dotted path is missing the colon separator. Raising this error
                    will provide a helpful message to the developer who adds new objects to
                    MOVED_IN_V3 or REMOVED_IN_V3 without following the correct format.

    Example:
        To import the `MyClass` class from the `my_package.my_module` module,
        you would use:

        ```python
        MyClass = import_from("my_package.my_module:MyClass")
        ```

        Equivalent to:

        ```python
        from my_package.my_module import MyClass
        ```
    """
    try:
        module_path, object_name = dotted_path.rsplit(":", 1)
        module = importlib.import_module(module_path)
        return getattr(module, object_name)
    except ValueError as exc:
        if "not enough values to unpack" in str(exc):
            raise ValueError(
                "Invalid dotted path format. Did you mean 'module.submodule:object_name' instead of 'module.submodule.object_name'?"
            ) from exc
    except Exception as exc:
        raise exc


@pytest.mark.parametrize("module", MOVED_IN_V3.keys())
def test_moved_in_v3(module):
    with pytest.warns(DeprecationWarning, match=MOVED_IN_V3[module]):
        import_from(module)


@pytest.mark.parametrize("module", REMOVED_IN_V3.keys())
def test_removed_in_v3(module):
    with pytest.raises(PrefectImportError):
        import_from(module)
        assert False, f"{module} should not have been importable"
