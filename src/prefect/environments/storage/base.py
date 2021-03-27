import warnings
from typing import Any

from prefect.storage import Storage as _Storage


class _DeprecatedStorageMixin:
    def __new__(cls, *args: Any, **kwargs: Any) -> "_DeprecatedStorageMixin":
        if cls.__module__.startswith("prefect."):
            name = cls.__name__
            warnings.warn(
                f"`prefect.environments.storage.{name}` is deprecated, please use "
                f"`prefect.storage.{name}` instead",
                stacklevel=2,
            )
        return super().__new__(cls)


class Storage(_Storage, _DeprecatedStorageMixin):
    pass
