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

from prefect.bundles.execute import execute_bundle, execute_bundle_from_file

warnings.warn(
    "`prefect._experimental.bundles.execute` has moved to "
    "`prefect.bundles.execute`. The old import path will be removed in a "
    "future release.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["execute_bundle", "execute_bundle_from_file"]


if __name__ == "__main__":
    import runpy

    runpy.run_module("prefect.bundles.execute", run_name="__main__")
