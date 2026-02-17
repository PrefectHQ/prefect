from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import timedelta
from typing import TYPE_CHECKING, Any, AsyncGenerator, NoReturn, Optional
from uuid import UUID

import sqlalchemy as sa
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

import prefect.types._datetime
from prefect.logging import get_logger
from prefect.server.database import (
    PrefectDBInterface,
    db_injector,
    provide_database_interface,
)
from prefect.server.events.ordering import (
    EventArrivedEarly,
    get_task_run_recorder_causal_ordering,
)
from prefect.server.events.ordering.memory import EventBeingProcessed
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
    db = provide_database_interface()

    async with db.session_context() as session:
        task_run, task_run_dict = db_recordable_task_run_from_event(event)

        assert task_run.state is not None

        now = prefect.types._datetime.now("UTC")

        if task_run.flow_run_id is not None:
            update_dict = {k: v for k, v in task_run_dict.items() if k != "id"}
            await session.execute(
                db.queries.insert(db.TaskRun)
                .values(**task_run_dict | {"created": now})
                .on_conflict_do_update(
                    index_elements=db.orm.task_run_unique_upsert_columns,
                    set_={**update_dict | {"updated": now}},
                    where=db.TaskRun.state_timestamp < task_run.state.timestamp,
                )
            )
            result = await session.execute(
                sa.select(db.TaskRun.id)
                .where(
                    sa.and_(
                        db.TaskRun.flow_run_id == task_run.flow_run_id,
                        db.TaskRun.task_key == task_run.task_key,
                        db.TaskRun.dynamic_key == task_run.dynamic_key,
                    )
                )
                .limit(1)
            )
            task_run.id = result.scalar_one()
        else:
            await session.execute(
                db.queries.insert(db.TaskRun)
                .values(**task_run_dict | {"created": now})
                .on_conflict_do_update(
                    index_elements=["id"],
                    set_={**task_run_dict | {"updated": now}},
                    where=db.TaskRun.state_timestamp < task_run.state.timestamp,
                )
            )

        await _insert_task_run_states(session, [task_run])

        await session.commit()


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

    # Drop duplicate tasks, keep the one with the latest state_timestamp
    all_task_runs.sort(key=lambda tr: tr["task_run"].state.timestamp)
    unique_task_runs_by_id: dict[UUID, dict[str, Any]] = {}
    for tr in all_task_runs:
        unique_task_runs_by_id[tr["task_run"].id] = tr

    # Also deduplicate by natural key (flow_run_id, task_key, dynamic_key)
    # for task runs with a flow_run_id, since multiple workers may process
    # events with different ids for the same logical task run.
    # Explicitly keep the entry with the latest state_timestamp per natural key.
    unique_by_natural_key: dict[tuple, dict[str, Any]] = {}
    without_flow_run: list[dict[str, Any]] = []
    for tr in unique_task_runs_by_id.values():
        task_run = tr["task_run"]
        if task_run.flow_run_id is not None:
            natural_key = (
                task_run.flow_run_id,
                task_run.task_key,
                task_run.dynamic_key,
            )
            existing = unique_by_natural_key.get(natural_key)
            if (
                existing is None
                or task_run.state.timestamp > existing["task_run"].state.timestamp
            ):
                unique_by_natural_key[natural_key] = tr
        else:
            without_flow_run.append(tr)
    unique_task_runs = list(unique_by_natural_key.values()) + without_flow_run

    # Batch by keys to avoid column mismatches during bulk insert
    batches_by_keys: dict[frozenset[str], list] = {}
    for tr in unique_task_runs:
        key_signature = frozenset(tr["task_run_dict"].keys())
        batches_by_keys.setdefault(key_signature, []).append(tr)

    logger.debug(
        f"Partitioned task runs into {len(batches_by_keys)} groups by update columns"
    )

    db = provide_database_interface()

    async with db.session_context() as session:
        for key_signature, batch in batches_by_keys.items():
            update_cols = set(key_signature) - {"id", "created"}

            # Split batch by flow_run_id presence for different conflict handling
            with_flow_run_batch = [
                tr for tr in batch if tr["task_run"].flow_run_id is not None
            ]
            no_flow_run_batch = [
                tr for tr in batch if tr["task_run"].flow_run_id is None
            ]

            if with_flow_run_batch:
                logger.debug(
                    f"Preparing to bulk insert {len(with_flow_run_batch)} task runs "
                    f"with composite key conflict handling"
                )
                to_insert = [
                    tr["task_run_dict"] | {"created": now, "updated": now}
                    for tr in with_flow_run_batch
                ]
                insert_statement = db.queries.insert(db.TaskRun).values(to_insert)
                upsert_statement = insert_statement.on_conflict_do_update(
                    index_elements=db.orm.task_run_unique_upsert_columns,
                    set_={
                        col.name: getattr(insert_statement.excluded, col.name)
                        for col in insert_statement.excluded
                        if col.name in (update_cols | {"updated"}) and col.name != "id"
                    },
                    where=db.TaskRun.state_timestamp
                    < insert_statement.excluded.state_timestamp,
                )
                await session.execute(upsert_statement)

            if no_flow_run_batch:
                logger.debug(
                    f"Preparing to bulk insert {len(no_flow_run_batch)} task runs "
                    f"with id conflict handling"
                )
                to_insert = [
                    tr["task_run_dict"] | {"created": now, "updated": now}
                    for tr in no_flow_run_batch
                ]
                insert_statement = db.queries.insert(db.TaskRun).values(to_insert)
                upsert_statement = insert_statement.on_conflict_do_update(
                    index_elements=["id"],
                    set_={
                        col.name: getattr(insert_statement.excluded, col.name)
                        for col in insert_statement.excluded
                        if col.name in update_cols | {"updated"}
                    },
                    where=db.TaskRun.state_timestamp
                    < insert_statement.excluded.state_timestamp,
                )
                await session.execute(upsert_statement)

            logger.debug(f"Finished bulk inserting {len(batch)} task runs")

        # Resolve actual task_run ids for all task runs that have a flow_run_id.
        # The ON CONFLICT on composite key preserves the existing row's id, which
        # may differ from the event's task_run_id if another worker inserted first.
        flow_run_task_runs = [
            tr for tr in all_task_runs if tr["task_run"].flow_run_id is not None
        ]
        if flow_run_task_runs:
            natural_keys = list(
                {
                    (
                        tr["task_run"].flow_run_id,
                        tr["task_run"].task_key,
                        tr["task_run"].dynamic_key,
                    )
                    for tr in flow_run_task_runs
                }
            )
            conditions = [
                sa.and_(
                    db.TaskRun.flow_run_id == fid,
                    db.TaskRun.task_key == tk,
                    db.TaskRun.dynamic_key == dk,
                )
                for fid, tk, dk in natural_keys
            ]
            result = await session.execute(
                sa.select(
                    db.TaskRun.id,
                    db.TaskRun.flow_run_id,
                    db.TaskRun.task_key,
                    db.TaskRun.dynamic_key,
                ).where(sa.or_(*conditions))
            )
            actual_ids: dict[tuple, UUID] = {
                (row.flow_run_id, row.task_key, row.dynamic_key): row.id
                for row in result
            }
            for tr in flow_run_task_runs:
                task_run = tr["task_run"]
                natural_key = (
                    task_run.flow_run_id,
                    task_run.task_key,
                    task_run.dynamic_key,
                )
                if natural_key in actual_ids:
                    task_run.id = actual_ids[natural_key]

        # Insert task run states, deduplicating by (task_run_id, timestamp) to
        # avoid violating uq_task_run_state__task_run_id_timestamp_desc when
        # multiple events resolved to the same task_run id after natural-key dedup.
        seen_state_keys: set[tuple] = set()
        deduped_for_states: list[TaskRun] = []
        for tr in all_task_runs:
            task_run = tr["task_run"]
            assert task_run.state is not None
            key = (task_run.id, task_run.state.timestamp)
            if key not in seen_state_keys:
                seen_state_keys.add(key)
                deduped_for_states.append(task_run)
        await _insert_task_run_states(session, deduped_for_states)
        await session.commit()


