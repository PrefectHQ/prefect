import warnings
from typing import Any

from prefect.executors import LocalDaskExecutor as _LocalDaskExecutor
from prefect.executors import DaskExecutor as _DaskExecutor


class DaskExecutor(_DaskExecutor):
    def __new__(cls, *args: Any, **kwargs: Any) -> "DaskExecutor":
        warnings.warn(
            "prefect.engine.executors.DaskExecutor has been moved to "
            "`prefect.executors.DaskExecutor`, please update your imports",
            stacklevel=2,
        )
        return super().__new__(cls)


class LocalDaskExecutor(_LocalDaskExecutor):
    def __new__(cls, *args: Any, **kwargs: Any) -> "LocalDaskExecutor":
        warnings.warn(
            "prefect.engine.executors.LocalDaskExecutor has been moved to "
            "`prefect.executors.LocalDaskExecutor`, please update your imports",
            stacklevel=2,
        )
        return super().__new__(cls)
