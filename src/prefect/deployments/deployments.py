from .._internal.compatibility.migration import getattr_migration

__getattr__ = getattr_migration(__name__)
