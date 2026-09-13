from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
import importlib
import inspect
from typing import Any, ClassVar, cast

from typing_extensions import Self

from prefect.server.schemas.core import Log
from prefect.server.schemas.filters import LogFilter
from prefect.server.schemas.sorting import LogSort
from prefect.settings.context import get_current_settings


class LogStorage(ABC):
    """Interface for server-side log storage implementations.

    Implementations own the backend-specific details of writing, querying, and deleting logs.
    """

    _instance: ClassVar[LogStorage | None] = None

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cast(Self, cls._instance)

    @abstractmethod
    async def write_logs(
        self,
        logs: Sequence[Log],
    ) -> None:
        """Store a collection of logs.

        Implementations are responsible for backend-specific batching and
        transactions. Log preparation and live-log publication are handled by the
        server write path.

        Args:
            logs: The logs to store.
        """
        raise NotImplementedError

    @abstractmethod
    async def read_logs(
        self,
        log_filter: LogFilter | None,
        offset: int,
        limit: int,
        sort: LogSort,
    ) -> Sequence[Log]:
        """Read logs matching the supplied filter and pagination options.

        Args:
            log_filter: Criteria used to select logs, or `None` to select all logs.
            offset: The number of matching logs to skip.
            limit: The maximum number of logs to return.
            sort: The order in which logs should be returned.

        Returns:
            The matching logs in the requested order.
        """
        raise NotImplementedError

    @abstractmethod
    async def delete_logs(
        self,
        log_filter: LogFilter,
    ) -> None:
        """Delete logs matching the supplied filter.

        Args:
            log_filter: Criteria identifying the logs to delete.
        """
        raise NotImplementedError


def get_log_storage() -> LogStorage:
    """Return the configured server log storage implementation.

    The module selected by `server.logs.storage` must export a concrete `LogStorage`.
    The base class ensures that one instance is reused for each concrete storage class during the process lifetime.

    Returns:
        The shared instance of the configured log storage implementation.

    Raises:
        ValueError: If the configured module does not export a concrete `LogStorage`
            implementation.
    """
    storage_module_path = get_current_settings().server.logs.storage
    log_storage_module = importlib.import_module(storage_module_path)
    log_storage_type = getattr(log_storage_module, "LogStorage", None)

    if (
        not isinstance(log_storage_type, type)
        or not issubclass(log_storage_type, LogStorage)
        or inspect.isabstract(log_storage_type)
    ):
        raise ValueError(
            f"The module {storage_module_path} does not contain a concrete "
            "LogStorage implementation"
        )

    return log_storage_type()
