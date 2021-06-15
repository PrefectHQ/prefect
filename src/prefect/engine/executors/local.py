import warnings
from typing import Any

from prefect.executors import LocalExecutor as _LocalExecutor


class LocalExecutor(_LocalExecutor):
    def __new__(cls, *args: Any, **kwargs: Any) -> "LocalExecutor":
        warnings.warn(
            "prefect.engine.executors.LocalExecutor has been moved to "
            "`prefect.executors.LocalExecutor`, please update your imports",
            stacklevel=2,
        )
        return super().__new__(cls)
