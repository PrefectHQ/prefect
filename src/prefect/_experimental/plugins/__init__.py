"""
Deprecated. Use `prefect.plugins` instead.

The plugin system has graduated from experimental to general availability.
Imports from this path continue to work but emit a `DeprecationWarning`.
"""

from prefect._internal.compatibility.deprecated_paths import deprecated_module_attrs

__getattr__ = deprecated_module_attrs(
    __name__,
    "prefect.plugins",
    (
        "run_startup_hooks",
        "HookContext",
        "SetupResult",
        "HookSpec",
        "SetupSummary",
        "PREFECT_PLUGIN_API_VERSION",
        "register_hook",
    ),
)
