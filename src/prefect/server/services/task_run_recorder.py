from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, AsyncGenerator, NoReturn, Optional
from uuid import UUID

import sqlalchemy as sa
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import prefect.types._datetime
from prefect.logging import get_logger
from prefect.server.database import (
    PrefectDBInterface,
    db_injector,
    provide_database_interface,
)
from prefect.server.events.schemas.events import ReceivedEvent
from prefect.server.schemas.core import TaskRun
from prefect.server.schemas.states import State
from prefect.server.services.base import RunInEphemeralServers, Service
from prefect.server.utilities.messaging import (
    Consumer,
    Message,
    MessageHandler,
    create_consumer,
)
from prefect.server.utilities.messaging._consumer_names import (
    generate_unique_consumer_name,
)
from prefect.server.utilities.messaging.memory import log_metrics_periodically
from prefect.settings.context import get_current_settings
from prefect.settings.models.server.services import ServicesBaseSetting

if TYPE_CHECKING:
    import logging

logger: "logging.Logger" = get_logger(__name__)

DEFAULT_PERSIST_MAX_RETRIES = 5

TaskRunUpsertKey = tuple[str, UUID] | tuple[str, UUID, str, str]


def _task_run_upsert_key(task_run: TaskRun) -> TaskRunUpsertKey:
    if task_run.flow_run_id is None:
        return ("id", task_run.id)
    return (
        "natural-key",
        task_run.flow_run_id,
        task_run.task_key,
        task_run.dynamic_key,
    )


@db_injector
async def _insert_task_run_states(
    db: PrefectDBInterface, session: AsyncSession, task_runs: list[TaskRun]
):
    if TYPE_CHECKING:
        for task_run in task_runs:
            assert task_run.state is not None

    now = prefect.types._datetime.now("UTC")

    await session.execute(
        db.queries.insert(db.TaskRunState)
        .values(
            [
                {
                    "created": now,
                    "task_run_id": task_run.id,
                    **task_run.state.model_dump(),
                }
                for task_run in task_runs
            ]
        )
        .on_conflict_do_nothing(
            index_elements=[
                "id",
            ]
        )
    )

    logger.debug(f"Recorded {len(task_runs)} task run state change(s)")


def task_run_from_event(event: ReceivedEvent) -> TaskRun:
    task_run_id = event.resource.prefect_object_id("prefect.task-run")

    flow_run_id: Optional[UUID] = None
    if flow_run_resource := event.resource_in_role.get("flow-run"):
        flow_run_id = flow_run_resource.prefect_object_id("prefect.flow-run")

    state: State = State.model_validate(
        {
            "id": event.id,
            "timestamp": event.occurred,
            **event.payload["validated_state"],
        }
    )
    state.state_details.task_run_id = task_run_id
    state.state_details.flow_run_id = flow_run_id

    return TaskRun.model_validate(
        {
            "id": task_run_id,
            "flow_run_id": flow_run_id,
            "state_id": state.id,
            "state": state,
            **event.payload["task_run"],
        }
    )


def db_recordable_task_run_from_event(
    event: ReceivedEvent,
) -> tuple[TaskRun, dict[str, Any]]:
    task_run: TaskRun = task_run_from_event(event)

    task_run_attributes = task_run.model_dump_for_orm(
        exclude={
            "state_id",
            "state",
            "created",
            "estimated_run_time",
            "estimated_start_time_delta",
        },
        exclude_unset=True,
    )

    assert task_run.state is not None

    denormalized_state_attributes = {
        "state_id": task_run.state.id,
        "state_type": task_run.state.type,
        "state_name": task_run.state.name,
        "state_timestamp": task_run.state.timestamp,
    }

    return task_run, {
        **task_run_attributes,
        **denormalized_state_attributes,
    }


async def record_task_run_event(event: ReceivedEvent, depth: int = 0) -> None:
    """Record a single task run event in the database"""
    max_attempts = 2
    for attempt in range(1, max_attempts + 1):
        try:
            await record_bulk_task_run_events([event])
            return
        except IntegrityError:
            if attempt < max_attempts:
                logger.info(
                    "Retrying task_run upsert after IntegrityError (attempt %s/%s)",
                    attempt,
                    max_attempts,
                )
                continue
            logger.warning(
                "Duplicate task_run, discarding event %s after %s attempts",
                event.id,
                max_attempts,
                exc_info=True,
            )


