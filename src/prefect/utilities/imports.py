"""
Utilities for working with imports. This is especially important for a framework like Prefect,
which will need to have first-class support for a wide variety of other libraries. We want
to make sure we have good ways of working with optional / lazy dependencies so that users
aren't burdened with unecessary cruft.
"""


from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import importlib
import types
import logging
from typing import Any, List


class LazyLoader(types.ModuleType):
    """
    Lazily import a module, mainly to avoid pulling in large dependencies. `contrib`,
    and `ffmpeg` are examples of modules that are large and not always needed, and this
    allows them to only be loaded when they are used.

    This code was taken from
    https://github.com/tensorflow/tensorflow/blob/master/tensorflow/python/util/lazy_loader.py
    on July 13, 2019.
    """

    # The lint error here is incorrect.
    def __init__(
        self,
        local_name: str,
        parent_module_globals: dict,
        name: str,
        warning: str = None,
    ):  # pylint: disable=super-on-old-class
        self._local_name = local_name
        self._parent_module_globals = parent_module_globals
        self._warning = warning

        super(LazyLoader, self).__init__(name)

    def _load(self) -> types.ModuleType:
        """Load the module and insert it into the parent's globals."""
        # Import the target module and insert it into the parent's namespace
        module = importlib.import_module(self.__name__)
        self._parent_module_globals[self._local_name] = module

        # Emit a warning if one was specified
        if self._warning:
            logging.warning(self._warning)
            # Make sure to only warn once.
            self._warning = None

        # Update this object's dict so that if someone keeps a reference to the
        #   LazyLoader, lookups are efficient (__getattr__ is only called on lookups
        #   that fail).
        self.__dict__.update(module.__dict__)

        return module

    def __getattr__(self, item: str) -> Any:
        module = self._load()
        return getattr(module, item)

    def __dir__(self) -> List[str]:
        module = self._load()
        return dir(module)


def lazy_import(
    import_module: str, parent_module_globals: dict, import_as: str = None
) -> LazyLoader:
    """
    Get a reference to a lazily-loaded module.

    Args:
        - import_module (str): the module to import
        - import_as (str, optional): the name to import it as; defaults to `import_module`
        - parent_module_globals (dict): a globals dictionary that the imported module
            should be added to. This should be the result of calling `globals()` from the
            same module calling this function.

    Returns:
        - LazyLoader: a module that will lazily resolve to the requested import

    Example:

    ```
    # equivalent to `import numpy`
    numpy = lazy_import('numpy', globals())

    # equivalent to `import numpy as np`
    np = lazy_import('numpy', globals(), import_as='np', )

    # lazy import of nested modules
    lazy_docker = lazy_import('prefect.environments.execution.docker', globals(), 'lazy_docker')
    ```
    """

    if import_as is None:
        import_as = import_module

    return LazyLoader(
        local_name=import_as,
        parent_module_globals=parent_module_globals,
        name=import_module,
    )
