"""Deprecated. Use `prefect.plugins` instead."""

from prefect._internal.compatibility.deprecated_paths import deprecated_module_attrs

__getattr__ = deprecated_module_attrs(
    __name__,
    "prefect.plugins",
    ("HookContext", "SetupResult", "HookSpec", "PREFECT_PLUGIN_API_VERSION"),
)
