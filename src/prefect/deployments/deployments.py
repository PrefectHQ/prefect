from typing import Any, Callable

from prefect._internal.compatibility.migration import getattr_migration

__getattr__: Callable[[str], Any] = getattr_migration(__name__)
