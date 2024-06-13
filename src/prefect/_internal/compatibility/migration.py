"""
This module provides a function to handle imports for moved or removed objects in Prefect 3.0 upgrade.

The `getattr_migration` function is used to handle imports for moved or removed objects in Prefect 3.0 upgrade.
It is used in the `__getattr__` attribute of modules that have moved or removed objects.

Usage:
```python
from prefect._internal.compatibility.migration import getattr_migration

__getattr__ = getattr_migration(__name__)
```
"""

import sys
from typing import Any, Callable, Dict

from pydantic_core import PydanticCustomError

from prefect.exceptions import PrefectImportError

MOVED_IN_V3 = {
    "prefect.deployments.deployments:load_flow_from_flow_run": "prefect.flows:load_flow_from_flow_run",
    "prefect.deployments:load_flow_from_flow_run": "prefect.flows:load_flow_from_flow_run",
    "prefect.variables:get": "prefect.variables:Variable.get",
    "prefect.engine:pause_flow_run": "prefect.flow_runs:pause_flow_run",
    "prefect.engine:resume_flow_run": "prefect.flow_runs:resume_flow_run",
    "prefect.engine:suspend_flow_run": "prefect.flow_runs:suspend_flow_run",
    "prefect.engine:_in_process_pause": "prefect.flow_runs:_in_process_pause",
}

REMOVED_IN_V3 = {
    "prefect.deployments.deployments:Deployment": "Use 'flow.serve()' or `prefect deploy` instead.",
    "prefect.deployments:Deployment": "Use 'flow.serve()' or `prefect deploy` instead.",
    "prefect.filesystems:GCS": "Use 'prefect_gcp' instead.",
    "prefect.filesystems:Azure": "Use 'prefect_azure' instead.",
    "prefect.filesystems:S3": "Use 'prefect_aws' instead.",
    "prefect.engine:_out_of_process_pause": "Use 'prefect.flow_runs.pause_flow_run' instead.",
}

# IMPORTANT FOR USAGE: When adding new modules to MOVED_IN_V3 or REMOVED_IN_V3, include the following lines at the bottom of that module:
# from prefect._internal.compatibility.migration import getattr_migration
# __getattr__ = getattr_migration(__name__)
# See src/prefect/filesystems.py for an example


def import_string_class_method(new_location: str) -> Callable:
    """
    Handle moved class methods.

    `import_string` does not account for moved class methods. This function handles cases where a method has been
    moved to a class. For example, if `new_location` is 'prefect.variables:Variable.get', `import_string(new_location)`
    will raise an error because it does not handle class methods. This function will import the class and get the
    method from the class.

    Args:
        new_location (str): The new location of the method.

    Returns:
        method: The resolved method from the class.

    Raises:
        PrefectImportError: If the method is not found in the class.
    """
    from pydantic._internal._validators import import_string

    class_name, method_name = new_location.rsplit(".", 1)

    cls = import_string(class_name)
    method = getattr(cls, method_name, None)

    if method is not None and callable(method):
        return method

    raise PrefectImportError(f"Unable to import {new_location!r}")


def getattr_migration(module_name: str) -> Callable[[str], Any]:
    """
    Handle imports for moved or removed objects in Prefect 3.0 upgrade

    Args:
        module_name (str): The name of the module to handle imports for.
    """

    def wrapper(name: str) -> object:
        """
        Raise a PrefectImportError if the object is not found, moved, or removed.
        """

        if name == "__path__":
            raise AttributeError(f"{module_name!r} object has no attribute {name!r}")
        import warnings

        from pydantic._internal._validators import import_string

        import_path = f"{module_name}:{name}"

        # Check if the attribute name corresponds to a moved or removed class or module
        if import_path in MOVED_IN_V3.keys():
            new_location = MOVED_IN_V3[import_path]
            warnings.warn(
                f"{import_path!r} has been moved to {new_location!r}. Importing from {new_location!r} instead. This warning will raise an error in a future release.",
                DeprecationWarning,
                stacklevel=2,
            )
            try:
                return import_string(new_location)
            except PydanticCustomError:
                return import_string_class_method(new_location)

        if import_path in REMOVED_IN_V3.keys():
            error_message = REMOVED_IN_V3[import_path]
            raise PrefectImportError(
                f"{import_path!r} has been removed. {error_message}"
            )

        globals: Dict[str, Any] = sys.modules[module_name].__dict__
        if name in globals:
            return globals[name]

        raise AttributeError(f"module {module_name!r} has no attribute {name!r}")

    return wrapper
