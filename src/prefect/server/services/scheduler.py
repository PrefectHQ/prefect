"""
The Scheduler service.

This service schedules flow runs from deployments with active schedules.
"""

from __future__ import annotations

import datetime
import logging
from datetime import timedelta
from typing import Any, Sequence
from uuid import UUID

import sqlalchemy as sa
from docket import Perpetual
from sqlalchemy.ext.asyncio import AsyncSession

import prefect.server.models as models
from prefect.logging import get_logger
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.schemas.states import StateType
from prefect.server.services.perpetual_services import perpetual_service
from prefect.settings.context import get_current_settings
from prefect.types._datetime import now
from prefect.utilities.collections import batched_iterable

logger: logging.Logger = get_logger(__name__)


class TryAgain(Exception):
    """Internal control-flow exception used to retry the Scheduler's main loop"""


def _get_select_deployments_to_schedule_query(
    db: PrefectDBInterface,
    deployment_batch_size: int,
    min_runs: int,
    min_scheduled_time: datetime.timedelta,
) -> sa.Select[tuple[UUID]]:
    """
    Returns a sqlalchemy query for selecting deployments to schedule.

    The query gets the IDs of any deployments where ANY active schedule has:

        - EITHER:
            - fewer than `min_runs` auto-scheduled runs for that schedule
            - OR the max scheduled time for that schedule is less than
              `min_scheduled_time` in the future

    This per-schedule check ensures that high-frequency schedules get
    re-evaluated even when other schedules on the same deployment still
    have runs far in the future.

    Each schedule's runs are identified via the ``created_by`` JSON column
    which stores ``{"id": "<schedule_id>", "type": "SCHEDULE", ...}`` on
    every auto-scheduled flow run.  An expression index on
    ``(created_by->>'id')`` keeps these correlated subqueries fast.
    """
    right_now = now("UTC")

    # Use type_coerce to bypass the Pydantic TypeDecorator so SQLAlchemy
    # emits a bare ``created_by->>'id'`` (Postgres) / ``json_extract(created_by, '$.id')``
    # (SQLite) without an extra CAST wrapper.  This is required for
    # PostgreSQL to match the expression index on ``(created_by->>'id')``.
    schedule_id_match = sa.type_coerce(db.FlowRun.created_by, sa.JSON)[
        "id"
    ].as_string() == sa.cast(db.DeploymentSchedule.id, sa.String)

    per_schedule_run_count = (
        sa.select(sa.func.count())
        .select_from(db.FlowRun)
        .where(
            db.FlowRun.deployment_id == db.DeploymentSchedule.deployment_id,
            db.FlowRun.state_type == StateType.SCHEDULED,
            db.FlowRun.next_scheduled_start_time >= right_now,
            db.FlowRun.auto_scheduled.is_(True),
            schedule_id_match,
        )
        .correlate(db.DeploymentSchedule)
        .scalar_subquery()
    )

    per_schedule_max_time = (
        sa.select(sa.func.max(db.FlowRun.next_scheduled_start_time))
        .select_from(db.FlowRun)
        .where(
            db.FlowRun.deployment_id == db.DeploymentSchedule.deployment_id,
            db.FlowRun.state_type == StateType.SCHEDULED,
            db.FlowRun.next_scheduled_start_time >= right_now,
            db.FlowRun.auto_scheduled.is_(True),
            schedule_id_match,
        )
        .correlate(db.DeploymentSchedule)
        .scalar_subquery()
    )

    any_schedule_needs_runs = (
        sa.select(sa.literal(1))
        .select_from(db.DeploymentSchedule)
        .where(
            db.DeploymentSchedule.deployment_id == db.Deployment.id,
            db.DeploymentSchedule.active.is_(True),
            sa.or_(
                per_schedule_run_count < min_runs,
                per_schedule_max_time < right_now + min_scheduled_time,
            ),
        )
        .correlate(db.Deployment)
        .exists()
    )

    query = (
        sa.select(db.Deployment.id)
        .where(
            db.Deployment.paused.is_not(True),
            any_schedule_needs_runs,
        )
        .order_by(db.Deployment.id)
        .limit(deployment_batch_size)
    )
    return query


def _get_select_recent_deployments_to_schedule_query(
    db: PrefectDBInterface,
    deployment_batch_size: int,
    loop_seconds: float,
) -> sa.Select[tuple[UUID]]:
    """
    Returns a sqlalchemy query for selecting recently updated deployments to schedule.
    """
    query = (
        sa.select(db.Deployment.id)
        .where(
            sa.and_(
                db.Deployment.paused.is_not(True),
                # use a slightly larger window than the loop interval to pick up
                # any deployments that were created *while* the scheduler was
                # last running (assuming the scheduler takes less than one
                # second to run). Scheduling is idempotent so picking up schedules
                # multiple times is not a concern.
                db.Deployment.updated
                >= now("UTC") - datetime.timedelta(seconds=loop_seconds + 1),
                (
                    # Only include deployments that have at least one
                    # active schedule.
                    sa.select(db.DeploymentSchedule.deployment_id)
                    .where(
                        sa.and_(
                            db.DeploymentSchedule.deployment_id == db.Deployment.id,
                            db.DeploymentSchedule.active.is_(True),
                        )
                    )
                    .exists()
                ),
            )
        )
        .order_by(db.Deployment.id)
        .limit(deployment_batch_size)
    )
    return query


