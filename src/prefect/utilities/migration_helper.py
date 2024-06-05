"""
This module provides a helper function to handle imports for moved or removed classes and modules.

The `handle_moved_objects` function creates a custom `__getattr__` function to intercept attribute access
on the given class or module and raise appropriate errors if it has been moved or removed.

The `MOVED_OBJECTS` dictionary should be updated with any old object paths and their new locations.
"""
import sys


class ModuleMovedError(ImportError):
    def __init__(self, message):
        super().__init__(message)


class ModuleRemovedError(ImportError):
    def __init__(self, message):
        super().__init__(message)


# Dictionary mapping old module paths to new locations or removal messages
# Format:
# "old.module.path": ("type", "new.module.path") - indicates the class or module has been moved
# "old.module.path": ("type", "Removed: Use 'new.module.path' instead.") - indicates the class or module has been removed
MOVED_OBJECTS = {
    "prefect.filesystems.GCS": ("class", "prefect_gcp"),
    "prefect.filesystems.Azure": ("class", "Removed: Use 'prefect_azure' instead."),
}


def handle_moved_objects(module_name, moved_ojbects):
    """
    Handle imports for moved or removed modules.

    This function creates a custom __getattr__ function to intercept attribute access
    on the given class or module and raise appropriate errors if the class or module has been moved or removed.

    Args:
        module_name (str): The name of the module to handle.
        moved_objects (dict): A dictionary mapping old module paths to new locations or removal messages.

    Usage:
    Add this snippet to the top of the module that contains moved or removed modules.

    Be sure to update the `MOVED_OJBECTS` dictionary with any old module paths and their new locations.
    ```python
    from prefect.migration_helper import handle_moved_objects, handle_moved_objects

    handle_moved_objects(__name__, MOVED_OBJECTS)
    ```
    """

    def __getattr__(name):
        qualified_name = f"{module_name}.{name}"
        # Skip special attributes like __path__
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError

        # Check if the attribute name corresponds to a moved or removed class or module
        if qualified_name in moved_ojbects:
            object_type, new_location = moved_ojbects[qualified_name]
            formatted_object_type = object_type.capitalize()
            if "removed" in new_location.lower():
                raise ModuleRemovedError(
                    f"{formatted_object_type} '{qualified_name}' has been removed. {new_location.split('Removed: ')[-1]}"
                )
            else:
                raise ModuleMovedError(
                    f"{formatted_object_type} '{qualified_name}' has been moved to '{new_location}'. Please update your import."
                )
        raise AttributeError(f"'{name}' not found in '{module_name}'.")

    # Override the module's __class__ to use the custom __getattr__ function
    module = sys.modules[module_name]
    original_class = module.__class__

    class CustomModule(original_class):
        def __getattr__(self, name):
            return __getattr__(name)

    module.__class__ = CustomModule
