"""
This module provides a helper function to handle imports for moved or removed modules.

The `handle_moved_modules` function creates a custom `__getattr__` function to intercept attribute access
on the given module and raise appropriate errors if the module has been moved or removed.

The `MOVED_MODULES` dictionary should be updated with any old module paths and their new locations.
"""
import sys


class ModuleMovedError(ImportError):
    def __init__(self, message):
        super().__init__(message)


# Dictionary mapping old module paths to new locations or removal messages
# Format:
# "old.module.path": "new.module.path" - indicates the module has moved to a new location
# "old.module.path": "removed: use new.module.path instead" - indicates the module has been removed, with a suggested alternative
MOVED_MODULES = {
    "prefect.filesystems.GCS": "Removed: Use 'prefect_gcp' instead",
    "prefect.filesystems.Azure": "Removed: Use 'prefect_azure' instead",
}


def handle_moved_modules(module_name, moved_modules):
    """
    Handle imports for moved or removed modules.

    This function creates a custom __getattr__ function to intercept attribute access
    on the given module and raise appropriate errors if the module has been moved or removed.

    Args:
        module_name (str): The name of the module to handle.
        moved_modules (dict): A dictionary mapping old module paths to new locations or removal messages.

    Usage:
    Add this snippet to the top of the module that contains moved or removed modules.

    Be sure to update the `MOVED_MODULES` dictionary with any old module paths and their new locations.
    ```python
    from prefect.migration_helper import handle_moved_modules, MOVED_MODULES

    handle_moved_modules(__name__, MOVED_MODULES)
    ```
    """

    def __getattr__(name):
        qualified_name = f"{module_name}.{name}"
        # Skip special attributes like __path__
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError

        # Check if the attribute name corresponds to a moved or removed module
        if qualified_name in moved_modules:
            new_location = moved_modules[qualified_name]
            if "removed" in new_location.lower():
                raise ModuleMovedError(
                    f"Module '{qualified_name}' has been removed. {new_location.split('Removed: ')[-1]}"
                )
            else:
                raise ModuleMovedError(
                    f"Module '{qualified_name}' has been moved to '{new_location}'. Please update your import."
                )
        raise AttributeError(f"Module '{name}' not found in '{module_name}'.")

    # Override the module's __class__ to use the custom __getattr__ function
    module = sys.modules[module_name]
    original_class = module.__class__

    class CustomModule(original_class):
        def __getattr__(self, name):
            return __getattr__(name)

    module.__class__ = CustomModule
