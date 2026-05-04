"""
Deprecated. Use `prefect.plugins` instead.

The plugin system has graduated from experimental to general availability.
Imports from this path continue to work but emit a `DeprecationWarning`.
"""

from prefect._internal.compatibility.deprecated_paths import deprecated_module_attrs

# Names are lazily resolved by `__getattr__` below; ruff's F822 (undefined
# name in __all__) doesn't fit this deprecation-shim pattern.
# fmt: off
__all__ = ("run_startup_hooks", "HookContext", "SetupResult", "HookSpec", "SetupSummary", "PREFECT_PLUGIN_API_VERSION", "register_hook")  # noqa: F822
# fmt: on

__getattr__ = deprecated_module_attrs(__name__, "prefect.plugins", __all__)
