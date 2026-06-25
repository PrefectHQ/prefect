"""
Compatibility shim for the legacy `prefect._experimental.bundles.execute`
entrypoint.

Existing work pool storage configurations may have stored the command
`python -m prefect._experimental.bundles.execute --key ...` before the
bundle implementation graduated to GA. This module re-exports the new
`prefect.bundles.execute` symbols and forwards `python -m` execution to
the new entrypoint, while emitting a `DeprecationWarning` so users know
to migrate to `prefect.bundles.execute`.
"""

import warnings
from typing import Any

warnings.warn(
    "`prefect._experimental.bundles.execute` has moved to "
    "`prefect.bundles.execute`. The old import path will be removed in a "
    "future release.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["execute_bundle", "execute_bundle_from_file"]  # noqa: F822


def __getattr__(name: str) -> Any:
    """Lazy-load symbols from `prefect.bundles.execute` so that running
    `python -m prefect._experimental.bundles.execute` does not put
    `prefect.bundles.execute` in `sys.modules` before the
    `runpy.run_module` forward below executes — that would trigger a
    runpy `RuntimeWarning` (and hard-fail under `PYTHONWARNINGS=error`).
    """
    if name in {"execute_bundle", "execute_bundle_from_file"}:
        from prefect.bundles.execute import execute_bundle, execute_bundle_from_file

        if name == "execute_bundle":
            return execute_bundle
        return execute_bundle_from_file
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if __name__ == "__main__":
    import runpy

    runpy.run_module("prefect.bundles.execute", run_name="__main__")
