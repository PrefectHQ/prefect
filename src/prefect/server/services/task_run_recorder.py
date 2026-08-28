from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, AsyncGenerator, NamedTuple, NoReturn, Optional
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
from prefect.server.utilities.database import get_max_query_parameters
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

    TaskRunUpsertKey = tuple[str, UUID] | tuple[str, UUID, str, str]
    TaskRunTargetValue = UUID | tuple[UUID, str, str]

logger: "logging.Logger" = get_logger(__name__)

DEFAULT_PERSIST_MAX_RETRIES = 5


def _task_run_upsert_key(task_run: TaskRun) -> TaskRunUpsertKey:
    if task_run.flow_run_id is None:
        return ("id", task_run.id)
    return (
        "natural-key",
        task_run.flow_run_id,
        task_run.task_key,
        task_run.dynamic_key,
    )


def _task_run_conflict_keys(task_run: TaskRun) -> list[TaskRunUpsertKey]:
    keys: list[TaskRunUpsertKey] = [("id", task_run.id)]
    if task_run.flow_run_id is not None:
        keys.append(
            (
                "natural-key",
                task_run.flow_run_id,
                task_run.task_key,
                task_run.dynamic_key,
            )
        )
    return keys


def _task_run_target_value(
    task_run: TaskRun, conflict_target: str
) -> TaskRunTargetValue:
    """The value `ON CONFLICT` matches this row on."""
    if conflict_target == "natural-key":
        return (task_run.flow_run_id, task_run.task_key, task_run.dynamic_key)
    return task_run.id


@dataclass
class _TaskRunRecord:
    """One event's task run, and the upsert bookkeeping resolved for it.

    The fields the constructor does not take are filled in stages, each by the
    method named below it. They have no defaults, so reading one before its
    stage has run raises `AttributeError` instead of silently reading a
    placeholder.
    """

    task_run: TaskRun
    # the columns to insert, keyed by column name; a key it does not carry is
    # left to its default, and a `None` value asks to write a real NULL
    task_run_dict: dict[str, Any]

    # `pin_upsert_key`
    conflict_group: TaskRunUpsertKey = field(init=False)
    upsert_key: TaskRunUpsertKey = field(init=False)
    # `resolve_conflict_target`
    conflict_target: str = field(init=False)
    target_value: TaskRunTargetValue = field(init=False)

    def pin_upsert_key(self, conflict_group: TaskRunUpsertKey) -> None:
        """Record the coalesced group, and the upsert key as it stands now.

        `rewrite_id` can change `task_run.id`, and so the upsert key, so it has
        to be pinned before that happens and used for every later lookup.
        """
        self.conflict_group = conflict_group
        self.upsert_key = _task_run_upsert_key(self.task_run)

    def rewrite_id(self, canonical_task_run_id: UUID) -> None:
        """Point the row at the id an existing row already holds.

        Both the model and the payload are rewritten, so the statement inserts
        the canonical id and callers observe it too.
        """
        self.task_run.id = canonical_task_run_id
        self.task_run_dict["id"] = canonical_task_run_id

    def resolve_conflict_target(self, conflict_target: str) -> None:
        """Fix the `ON CONFLICT` target, and the value it matches this row on."""
        self.conflict_target = conflict_target
        self.target_value = _task_run_target_value(self.task_run, conflict_target)


class _UpsertSegment(NamedTuple):
    """A contiguous run of task runs that can share one upsert statement."""

    conflict_target: str
    columns: frozenset[str]
    null_filled: frozenset[str]
    rows: list[_TaskRunRecord]


def _fillable_columns(db: PrefectDBInterface) -> frozenset[str]:
    """Columns where passing `NULL` does the same thing as leaving the key out.

    An explicit `None` overrides a column default, so any column with a default
    is excluded.
    """
    return (
        frozenset(
            column.name
            for column in db.TaskRun.__table__.columns
            if column.nullable
            and column.default is None
            and column.server_default is None
        )
        # the ON CONFLICT WHERE clause compares against this column, and
        # `x < NULL` is NULL, so a NULL-filled row would silently skip its update
        - {"state_timestamp"}
        # ON CONFLICT matches rows on these columns, and NULL matches nothing, so
        # a filled row would insert a duplicate instead of updating. Excluding them
        # also keeps `flow_run_id` out of the coalesce, so an event with no flow
        # run still clears it.
        - {column.key for column in db.orm.task_run_unique_upsert_columns}
    )