async def _collect_flow_runs(
    db: PrefectDBInterface,
    session: AsyncSession,
    deployment_ids: Sequence[UUID],
    max_scheduled_time: datetime.timedelta,
    min_scheduled_time: datetime.timedelta,
    min_runs: int,
    max_runs: int,
) -> list[dict[str, Any]]:
    """Collect flow runs to schedule from a list of deployments."""
    runs_to_insert: list[dict[str, Any]] = []
    for deployment_id in deployment_ids:
        right_now = now("UTC")
        # guard against erroneously configured schedules
        try:
            runs_to_insert.extend(
                await models.deployments._generate_scheduled_flow_runs(
                    db,
                    session=session,
                    deployment_id=deployment_id,
                    start_time=right_now,
                    end_time=right_now + max_scheduled_time,
                    min_time=min_scheduled_time,
                    min_runs=min_runs,
                    max_runs=max_runs,
                )
            )
        except Exception:
            logger.exception(
                f"Error scheduling deployment {deployment_id!r}.",
            )
        finally:
            connection = await session.connection()
            if connection.invalidated:
                # If the error we handled above was the kind of database error that
                # causes underlying transaction to rollback and the connection to
                # become invalidated, rollback this session.
                await session.rollback()
                raise TryAgain()
    return runs_to_insert


@perpetual_service(
    enabled_getter=lambda: get_current_settings().server.services.scheduler.enabled,
)
async def schedule_deployments(
    perpetual: Perpetual = Perpetual(
        automatic=False,
        every=timedelta(
            seconds=get_current_settings().server.services.scheduler.loop_seconds
        ),
    ),
) -> None:
    """
    Main scheduler - schedules flow runs from deployments with active schedules.

    Schedule flow runs by:
    - Querying for deployments with active schedules
    - Generating the next set of flow runs based on each deployment's schedule
    - Inserting all scheduled flow runs into the database
    """
    settings = get_current_settings().server.services.scheduler
    deployment_batch_size = settings.deployment_batch_size
    max_runs = settings.max_runs
    min_runs = settings.min_runs
    max_scheduled_time = settings.max_scheduled_time
    min_scheduled_time = settings.min_scheduled_time
    insert_batch_size = settings.insert_batch_size

    db = provide_database_interface()
    total_inserted_runs = 0
    last_id = None

    while True:
        async with db.session_context(begin_transaction=False) as session:
            query = _get_select_deployments_to_schedule_query(
                db, deployment_batch_size, min_runs, min_scheduled_time
            )

            # use cursor based pagination
            if last_id:
                query = query.where(db.Deployment.id > last_id)

            result = await session.execute(query)
            deployment_ids = result.scalars().unique().all()

            # collect runs across all deployments
            try:
                runs_to_insert = await _collect_flow_runs(
                    db,
                    session=session,
                    deployment_ids=deployment_ids,
                    max_scheduled_time=max_scheduled_time,
                    min_scheduled_time=min_scheduled_time,
                    min_runs=min_runs,
                    max_runs=max_runs,
                )
            except TryAgain:
                continue

        # bulk insert the runs based on batch size setting
        for batch in batched_iterable(runs_to_insert, insert_batch_size):
            async with db.session_context(begin_transaction=True) as session:
                inserted_runs = await models.deployments._insert_scheduled_flow_runs(
                    session=session, runs=list(batch)
                )
                total_inserted_runs += len(inserted_runs)

        # if this is the last page of deployments, exit the loop
        if len(deployment_ids) < deployment_batch_size:
            break
        else:
            # record the last deployment ID
            last_id = deployment_ids[-1]

    logger.info(f"Scheduled {total_inserted_runs} runs.")


@perpetual_service(
    enabled_getter=lambda: get_current_settings().server.services.scheduler.enabled,
)
async def schedule_recent_deployments(
    perpetual: Perpetual = Perpetual(
        automatic=False,
        every=timedelta(
            seconds=get_current_settings().server.services.scheduler.recent_deployments_loop_seconds
        ),
    ),
) -> None:
    """
    Recent deployments scheduler - schedules deployments that were updated very recently.

    This scheduler runs on a tight loop and ensures that runs from newly-created or
    updated deployments are rapidly scheduled without waiting for the main scheduler.

    Note that scheduling is idempotent, so it's okay for this scheduler to attempt
    to schedule the same deployments as the main scheduler.
    """
    settings = get_current_settings().server.services.scheduler
    deployment_batch_size = settings.deployment_batch_size
    max_runs = settings.max_runs
    min_runs = settings.min_runs
    max_scheduled_time = settings.max_scheduled_time
    min_scheduled_time = settings.min_scheduled_time
    insert_batch_size = settings.insert_batch_size
    loop_seconds = settings.recent_deployments_loop_seconds

    db = provide_database_interface()
    total_inserted_runs = 0
    last_id = None

    while True:
        async with db.session_context(begin_transaction=False) as session:
            query = _get_select_recent_deployments_to_schedule_query(
                db, deployment_batch_size, loop_seconds
            )

            if last_id:
                query = query.where(db.Deployment.id > last_id)

            result = await session.execute(query)
            deployment_ids = result.scalars().unique().all()

            try:
                runs_to_insert = await _collect_flow_runs(
                    db,
                    session=session,
                    deployment_ids=deployment_ids,
                    max_scheduled_time=max_scheduled_time,
                    min_scheduled_time=min_scheduled_time,
                    min_runs=min_runs,
                    max_runs=max_runs,
                )
            except TryAgain:
                continue

        for batch in batched_iterable(runs_to_insert, insert_batch_size):
            async with db.session_context(begin_transaction=True) as session:
                inserted_runs = await models.deployments._insert_scheduled_flow_runs(
                    session=session, runs=list(batch)
                )
                total_inserted_runs += len(inserted_runs)

        if len(deployment_ids) < deployment_batch_size:
            break
        else:
            last_id = deployment_ids[-1]

    logger.info(f"Scheduled {total_inserted_runs} runs.")
