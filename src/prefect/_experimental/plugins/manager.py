"""Deprecated. Use `prefect.plugins` instead."""

from prefect._internal.compatibility.deprecated_paths import deprecated_module_attrs

__all__ = ("register_hook",)  # noqa: F822 - lazily resolved by `__getattr__`

__getattr__ = deprecated_module_attrs(__name__, "prefect.plugins", __all__)