def _segment_task_runs_for_upsert(
    task_runs: list[_TaskRunRecord],
    fillable: frozenset[str],
    max_rows: int,
) -> list[_UpsertSegment]:
    """Group already-sorted task runs into the longest batches that can share a statement.

    Each record must have had `resolve_conflict_target` called on it.

    Segments are contiguous blocks of the input, emitted in order, so
    concatenating them gives back the input unchanged. The caller has already
    sorted the rows by conflict key, which is what makes concurrent recorders
    take row locks in the same order and so not deadlock.
    """
    segments: list[_UpsertSegment] = []

    conflict_target = ""
    # Segments below hold on to these, and `|=` on a frozenset rebinds rather
    # than mutating in place, so an emitted segment's sets can never grow. Plain
    # sets would leave every segment sharing one object that ends up describing
    # the whole flush.
    union: frozenset[str] = frozenset()
    null_filled: frozenset[str] = frozenset()
    explicit_nulls: frozenset[str] = frozenset()
    seen: set[TaskRunTargetValue] = set()
    rows: list[_TaskRunRecord] = []

    for tr in task_runs:
        columns = frozenset(tr.task_run_dict)
        row_nulls = frozenset(
            column for column, value in tr.task_run_dict.items() if value is None
        )
        if rows:
            # A statement has a single column list, so any row missing one of its
            # columns is given NULL there. Merging adds a fill for every column the
            # batch and this row do not both have.
            merged_fills = null_filled | (union ^ columns)
            merged_nulls = explicit_nulls | row_nulls
            if (
                tr.conflict_target == conflict_target
                # a fill is only safe on a fillable column, and only where no row
                # writes a real NULL: the two are the same value, so one SET
                # clause cannot mean both
                and merged_fills <= fillable - merged_nulls
                # a target value already in the batch makes PostgreSQL raise
                # CardinalityViolationError, which is not an IntegrityError and so is
                # never retried, and makes SQLite silently keep only the last write
                and tr.target_value not in seen
                and len(rows) < max_rows
            ):
                union |= columns
                null_filled, explicit_nulls = merged_fills, merged_nulls
                seen.add(tr.target_value)
                rows.append(tr)
                continue
            segments.append(_UpsertSegment(conflict_target, union, null_filled, rows))

        conflict_target = tr.conflict_target
        union = columns
        null_filled = frozenset()
        explicit_nulls = row_nulls
        seen = {tr.target_value}
        rows = [tr]

    if rows:
        segments.append(_UpsertSegment(conflict_target, union, null_filled, rows))

    return segments


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
    """Record a single task run event in the database.

    Delegates to `record_bulk_task_run_events`, which already retries once on
    `IntegrityError` to recover from TOCTOU races against concurrent recorders.
    Any `IntegrityError` that survives the retry is treated as an unrecoverable
    duplicate and the event is discarded.
    """
    try:
        await record_bulk_task_run_events([event])
    except IntegrityError:
        logger.warning(
            "Duplicate task_run, discarding event %s",
            event.id,
            exc_info=True,
        )


async def record_bulk_task_run_events(events: list[ReceivedEvent]) -> None:
    """Record multiple task run events in the database, taking advantage of bulk inserts.

    Retries once on `IntegrityError` to handle TOCTOU races between concurrent
    recorder instances: when two batches reference the same `task_run.id` with
    different natural keys, one batch's existence-check SELECT may run before
    the other batch's INSERT commits. The retry re-runs the SELECT in a fresh
    session so the conflict target is chosen against the now-visible row.
    """

    max_attempts = 2
    for attempt in range(1, max_attempts + 1):
        try:
            await _record_bulk_task_run_events(events)
            return
        except IntegrityError:
            if attempt < max_attempts:
                logger.info(
                    "Retrying bulk task_run upsert after IntegrityError"
                    " (attempt %s/%s)",
                    attempt,
                    max_attempts,
                )
                continue
            raise


