"""Deprecated. Use `prefect.plugins` instead."""

from prefect._internal.compatibility.deprecated_paths import deprecated_module_attrs

__all__ = ("HookContext", "SetupResult", "HookSpec", "PREFECT_PLUGIN_API_VERSION")  # noqa: F822 - names lazily resolved by `__getattr__`

__getattr__ = deprecated_module_attrs(__name__, "prefect.plugins", __all__)
