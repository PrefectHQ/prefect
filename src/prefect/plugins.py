"""
Utilities for loading plugins that extend Prefect's functionality.

Plugins are detected by entry point definitions in package setup files.

Currently supported entrypoints:
    - prefect.collections: Identifies this package as a Prefect collection that
        should be imported when Prefect is imported.
"""

from types import ModuleType
from typing import Dict, Union

import prefect.settings
from prefect.utilities.compat import EntryPoints, entry_points


def safe_load_entrypoints(group: str) -> Dict[str, Union[Exception, ModuleType]]:
    """
    Load entry points for a group capturing any exceptions that occur.
    """
    entrypoints: EntryPoints = entry_points(group=group)

    # TODO: `load()` claims to return module types but could return arbitrary types
    #       too. We can cast the return type if we want to be more correct. We may
    #       also want to validate the type for the group for entrypoints that have
    #       a specific type we expect.
    results = {}

    for entrypoint in entrypoints:
        result = None
        try:
            result = entrypoint.load()
        except Exception as exc:
            result = exc

        results[entrypoint.name] = result

    return results


def load_prefect_collections() -> Dict[str, ModuleType]:
    """
    Load all Prefect collections that define an entrypoint in the group
    `prefect.collections`.
    """
    collections = safe_load_entrypoints(group="prefect.collections")

    # TODO: Consider the utility of this once we've established this pattern.
    #       We cannot use a logger here because logging is not yet initialized.
    #       It would be nice if logging was initialized so we could log failures
    #       at least.
    if prefect.settings.PREFECT_TEST_MODE or prefect.settings.PREFECT_DEBUG_MODE:
        for name, result in collections.items():
            if isinstance(result, Exception):
                print(
                    # TODO: Use exc_info if we have a logger
                    f"Failed to load collection {name!r}: {type(result).__name__}: {result}"
                )
            else:
                print(f"Loaded collection {name!r}.")

    return collections
