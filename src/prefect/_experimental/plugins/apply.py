"""Deprecated. The contents of this module were never public API."""

from prefect._internal.compatibility.deprecated_paths import deprecated_module_attrs

__getattr__ = deprecated_module_attrs(__name__, "prefect.plugins", ())
