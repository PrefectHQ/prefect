import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import timedelta
from typing import Any, AsyncGenerator, Dict, Optional
from uuid import UUID

import pendulum
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.logging import get_logger
from prefect.server.database.dependencies import db_injector, provide_database_interface
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.events.ordering import CausalOrdering, EventArrivedEarly
from prefect.server.events.schemas.events import ReceivedEvent
from prefect.server.schemas.core import TaskRun
from prefect.server.schemas.states import State
from prefect.server.utilities.messaging import Message, MessageHandler, create_consumer

logger = get_logger(__name__)


def causal_ordering():
    return CausalOrdering(
        "task-run-recorder",
    )


@db_injector
async def _insert_task_run(
    db: PrefectDBInterface,
    session: AsyncSession,
    task_run: TaskRun,
    task_run_attributes: Dict[str, Any],
):
    await session.execute(
        db.insert(db.TaskRun)
        .values(
            created=pendulum.now("UTC"),
            **task_run_attributes,
        )
        .on_conflict_do_update(
            index_elements=[
                "id",
            ],
            set_={
                "updated": pendulum.now("UTC"),
                **task_run_attributes,
            },
            where=db.TaskRun.state_timestamp < task_run.state.timestamp,
        )
    )


@db_injector
async def _insert_task_run_state(
    db: PrefectDBInterface, session: AsyncSession, task_run: TaskRun
):
    await session.execute(
        db.insert(db.TaskRunState)
        .values(
            created=pendulum.now("UTC"),
            task_run_id=task_run.id,
            **task_run.state.model_dump(),
        )
        .on_conflict_do_nothing(
            index_elements=[
                "id",
            ]
        )
    )


@db_injector
async def _update_task_run_with_state(
    db: PrefectDBInterface,
    session: AsyncSession,
    task_run: TaskRun,
    denormalized_state_attributes: Dict[str, Any],
):
    await session.execute(
        sa.update(db.TaskRun)
        .where(
            db.TaskRun.id == task_run.id,
            sa.or_(
                db.TaskRun.state_timestamp.is_(None),
                db.TaskRun.state_timestamp < task_run.state.timestamp,
            ),
        )
        .values(**denormalized_state_attributes)
    )


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


async def record_task_run_event(event: ReceivedEvent, depth: int = 0):
    db = provide_database_interface()

    async with AsyncExitStack() as stack:
        await stack.enter_async_context(
            (
                causal_ordering().preceding_event_confirmed(
                    record_task_run_event, event, depth=depth
                )
            )
        )

        task_run = task_run_from_event(event)

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

        assert task_run.state

        denormalized_state_attributes = {
            "state_id": task_run.state.id,
            "state_type": task_run.state.type,
            "state_name": task_run.state.name,
            "state_timestamp": task_run.state.timestamp,
        }
        session = await stack.enter_async_context(
            db.session_context(begin_transaction=True)
        )

        await _insert_task_run(session, task_run, task_run_attributes)
        await _insert_task_run_state(session, task_run)
        await _update_task_run_with_state(
            session, task_run, denormalized_state_attributes
        )

    logger.info(
        "Recorded task run state change",
        extra={
            "task_run_id": task_run.id,
            "flow_run_id": task_run.flow_run_id,
            "event_id": event.id,
            "event_follows": event.follows,
            "event": event.event,
            "occurred": event.occurred,
            "current_state_type": task_run.state_type,
            "current_state_name": task_run.state_name,
        },
    )


async def record_lost_follower_task_run_events():
    events = await causal_ordering().get_lost_followers()

    for event in events:
        await record_task_run_event(event)


async def periodically_process_followers(periodic_granularity: timedelta):
    """Periodically process followers that are waiting on a leader event that never arrived"""
    logger.debug(
        "Starting periodically process followers task every %s seconds",
        periodic_granularity.total_seconds(),
    )
    while True:
        try:
            await record_lost_follower_task_run_events()
        except asyncio.CancelledError:
            logger.debug("Periodically process followers task cancelled")
            return
        except Exception:
            logger.exception("Error while processing task-run-recorders followers.")
        finally:
            await asyncio.sleep(periodic_granularity.total_seconds())


@asynccontextmanager
async def consumer(
    periodic_granularity: timedelta = timedelta(seconds=5),
) -> AsyncGenerator[MessageHandler, None]:
    record_lost_followers_task = asyncio.create_task(
        periodically_process_followers(periodic_granularity=periodic_granularity)
    )

    async def message_handler(message: Message):
        event: ReceivedEvent = ReceivedEvent.model_validate_json(message.data)

        if not event.event.startswith("prefect.task-run"):
            return

        if not event.resource.get("prefect.orchestration") == "client":
            return

        logger.info(
            f"Received event: {event.event} with id: {event.id} for resource: {event.resource.get('prefect.resource.id')}"
        )

        try:
            await record_task_run_event(event)
        except EventArrivedEarly:
            # We're safe to ACK this message because it has been parked by the
            # causal ordering mechanism and will be reprocessed when the preceding
            # event arrives.
            pass

    try:
        yield message_handler
    finally:
        try:
            record_lost_followers_task.cancel()
            await record_lost_followers_task
        except asyncio.CancelledError:
            logger.debug("Periodically process followers task cancelled successfully")


class TaskRunRecorder:
    """A service to record task run and task run states from events."""

    name: str = "TaskRunRecorder"

    consumer_task: Optional[asyncio.Task] = None

    def __init__(self):
        self._started_event: Optional[asyncio.Event] = None

    @property
    def started_event(self) -> asyncio.Event:
        if self._started_event is None:
            self._started_event = asyncio.Event()
        return self._started_event

    @started_event.setter
    def started_event(self, value: asyncio.Event) -> None:
        self._started_event = value

    async def start(self):
        assert self.consumer_task is None, "TaskRunRecorder already started"
        self.consumer = create_consumer("events")

        async with consumer() as handler:
            self.consumer_task = asyncio.create_task(self.consumer.run(handler))
            logger.debug("TaskRunRecorder started")
            self.started_event.set()

            try:
                await self.consumer_task
            except asyncio.CancelledError:
                pass

    async def stop(self):
        assert self.consumer_task is not None, "Logger not started"
        self.consumer_task.cancel()
        try:
            await self.consumer_task
        except asyncio.CancelledError:
            pass
        finally:
            self.consumer_task = None
        logger.debug("TaskRunRecorder stopped")
