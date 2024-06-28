"""
2024-06-27: This surfaces an actionable error message for moved or removed objects in Prefect 3.0 upgrade.
"""
from prefect._internal.compatibility.migration import getattr_migration

__getattr__ = getattr_migration(__name__)
