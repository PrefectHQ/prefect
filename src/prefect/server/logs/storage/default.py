from __future__ import annotations

from collections.abc import Sequence

from prefect.server.database import provide_database_interface
from prefect.server.logs.storage import LogStorage as _LogStorage
from prefect.server.models import logs as log_models
from prefect.server.schemas.core import Log
from prefect.server.schemas.filters import LogFilter
from prefect.server.schemas.sorting import LogSort


class LogStorage(_LogStorage):
    """The built-in log storage implementation backed by the Prefect database."""

    async def write_logs(
        self,
        logs: Sequence[Log],
    ) -> None:
        """Write logs to the Prefect database using the existing log model behavior.

        Logs are split into database-safe batches, and each batch is written in its
        own transaction.

        Args:
            logs: The logs to write.
        """
        if not logs:
            return

        db = provide_database_interface()
        for batch in log_models.split_logs_into_batches(logs):
            async with db.session_context(begin_transaction=True) as session:
                await log_models.create_logs(session=session, logs=batch)

    async def read_logs(
        self,
        log_filter: LogFilter | None,
        offset: int,
        limit: int,
        sort: LogSort,
    ) -> Sequence[Log]:
        """Read logs from the Prefect database.

        Args:
            log_filter: Criteria used to select logs, or `None` to select all logs.
            offset: The number of matching logs to skip.
            limit: The maximum number of logs to return.
            sort: The order in which logs should be returned.

        Returns:
            The matching logs as server log schemas.
        """
        db = provide_database_interface()
        async with db.session_context() as session:
            result = await log_models.read_logs(
                session=session,
                log_filter=log_filter,
                offset=offset,
                limit=limit,
                sort=sort,
            )
            return [Log.model_validate(log, from_attributes=True) for log in result]

    async def delete_logs(
        self,
        log_filter: LogFilter,
    ) -> None:
        """Delete logs matching a filter from the Prefect database.

        Args:
            log_filter: Criteria identifying the logs to delete.
        """
        db = provide_database_interface()
        async with db.session_context(begin_transaction=True) as session:
            await log_models.delete_logs(
                session=session,
                log_filter=log_filter,
            )
