"""
Utilities for loading Prefect collections via setuptools entry points.

Collections are detected via the `prefect.collections` entry point group;
each entry point is a module to import when Prefect itself is imported,
typically to register Blocks or other Prefect-aware classes.

Public API is re-exported from `prefect.plugins`.
"""

import importlib
from importlib.metadata import EntryPoints, entry_points
from types import ModuleType
from typing import Any, Union

import prefect.settings

_collections: Union[None, dict[str, Union[ModuleType, Exception]]] = None


def safe_load_entrypoints(entrypoints: EntryPoints) -> dict[str, Union[Exception, Any]]:
    """
    Load entry points for a group capturing any exceptions that occur.
    """
    # TODO: `load()` claims to return module types but could return arbitrary types
    #       too. We can cast the return type if we want to be more correct. We may
    #       also want to validate the type for the group for entrypoints that have
    #       a specific type we expect.

    results: dict[str, Union[Exception, Any]] = {}

    for entrypoint in entrypoints:
        result = None
        try:
            result = entrypoint.load()
        except Exception as exc:
            result = exc

        results[entrypoint.name or entrypoint.value] = result

    return results


def load_prefect_collections(
    reload: bool = False,
) -> dict[str, Union[ModuleType, Exception]]:
    """
    Load all Prefect collections that define an entrypoint in the group
    `prefect.collections`.

    Results are cached. With `reload=True`, import and metadata caches are
    invalidated and entry points that are new or failed on a previous call are
    loaded, so packages installed or repaired after the first call are picked up.
    """
    global _collections

    if _collections is not None and not reload:
        return _collections

    if _collections is not None:
        importlib.invalidate_caches()

    collection_entrypoints: EntryPoints = entry_points(group="prefect.collections")
    if _collections is not None:
        known = {
            name
            for name, result in _collections.items()
            if not isinstance(result, Exception)
        }
        collection_entrypoints = EntryPoints(
            ep for ep in collection_entrypoints if (ep.name or ep.value) not in known
        )
    loaded: dict[str, Union[Exception, Any]] = safe_load_entrypoints(
        collection_entrypoints
    )
    collections = {**_collections, **loaded} if _collections is not None else loaded

    # TODO: Consider the utility of this once we've established this pattern.
    #       We cannot use a logger here because logging is not yet initialized.
    #       It would be nice if logging was initialized so we could log failures
    #       at least.
    for name, result in loaded.items():
        if isinstance(result, Exception):
            print(
                # TODO: Use exc_info if we have a logger
                f"Warning!  Failed to load collection {name!r}:"
                f" {type(result).__name__}: {result}"
            )
        else:
            if prefect.settings.PREFECT_DEBUG_MODE:
                print(f"Loaded collection {name!r}.")

    _collections = collections
    return collections
