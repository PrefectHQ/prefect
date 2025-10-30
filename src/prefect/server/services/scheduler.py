"""
The Scheduler service.
"""

from __future__ import annotations

import datetime
import logging
from datetime import timedelta
from typing import Any, Sequence
from uuid import UUID

import sqlalchemy as sa
from docket import Depends, Perpetual
from sqlalchemy.ext.asyncio import AsyncSession

import prefect.server.models as models
from prefect.logging import get_logger
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.schemas.states import StateType
from prefect.settings import (
    PREFECT_API_SERVICES_SCHEDULER_DEPLOYMENT_BATCH_SIZE,
    PREFECT_API_SERVICES_SCHEDULER_INSERT_BATCH_SIZE,
    PREFECT_API_SERVICES_SCHEDULER_LOOP_SECONDS,
    PREFECT_API_SERVICES_SCHEDULER_MAX_RUNS,
    PREFECT_API_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME,
    PREFECT_API_SERVICES_SCHEDULER_MIN_RUNS,
    PREFECT_API_SERVICES_SCHEDULER_MIN_SCHEDULED_TIME,
)
from prefect.settings.context import get_current_settings
from prefect.types._datetime import now
from prefect.utilities.collections import batched_iterable

logger: "logging.Logger" = get_logger(__name__)


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

    The query gets the IDs of any deployments with:

        - an active schedule
        - EITHER:
            - fewer than `min_runs` auto-scheduled runs
            - OR the max scheduled time is less than `max_scheduled_time` in the future
    """
    right_now = now("UTC")
    query = (
        sa.select(db.Deployment.id)
        .select_from(db.Deployment)
        .join(
            db.FlowRun,
            sa.and_(
                db.Deployment.id == db.FlowRun.deployment_id,
                db.FlowRun.state_type == StateType.SCHEDULED,
                db.FlowRun.next_scheduled_start_time >= right_now,
                db.FlowRun.auto_scheduled.is_(True),
            ),
            isouter=True,
        )
        .where(
            sa.and_(
                db.Deployment.paused.is_not(True),
                (
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
        .group_by(db.Deployment.id)
        .having(
            sa.or_(
                sa.func.count(db.FlowRun.next_scheduled_start_time) < min_runs,
                sa.func.max(db.FlowRun.next_scheduled_start_time)
                < right_now + min_scheduled_time,
            )
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
                db.Deployment.updated
                >= now("UTC") - datetime.timedelta(seconds=loop_seconds + 1),
                (
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
    """Collect flow runs to schedule for the given deployments."""
    runs_to_insert: list[dict[str, Any]] = []
    for deployment_id in deployment_ids:
        right_now = now("UTC")
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
                await session.rollback()
                raise TryAgain()
    return runs_to_insert


async def schedule_deployments(
    db: PrefectDBInterface = Depends(provide_database_interface),
    perpetual: Perpetual = Perpetual(
        automatic=True,
        every=timedelta(seconds=PREFECT_API_SERVICES_SCHEDULER_LOOP_SECONDS.value()),
    ),
) -> None:
    """
    Main scheduler - schedules flow runs from deployments.

    Perpetual task that runs according to PREFECT_API_SERVICES_SCHEDULER_LOOP_SECONDS.
    """
    logger.info("schedule_deployments() EXECUTING")
    deployment_batch_size = PREFECT_API_SERVICES_SCHEDULER_DEPLOYMENT_BATCH_SIZE.value()
    max_runs = PREFECT_API_SERVICES_SCHEDULER_MAX_RUNS.value()
    min_runs = PREFECT_API_SERVICES_SCHEDULER_MIN_RUNS.value()
    max_scheduled_time = PREFECT_API_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME.value()
    min_scheduled_time = PREFECT_API_SERVICES_SCHEDULER_MIN_SCHEDULED_TIME.value()
    insert_batch_size = PREFECT_API_SERVICES_SCHEDULER_INSERT_BATCH_SIZE.value()

    total_inserted_runs = 0
    last_id = None

    while True:
        async with db.session_context(begin_transaction=False) as session:
            query = _get_select_deployments_to_schedule_query(
                db, deployment_batch_size, min_runs, min_scheduled_time
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


async def schedule_recent_deployments(
    db: PrefectDBInterface = Depends(provide_database_interface),
    perpetual: Perpetual = Perpetual(
        automatic=True,
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

    Perpetual task that runs according to recent_deployments_loop_seconds setting.
    """
    deployment_batch_size = PREFECT_API_SERVICES_SCHEDULER_DEPLOYMENT_BATCH_SIZE.value()
    max_runs = PREFECT_API_SERVICES_SCHEDULER_MAX_RUNS.value()
    min_runs = PREFECT_API_SERVICES_SCHEDULER_MIN_RUNS.value()
    max_scheduled_time = PREFECT_API_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME.value()
    min_scheduled_time = PREFECT_API_SERVICES_SCHEDULER_MIN_SCHEDULED_TIME.value()
    insert_batch_size = PREFECT_API_SERVICES_SCHEDULER_INSERT_BATCH_SIZE.value()
    loop_seconds = (
        get_current_settings().server.services.scheduler.recent_deployments_loop_seconds
    )

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
