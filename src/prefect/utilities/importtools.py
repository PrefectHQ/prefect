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
    try:
        mod_name, attr_name = name.rsplit(".", 1)
        mod = importlib.import_module(mod_name)
        return getattr(mod, attr_name)
    except ValueError:
        return importlib.import_module(name)
