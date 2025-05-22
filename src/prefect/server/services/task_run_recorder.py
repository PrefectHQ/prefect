from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, NoReturn, Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.logging import get_logger
from prefect.server.database import (
    PrefectDBInterface,
    db_injector,
    provide_database_interface,
)
from prefect.server.events.ordering import CausalOrdering, EventArrivedEarly
from prefect.server.events.schemas.events import ReceivedEvent
from prefect.server.schemas.core import TaskRun
from prefect.server.schemas.states import State
from prefect.server.services.base import RunInAllServers, Service
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
from prefect.types._datetime import now

if TYPE_CHECKING:
    import logging

logger: "logging.Logger" = get_logger(__name__)


def causal_ordering() -> CausalOrdering:
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
    if TYPE_CHECKING:
        assert task_run.state is not None
    await session.execute(
        db.queries.insert(db.TaskRun)
        .values(
            created=now("UTC"),
            **task_run_attributes,
        )
        .on_conflict_do_update(
            index_elements=[
                "id",
            ],
            set_={
                "updated": now("UTC"),
                **task_run_attributes,
            },
            where=db.TaskRun.state_timestamp < task_run.state.timestamp,
        )
    )


@db_injector
async def _insert_task_run_state(
    db: PrefectDBInterface, session: AsyncSession, task_run: TaskRun
):
    if TYPE_CHECKING:
        assert task_run.state is not None
    await session.execute(
        db.queries.insert(db.TaskRunState)
        .values(
            created=now("UTC"),
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
    if TYPE_CHECKING:
        assert task_run.state is not None
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


async def record_task_run_event(event: ReceivedEvent) -> None:
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
        await _insert_task_run(session, task_run, task_run_attributes)
        await _insert_task_run_state(session, task_run)
        await _update_task_run_with_state(
            session, task_run, denormalized_state_attributes
        )
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


@asynccontextmanager
async def consumer() -> AsyncGenerator[MessageHandler, None]:
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

        try:
            await record_task_run_event(event)
        except EventArrivedEarly:
            # We're safe to ACK this message because it has been parked by the
            # causal ordering mechanism and will be reprocessed when the preceding
            # event arrives.
            pass

    yield message_handler


class TaskRunRecorder(RunInAllServers, Service):
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