async def record_bulk_task_run_events(events: list[ReceivedEvent]) -> None:
    """Record multiple task run events in the database, taking advantage of bulk inserts."""

    if len(events) == 0:
        return

    now = prefect.types._datetime.now("UTC")

    all_task_runs = [
        {"task_run": task_run, "task_run_dict": task_run_dict, "event": event}
        for event in events
        for task_run, task_run_dict in [db_recordable_task_run_from_event(event)]
    ]

    # Drop duplicate task runs, keep the one with the latest state_timestamp.
    # For task runs linked to a flow run, the database identity is the natural key
    # (flow_run_id, task_key, dynamic_key); task run events can arrive with
    # different resource ids for the same natural key.
    all_task_runs.sort(key=lambda tr: tr["task_run"].state.timestamp)
    unique_task_runs_by_key: dict[TaskRunUpsertKey, dict[str, Any]] = {}
    for tr in all_task_runs:
        unique_task_runs_by_key[_task_run_upsert_key(tr["task_run"])] = tr
    unique_task_runs = sorted(
        unique_task_runs_by_key.values(),
        key=lambda tr: _task_run_upsert_key(tr["task_run"]),
    )

    # Batch by keys to avoid column mismatches during bulk insert.
    # Each batch preserves the conflict-key sort order established above for
    # deterministic lock acquisition, preventing deadlocks under concurrency.
    batches_by_keys: dict[tuple[frozenset[str], bool], list] = {}
    for tr in unique_task_runs:
        task_run = tr["task_run"]
        key_signature = (
            frozenset(tr["task_run_dict"].keys()),
            task_run.flow_run_id is not None,
        )
        batches_by_keys.setdefault(key_signature, []).append(tr)

    logger.debug(
        f"Partitioned task runs into {len(batches_by_keys)} groups by update columns"
    )

    db = provide_database_interface()

    async with db.session_context() as session:
        canonical_task_run_ids: dict[TaskRunUpsertKey, UUID] = {}

        for (column_keys, has_natural_key), batch in batches_by_keys.items():
            update_cols = set(column_keys) - {"id", "created"}

            logger.debug(f"Preparing to bulk insert {len(batch)} task runs")
            to_insert = [
                tr["task_run_dict"] | {"created": now, "updated": now} for tr in batch
            ]

            insert_statement = db.queries.insert(db.TaskRun).values(to_insert)
            index_elements = (
                db.orm.task_run_unique_upsert_columns if has_natural_key else ["id"]
            )
            upsert_statement = insert_statement.on_conflict_do_update(
                index_elements=index_elements,
                set_={
                    # See https://www.postgresql.org/docs/current/sql-insert.html for details on excluded.
                    # Idea is excluded.x references the proposed insertion value for column x.
                    **{
                        col.name: getattr(insert_statement.excluded, col.name)
                        for col in insert_statement.excluded
                        if col.name in (update_cols | {"updated"}) - {"id"}
                    },
                },
                where=db.TaskRun.state_timestamp
                < insert_statement.excluded.state_timestamp,
            )
            await session.execute(upsert_statement)

            logger.debug(f"Finished bulk inserting {len(batch)} task runs")

            if has_natural_key:
                natural_keys = [
                    (
                        tr["task_run"].flow_run_id,
                        tr["task_run"].task_key,
                        tr["task_run"].dynamic_key,
                    )
                    for tr in batch
                ]
                result = await session.execute(
                    sa.select(
                        db.TaskRun.flow_run_id,
                        db.TaskRun.task_key,
                        db.TaskRun.dynamic_key,
                        db.TaskRun.id,
                    ).where(
                        sa.tuple_(
                            db.TaskRun.flow_run_id,
                            db.TaskRun.task_key,
                            db.TaskRun.dynamic_key,
                        ).in_(natural_keys)
                    )
                )
                for flow_run_id, task_key, dynamic_key, task_run_id in result.all():
                    canonical_task_run_ids[
                        ("natural-key", flow_run_id, task_key, dynamic_key)
                    ] = task_run_id
            else:
                for tr in batch:
                    canonical_task_run_ids[_task_run_upsert_key(tr["task_run"])] = tr[
                        "task_run"
                    ].id

        for tr in all_task_runs:
            task_run = tr["task_run"]
            canonical_task_run_id = canonical_task_run_ids[
                _task_run_upsert_key(task_run)
            ]
            task_run.id = canonical_task_run_id
            if task_run.state is not None:
                task_run.state.state_details.task_run_id = canonical_task_run_id

        # Insert all task run states - we only coalesce task run updates, not states
        await _insert_task_run_states(session, [tr["task_run"] for tr in all_task_runs])
        await session.commit()