async def _record_bulk_task_run_events(events: list[ReceivedEvent]) -> None:
    if len(events) == 0:
        return

    now = prefect.types._datetime.now("UTC")

    all_task_runs = [
        _TaskRunRecord(task_run=task_run, task_run_dict=task_run_dict)
        for event in events
        for task_run, task_run_dict in [db_recordable_task_run_from_event(event)]
    ]

    # Drop duplicate task run rows, keep the one with the latest state_timestamp.
    # A single bulk flush can contain events that collide on either id or natural
    # key, so coalesce connected conflicts before choosing the ON CONFLICT target.
    all_task_runs.sort(key=lambda tr: tr.task_run.state.timestamp)
    parent: dict[TaskRunUpsertKey, TaskRunUpsertKey] = {}

    def find(key: TaskRunUpsertKey) -> TaskRunUpsertKey:
        parent.setdefault(key, key)
        if parent[key] != key:
            parent[key] = find(parent[key])
        return parent[key]

    def union(left: TaskRunUpsertKey, right: TaskRunUpsertKey) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for tr in all_task_runs:
        conflict_keys = _task_run_conflict_keys(tr.task_run)
        for conflict_key in conflict_keys[1:]:
            union(conflict_keys[0], conflict_key)

    unique_task_runs_by_group: dict[TaskRunUpsertKey, _TaskRunRecord] = {}
    conflict_keys_by_group: dict[TaskRunUpsertKey, set[TaskRunUpsertKey]] = {}
    upsert_key_aliases: dict[TaskRunUpsertKey, TaskRunUpsertKey] = {}
    for tr in all_task_runs:
        conflict_keys = _task_run_conflict_keys(tr.task_run)
        conflict_group = find(conflict_keys[0])
        tr.pin_upsert_key(conflict_group)
        unique_task_runs_by_group[conflict_group] = tr
        conflict_keys_by_group.setdefault(conflict_group, set()).update(conflict_keys)

    for tr in all_task_runs:
        upsert_key_aliases[tr.upsert_key] = unique_task_runs_by_group[
            tr.conflict_group
        ].upsert_key

    unique_task_runs = sorted(
        unique_task_runs_by_group.values(),
        key=lambda tr: tr.upsert_key,
    )

    db = provide_database_interface()

    task_run_ids: list[UUID] = []
    natural_keys: list[tuple[UUID, str, str]] = []
    for conflict_keys in conflict_keys_by_group.values():
        for conflict_key in conflict_keys:
            if len(conflict_key) == 2:
                task_run_ids.append(conflict_key[1])
            else:
                natural_keys.append((conflict_key[1], conflict_key[2], conflict_key[3]))

    async with db.session_context() as session:
        existing_task_run_ids: set[UUID] = set()
        existing_natural_keys: set[tuple[UUID, str, str]] = set()
        existing_task_run_ids_by_key: dict[TaskRunUpsertKey, UUID] = {}
        if task_run_ids or natural_keys:
            conditions = []
            if task_run_ids:
                conditions.append(db.TaskRun.id.in_(task_run_ids))
            if natural_keys:
                conditions.append(
                    sa.tuple_(
                        db.TaskRun.flow_run_id,
                        db.TaskRun.task_key,
                        db.TaskRun.dynamic_key,
                    ).in_(natural_keys)
                )
            result = await session.execute(
                sa.select(
                    db.TaskRun.id,
                    db.TaskRun.flow_run_id,
                    db.TaskRun.task_key,
                    db.TaskRun.dynamic_key,
                ).where(sa.or_(*conditions))
            )
            for task_run_id, flow_run_id, task_key, dynamic_key in result.all():
                existing_task_run_ids.add(task_run_id)
                existing_task_run_ids_by_key[("id", task_run_id)] = task_run_id
                if flow_run_id is not None:
                    existing_natural_keys.add((flow_run_id, task_key, dynamic_key))
                    existing_task_run_ids_by_key[
                        ("natural-key", flow_run_id, task_key, dynamic_key)
                    ] = task_run_id

        def conflict_target(tr: _TaskRunRecord) -> str:
            task_run = tr.task_run
            natural_key = (
                task_run.flow_run_id,
                task_run.task_key,
                task_run.dynamic_key,
            )
            if (
                task_run.flow_run_id is not None
                and natural_key in existing_natural_keys
            ):
                return "natural-key"
            if task_run.id in existing_task_run_ids:
                return "id"
            for conflict_key in sorted(
                conflict_keys_by_group[tr.conflict_group], key=str
            ):
                if conflict_key in existing_task_run_ids_by_key:
                    tr.rewrite_id(existing_task_run_ids_by_key[conflict_key])
                    return "id"
            if task_run.flow_run_id is not None:
                return "natural-key"
            return "id"

        for tr in unique_task_runs:
            tr.resolve_conflict_target(conflict_target(tr))

        fillable = _fillable_columns(db)
        # Sized on how many columns the table has, not how many keys the rows
        # carry: SQLAlchemy renders a bind parameter for every column with a
        # Python-side default, whether the row supplies it or not.
        max_rows = get_max_query_parameters() // len(db.TaskRun.__table__.columns)
        segments = _segment_task_runs_for_upsert(unique_task_runs, fillable, max_rows)

        logger.debug(
            "Partitioned %s task runs into %s upsert statement(s)",
            len(unique_task_runs),
            len(segments),
        )

        canonical_task_run_ids: dict[TaskRunUpsertKey, UUID] = {}

        for segment in segments:
            update_cols = (segment.columns | {"updated"}) - {"id", "created"}
            # sorted so the column order does not vary with the hash seed, which
            # keeps the generated SQL text stable
            insert_cols = sorted(segment.columns)

            # SQLAlchemy takes the statement's column list from the first row and
            # silently drops keys that only later rows carry, so give every row
            # the same keys.
            to_insert = [
                {column: tr.task_run_dict.get(column) for column in insert_cols}
                | {"created": now, "updated": now}
                for tr in segment.rows
            ]

            insert_statement = db.queries.insert(db.TaskRun).values(to_insert)
            index_elements = (
                db.orm.task_run_unique_upsert_columns
                if segment.conflict_target == "natural-key"
                else ["id"]
            )
            # See https://www.postgresql.org/docs/current/sql-insert.html for details on excluded.
            # Idea is excluded.x references the proposed insertion value for column x.
            # `coalesce` undoes the NULL fills, and applies to exactly the columns
            # that were filled. A column every row supplied keeps a plain
            # `excluded.col`, so a row asking to write a real NULL still writes one.
            upsert_statement = insert_statement.on_conflict_do_update(
                index_elements=index_elements,
                set_={
                    col.name: (
                        sa.func.coalesce(
                            getattr(insert_statement.excluded, col.name),
                            getattr(db.TaskRun, col.name),
                        )
                        if col.name in segment.null_filled
                        else getattr(insert_statement.excluded, col.name)
                    )
                    for col in insert_statement.excluded
                    if col.name in update_cols
                },
                where=db.TaskRun.state_timestamp
                < insert_statement.excluded.state_timestamp,
            )
            await session.execute(upsert_statement)

            if segment.conflict_target == "natural-key":
                segment_natural_keys = [
                    (
                        tr.task_run.flow_run_id,
                        tr.task_run.task_key,
                        tr.task_run.dynamic_key,
                    )
                    for tr in segment.rows
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
                        ).in_(segment_natural_keys)
                    )
                )
                for flow_run_id, task_key, dynamic_key, task_run_id in result.all():
                    canonical_task_run_ids[
                        ("natural-key", flow_run_id, task_key, dynamic_key)
                    ] = task_run_id
            else:
                for tr in segment.rows:
                    canonical_task_run_ids[tr.upsert_key] = tr.task_run.id

        for alias_key, canonical_key in upsert_key_aliases.items():
            canonical_task_run_ids[alias_key] = canonical_task_run_ids[canonical_key]

        for tr in all_task_runs:
            task_run = tr.task_run
            canonical_task_run_id = canonical_task_run_ids[tr.upsert_key]
            task_run.id = canonical_task_run_id
            if task_run.state is not None:
                task_run.state.state_details.task_run_id = canonical_task_run_id

        # Insert all task run states - we only coalesce task run updates, not states
        await _insert_task_run_states(session, [tr.task_run for tr in all_task_runs])
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
        while True:
            try:
                await asyncio.sleep(flush_every)
                if queue.qsize():
                    await flush()
            except asyncio.CancelledError:
                return
            except Exception:
                # flush() re-raises when events are dropped; this task is never
                # awaited, so letting that propagate would kill periodic
                # flushing silently and strand queued events (issue #21057)
                logger.exception("Error during periodic flush; continuing")

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
