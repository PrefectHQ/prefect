import importlib
from typing import Any


def import_object(name: str) -> Any:
    """Import an object given a fully-qualified name.

    Args:
        - name (string): The fully-qualified name of the object to import.

    Returns:
        - obj: The object that was imported.

    Example:

    ```python
    >>> obj = import_object("random.randint")
    >>> import random
    >>> obj == random.randint
    True
    ```
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