class RetryableEvent(BaseModel):
    event: ReceivedEvent
    persist_attempts: int = 0


@asynccontextmanager
async def consumer(
    write_batch_size: int,
    flush_every: int,
    max_persist_retries: int = DEFAULT_PERSIST_MAX_RETRIES,
) -> AsyncGenerator[MessageHandler, None]:
    logger.info(
        f"Creating TaskRunRecorder consumer with batch size {write_batch_size} and flush every {flush_every} seconds"
    )

    queue: asyncio.Queue[RetryableEvent] = asyncio.Queue()

    async def flush() -> None:
        logger.debug(f"Persisting {queue.qsize()} events...")

        batch: list[RetryableEvent] = []

        while queue.qsize() > 0 and len(batch) < write_batch_size:
            batch.append(await queue.get())

        try:
            await record_bulk_task_run_events([item.event for item in batch])
        except Exception:
            dropped = 0
            to_retry = 0
            for item in batch:
                item.persist_attempts += 1
                if item.persist_attempts <= max_persist_retries:
                    to_retry += 1
                    await queue.put(item)
                else:
                    dropped += 1
                    logger.error(
                        f"Dropping event {item.event.id} after {item.persist_attempts} failed attempts"
                    )
            logger.error(
                f"Error flushing {len(batch)} events ({to_retry} to retry, {dropped} dropped)",
                exc_info=True,
            )

            if dropped > 0:
                raise

    async def flush_periodically():
        try:
            while True:
                await asyncio.sleep(flush_every)
                if queue.qsize():
                    await flush()
        except asyncio.CancelledError:
            return

    async def message_handler(message: Message):
        event: ReceivedEvent = ReceivedEvent.model_validate_json(message.data)

        if not event.event.startswith("prefect.task-run"):
            return

        if not event.resource.get("prefect.orchestration") == "client":
            return

        logger.debug(
            "Received event: %s with id: %s for resource: %s",
            event.event,
            event.id,
            event.resource.get("prefect.resource.id"),
        )

        await queue.put(RetryableEvent(event=event))

        if queue.qsize() >= write_batch_size:
            await flush()

    periodic_flush = asyncio.create_task(flush_periodically())

    try:
        yield message_handler
    finally:
        periodic_flush.cancel()

        if queue.qsize():
            await flush()


class TaskRunRecorder(RunInEphemeralServers, Service):
    """Constructs task runs and states from client-emitted events"""

    consumer_task: asyncio.Task[None] | None = None
    metrics_task: asyncio.Task[None] | None = None

    @classmethod
    def service_settings(cls) -> ServicesBaseSetting:
        return get_current_settings().server.services.task_run_recorder

    def __init__(self):
        super().__init__()
        self._started_event: Optional[asyncio.Event] = None

    @property
    def started_event(self) -> asyncio.Event:
        if self._started_event is None:
            self._started_event = asyncio.Event()
        return self._started_event

    @started_event.setter
    def started_event(self, value: asyncio.Event) -> None:
        self._started_event = value

    async def start(
        self, max_persist_retries: int = DEFAULT_PERSIST_MAX_RETRIES
    ) -> NoReturn:
        assert self.consumer_task is None, "TaskRunRecorder already started"
        self.consumer: Consumer = create_consumer(
            "events",
            group="task-run-recorder",
            name=generate_unique_consumer_name("task-run-recorder"),
            read_batch_size=self.service_settings().read_batch_size,
        )

        async with consumer(
            write_batch_size=self.service_settings().batch_size,
            flush_every=int(self.service_settings().flush_interval),
            max_persist_retries=max_persist_retries,
        ) as handler:
            self.consumer_task = asyncio.create_task(self.consumer.run(handler))
            self.metrics_task = asyncio.create_task(log_metrics_periodically())

            logger.debug("TaskRunRecorder started")
            self.started_event.set()

            try:
                await self.consumer_task
            except asyncio.CancelledError:
                pass

    async def stop(self) -> None:
        assert self.consumer_task is not None, "Logger not started"
        self.consumer_task.cancel()
        if self.metrics_task:
            self.metrics_task.cancel()
        try:
            await self.consumer_task
            if self.metrics_task:
                await self.metrics_task
        except asyncio.CancelledError:
            pass
        finally:
            self.consumer_task = None
            self.metrics_task = None
        logger.debug("TaskRunRecorder stopped")
