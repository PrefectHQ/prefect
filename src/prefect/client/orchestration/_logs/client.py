from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable, Union

from prefect.client.orchestration.base import BaseAsyncClient, BaseClient

if TYPE_CHECKING:
    from prefect.client.schemas.actions import (
        LogCreate,
    )
    from prefect.client.schemas.filters import (
        LogFilter,
    )
    from prefect.client.schemas.objects import (
        Log,
    )
    from prefect.client.schemas.sorting import LogSort


class LogClient(BaseClient):
    def create_logs(self, logs: Iterable[Union["LogCreate", dict[str, Any]]]) -> None:
        """
        Create logs for a flow or task run
        """
        from prefect.client.schemas.actions import LogCreate

        serialized_logs = [
            log.model_dump(mode="json") if isinstance(log, LogCreate) else log
            for log in logs
        ]
        self.request("POST", "/logs/", json=serialized_logs)

    def read_logs(
        self,
        log_filter: "LogFilter | None" = None,
        limit: int | None = None,
        offset: int | None = None,
        sort: "LogSort | None" = None,
    ) -> list["Log"]:
        """
        Read flow and task run logs.
        """
        from prefect.client.schemas.sorting import LogSort

        body: dict[str, Any] = {
            "logs": log_filter.model_dump(mode="json") if log_filter else None,
            "limit": limit,
            "offset": offset,
            "sort": sort or LogSort.TIMESTAMP_ASC,
        }
        response = self.request("POST", "/logs/filter", json=body)
        from prefect.client.schemas.objects import Log

        return Log.model_validate_list(response.json())


class LogAsyncClient(BaseAsyncClient):
    async def create_logs(
        self, logs: Iterable[Union["LogCreate", dict[str, Any]]]
    ) -> None:
        """
        Create logs for a flow or task run

        Args:
            logs: An iterable of `LogCreate` objects or already json-compatible dicts
        """
        from prefect.client.schemas.actions import LogCreate

        serialized_logs = [
            log.model_dump(mode="json") if isinstance(log, LogCreate) else log
            for log in logs
        ]
        await self.request("POST", "/logs/", json=serialized_logs)

    async def read_logs(
        self,
        log_filter: "LogFilter | None" = None,
        limit: int | None = None,
        offset: int | None = None,
        sort: "LogSort | None" = None,
    ) -> list[Log]:
        """
        Read flow and task run logs.
        """
        from prefect.client.schemas.sorting import LogSort

        body: dict[str, Any] = {
            "logs": log_filter.model_dump(mode="json") if log_filter else None,
            "limit": limit,
            "offset": offset,
            "sort": sort or LogSort.TIMESTAMP_ASC,
        }

        response = await self.request("POST", "/logs/filter", json=body)
        from prefect.client.schemas.objects import Log

        return Log.model_validate_list(response.json())
