from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import timedelta
from typing import TYPE_CHECKING, AsyncGenerator, NoReturn, Optional
from uuid import UUID

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


@db_injector
async def _insert_task_run_state(
    db: PrefectDBInterface, session: AsyncSession, task_run: TaskRun
):
    if TYPE_CHECKING:
        assert task_run.state is not None
    await session.execute(
        db.queries.insert(db.TaskRunState)
        .values(
            created=prefect.types._datetime.now("UTC"),
            task_run_id=task_run.id,
            **task_run.state.model_dump(),
        )
        .on_conflict_do_nothing(
            index_elements=[
                "id",
            ]
        )
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


async def record_task_run_event(event: ReceivedEvent, depth: int = 0) -> None:
    async with AsyncExitStack() as stack:
        try:
            await stack.enter_async_context(
                get_task_run_recorder_causal_ordering().preceding_event_confirmed(
                    record_task_run_event, event, depth=depth
                )
            )
        except EventArrivedEarly:
            # We're safe to ACK this message because it has been parked by the
            # causal ordering mechanism and will be reprocessed when the preceding
            # event arrives.
            return

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

        db = provide_database_interface()
        async with db.session_context() as session:
            # Combine all attributes for a single atomic operation
            all_attributes = {
                **task_run_attributes,
                **denormalized_state_attributes,
                "created": prefect.types._datetime.now("UTC"),
            }

            # Single atomic INSERT ... ON CONFLICT DO UPDATE
            await session.execute(
                db.queries.insert(db.TaskRun)
                .values(**all_attributes)
                .on_conflict_do_update(
                    index_elements=["id"],
                    set_={
                        "updated": prefect.types._datetime.now("UTC"),
                        **task_run_attributes,
                        **denormalized_state_attributes,
                    },
                    where=db.TaskRun.state_timestamp < task_run.state.timestamp,
                )
            )

            # Still need to insert the task_run_state separately
            await _insert_task_run_state(session, task_run)

            await session.commit()

        logger.debug(
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


async def record_lost_follower_task_run_events() -> None:
    ordering = get_task_run_recorder_causal_ordering()
    events = await ordering.get_lost_followers()

    for event in events:
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


@asynccontextmanager
async def consumer() -> AsyncGenerator[MessageHandler, None]:
    record_lost_followers_task = asyncio.create_task(
        periodically_process_followers(periodic_granularity=timedelta(seconds=5))
    )

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

        await record_task_run_event(event)

    try:
        yield message_handler
    finally:
        record_lost_followers_task.cancel()
        try:
            await record_lost_followers_task
        except asyncio.CancelledError:
            logger.info("Periodically process followers task cancelled successfully")


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

    async def start(self) -> NoReturn:
        assert self.consumer_task is None, "TaskRunRecorder already started"
        self.consumer: Consumer = create_consumer(
            "events",
            group="task-run-recorder",
            name=generate_unique_consumer_name("task-run-recorder"),
        )

        async with consumer() as handler:
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
