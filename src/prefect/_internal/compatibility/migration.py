"""
This module provides a helper function to handle imports for moved or removed classes and modules.

The `handle_moved_objects` function creates a custom `__getattr__` function to intercept attribute access
on the given class or module and raise appropriate errors if it has been moved or removed.

The `MOVED_IN_V3` dictionary should be updated with any old object paths and their new locations.
"""
import sys
from typing import Any, Callable, Dict

from prefect.exceptions import PrefectImportError

# IMPORTANT FOR USAGE: When adding new modules to MOVED_IN_V3 or REMOVED_IN_V3, include the following line at the bottom of that module:
# __getattr__ = getattr_migration(__name__)
# See src/prefect/filesystems for an example

MOVED_IN_V3 = {
    "prefect.deployments.deployments:load_flow_from_flow_run": "prefect.flows:load_flow_from_flow_run",
}

REMOVED_IN_V3 = {
    "prefect.deployments.deployments:Deployment": "Use 'flow.serve()' or `prefect deploy` instead.",
    "prefect.deployments:Deployment": "Use 'flow.serve()' or `prefect deploy` instead.",
    "prefect.filesystems:GCS": "Use 'prefect_gcp' instead.",
    "prefect.filesystems:Azure": "Use 'prefect_azure' instead.",
    "prefect.filesystems:S3": "Use 'prefect_aws' instead.",
}


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
            raise AttributeError(f"'{module_name}' object has no attribute '{name}'")
        import warnings

        from pydantic._internal._validators import import_string

        import_path = f"{module_name}:{name}"

        # Check if the attribute name corresponds to a moved or removed class or module
        if import_path in MOVED_IN_V3.keys():
            new_location = MOVED_IN_V3[import_path]
            warnings.warn(f"{import_path} has been moved to {new_location}.")
            return import_string(new_location)

        if import_path in REMOVED_IN_V3.keys():
            error_message = REMOVED_IN_V3[import_path]
            raise PrefectImportError(f"{import_path} has been removed. {error_message}")

        globals: Dict[str, Any] = sys.modules[module_name].__dict__
        if name in globals:
            return globals[name]

        raise AttributeError(f"module {module_name} has no attribute {name}")

    return wrapper