async def handle_task_run_events(events: list[ReceivedEvent], depth: int = 0) -> None:
    to_insert = []

    for event in events:
        try:
            async with AsyncExitStack() as stack:
                await stack.enter_async_context(
                    get_task_run_recorder_causal_ordering().preceding_event_confirmed(
                        record_task_run_event, event, depth=depth
                    )
                )
        except EventArrivedEarly:
            # We're safe to ACK this message because it has been parked by the
            # causal ordering mechanism and will be reprocessed when the preceding
            # event arrives.
            continue
        except EventBeingProcessed:
            pass

        to_insert.append(event)

    logger.debug(
        f"Recording {len(to_insert)} task run events in bulk ({len(events)} total events received, {len(events) - len(to_insert)} parked for causal ordering)"
    )
    await record_bulk_task_run_events(to_insert)
    logger.debug(f"Finished recording {len(to_insert)} bulk task run events")


async def record_lost_follower_task_run_events() -> None:
    ordering = get_task_run_recorder_causal_ordering()
    events = await ordering.get_lost_followers()

    for event in events:
        print(f"Processing lost follower event {event.id}")
        # Temporarily skip events that are older than 24 hours
        # this is to avoid processing a large backlog of events
        # that are potentially sitting in the waitlist while
        # we were not processing lost followers
        if event.occurred < prefect.types._datetime.now("UTC") - timedelta(hours=24):
            await ordering.forget_follower(event)
            continue

        await record_task_run_event(event)


async def periodically_process_followers(periodic_granularity: timedelta) -> NoReturn:
    """Periodically process followers that are waiting on a leader event that never arrived"""

    logger.info(
        "Starting periodically process followers task every %s seconds",
        periodic_granularity.total_seconds(),
    )
    while True:
        try:
            await record_lost_follower_task_run_events()
        except asyncio.CancelledError:
            logger.info("Periodically process followers task cancelled")
            return
        except Exception:
            logger.exception("Error running periodically process followers task")
        finally:
            await asyncio.sleep(periodic_granularity.total_seconds())


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

    record_lost_followers_task = asyncio.create_task(
        periodically_process_followers(periodic_granularity=timedelta(seconds=5))
    )

    queue: asyncio.Queue[RetryableEvent] = asyncio.Queue()

    async def flush() -> None:
        logger.debug(f"Persisting {queue.qsize()} events...")

        batch: list[RetryableEvent] = []

        while queue.qsize() > 0 and len(batch) < write_batch_size:
            batch.append(await queue.get())

        try:
            await handle_task_run_events([batch.event for batch in batch])
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
        record_lost_followers_task.cancel()
        periodic_flush.cancel()
        try:
            await record_lost_followers_task
        except asyncio.CancelledError:
            logger.info("Periodically process followers task cancelled successfully")

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
