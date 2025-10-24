"""
The DBVacuum service. Responsible for deleting old Prefect resources past their retention period.

The retention period can be configured by changing `PREFECT_API_SERVICES_DB_VACUUM_RETENTION_DAYS`.
Resources are deleted in batches to avoid long-running transactions and table locks.
"""

from __future__ import annotations

import asyncio
import datetime
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from prefect.server.database import PrefectDBInterface, inject_db
from prefect.server.database.dependencies import db_injector
from prefect.server.services.base import LoopService
from prefect.settings.context import get_current_settings
from prefect.settings.models.server.services import (
    ServerServicesDBVacuumSettings,
    ServicesBaseSetting,
)
from prefect.types._datetime import now

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class DBVacuum(LoopService):
    """
    Deletes Prefect resources from the database older than the configured retention period.

    The resources deleted are:
    - flow runs
    - task runs
    - logs
    - artifacts
    """

    @classmethod
    def service_settings(cls) -> ServicesBaseSetting:
        return cls.settings()

    @classmethod
    def settings(cls) -> ServerServicesDBVacuumSettings:
        return get_current_settings().server.services.db_vacuum

    def __init__(
        self,
        loop_seconds: float | None = None,
        **kwargs: Any,
    ):
        """
        Args:
            loop_seconds: How often to run the cleanup (default: 3600 = 1 hour)
            retention_days: Delete runs older than this many days (default: 90)
            batch_size: Number of runs to delete per transaction (default: 500)
        """
        super().__init__(
            loop_seconds=loop_seconds or DBVacuum.settings().loop_seconds,
            **kwargs,
        )

    @inject_db
    async def delete_logs(
        self,
        db: PrefectDBInterface,
        session: AsyncSession,
    ) -> int:
        keep_going = True
        total_count = 0
        while keep_going:
            deleted_logs = await db.queries.delete_old_logs(
                session=session, limit=DBVacuum.settings().batch_size
            )
            total_count += deleted_logs
            keep_going = deleted_logs > 0

        return total_count

    @inject_db
    async def delete_artifacts(
        self,
        db: PrefectDBInterface,
        session: AsyncSession,
    ) -> int:
        keep_going = True
        total_count = 0
        while keep_going:
            deleted_artifacts = await db.queries.delete_old_artifacts(
                session=session, limit=DBVacuum.settings().batch_size
            )
            total_count += deleted_artifacts
            keep_going = deleted_artifacts > 0

        return total_count

    @inject_db
    async def delete_flow_runs(
        self,
        db: PrefectDBInterface,
        session: AsyncSession,
        before: datetime.datetime,
    ) -> tuple[int, int]:
        return await db.queries.delete_old_flow_runs(
            session=session, before=before, limit=DBVacuum.settings().batch_size
        )

    @db_injector
    async def run_once(self, db: PrefectDBInterface) -> None:
        """
        Delete old Prefect resources from the database older than the configured retention period.
        """
        cutoff_time = now("UTC") - timedelta(days=DBVacuum.settings().retention_days)

        self.logger.info(
            f"Running DB Vacuum: deleting Prefect resources older than {DBVacuum.settings().retention_days} days (before {cutoff_time.isoformat()})."
        )

        async with db.session_context(begin_transaction=False) as session:
            # The deletion is performed as follows. First, all top level flow runs (parent_task_id=null) are deleted.
            # This will cascade delete child tasks (and thus orphaning any sub-flows).
            # Secondly, all associated logs are deleted, which will no longer have an associated flow run.
            # Finally, all associated artifacts are deleted, which will no longer have an associated flow run.
            # Subsequent runs will delete the now task-less flow runs, thus eventually deleting all nested flow runs
            # and tasks of a flow run.
            deleted_flow_runs, deleted_task_runs = await self.delete_flow_runs(
                db=db, session=session, before=cutoff_time
            )
            deleted_logs = await self.delete_logs(db=db, session=session)
            deleted_artifacts = await self.delete_artifacts(db=db, session=session)

        self.logger.info(
            f"Finished running DB Vacuum: deleted {deleted_flow_runs} flow runs, {deleted_task_runs} task runs, {deleted_logs} logs, {deleted_artifacts} artifacts."
        )


if __name__ == "__main__":
    asyncio.run(
        DBVacuum(
            handle_signals=True,
        ).start()
    )
