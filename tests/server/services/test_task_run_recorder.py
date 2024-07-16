import asyncio
from typing import AsyncGenerator
from uuid import UUID

import pendulum
import pytest

from prefect.server.events.schemas.events import ReceivedEvent
from prefect.server.services import task_run_recorder
from prefect.server.utilities.messaging import MessageHandler
from prefect.server.utilities.messaging.memory import MemoryMessage


async def test_start_and_stop_service():
    service = task_run_recorder.TaskRunRecorder()
    service_task = asyncio.create_task(service.start())
    service.started_event = asyncio.Event()

    await service.started_event.wait()
    assert service.consumer_task is not None

    await service.stop()
    assert service.consumer_task is None

    await service_task


@pytest.fixture
async def task_run_recorder_handler() -> AsyncGenerator[MessageHandler, None]:
    async with task_run_recorder.consumer() as handler:
        yield handler


@pytest.fixture
def hello_event() -> ReceivedEvent:
    return ReceivedEvent(
        occurred=pendulum.datetime(2022, 1, 2, 3, 4, 5, 6, "UTC"),
        event="hello",
        resource={
            "prefect.resource.id": "my.resource.id",
        },
        related=[
            {"prefect.resource.id": "related-1", "prefect.resource.role": "role-1"},
            {"prefect.resource.id": "related-2", "prefect.resource.role": "role-1"},
            {"prefect.resource.id": "related-3", "prefect.resource.role": "role-2"},
        ],
        payload={"hello": "world"},
        account=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        workspace=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        received=pendulum.datetime(2022, 2, 3, 4, 5, 6, 7, "UTC"),
        id=UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"),
        follows=UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
    )


@pytest.fixture
def client_orchestrated_task_run_event() -> ReceivedEvent:
    return ReceivedEvent(
        occurred=pendulum.datetime(2022, 1, 2, 3, 4, 5, 6, "UTC"),
        event="prefect.task-run.Running",
        resource={
            "prefect.resource.id": "prefect.task-run.b75b283c-7cd5-439a-b23e-d0c59e78b042",
            "prefect.resource.name": "my_task",
            "prefect.state-message": "",
            "prefect.state-name": "Running",
            "prefect.state-timestamp": pendulum.datetime(
                2022, 1, 2, 3, 4, 5, 6, "UTC"
            ).isoformat(),
            "prefect.state-type": "RUNNING",
            "prefect.orchestration": "client",
        },
        related=[],
        payload={
            "intended": {"from": "PENDING", "to": "RUNNING"},
            "initial_state": {"type": "PENDING", "name": "Pending", "message": ""},
            "validated_state": {"type": "RUNNING", "name": "Running", "message": ""},
        },
        account=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        workspace=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        received=pendulum.datetime(2022, 2, 3, 4, 5, 6, 7, "UTC"),
        id=UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"),
        follows=UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
    )


@pytest.fixture
def server_orchestrated_task_run_event() -> ReceivedEvent:
    return ReceivedEvent(
        occurred=pendulum.datetime(2022, 1, 2, 3, 4, 5, 6, "UTC"),
        event="prefect.task-run.Running",
        resource={
            "prefect.resource.id": "prefect.task-run.b75b283c-7cd5-439a-b23e-d0c59e78b042",
            "prefect.resource.name": "my_task",
            "prefect.state-message": "",
            "prefect.state-name": "Running",
            "prefect.state-timestamp": pendulum.datetime(
                2022, 1, 2, 3, 4, 5, 6, "UTC"
            ).isoformat(),
            "prefect.state-type": "RUNNING",
            "prefect.orchestration": "server",
        },
        related=[],
        payload={
            "intended": {"from": "PENDING", "to": "RUNNING"},
            "initial_state": {"type": "PENDING", "name": "Pending", "message": ""},
            "validated_state": {"type": "RUNNING", "name": "Running", "message": ""},
        },
        account=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        workspace=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        received=pendulum.datetime(2022, 2, 3, 4, 5, 6, 7, "UTC"),
        id=UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"),
        follows=UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
    )


@pytest.fixture
def client_orchestrated_task_run_event_message(
    client_orchestrated_task_run_event: ReceivedEvent,
) -> MemoryMessage:
    return MemoryMessage(
        data=client_orchestrated_task_run_event.model_dump_json().encode(),
        attributes={},
    )


@pytest.fixture
def server_orchestrated_task_run_event_message(
    server_orchestrated_task_run_event: ReceivedEvent,
) -> MemoryMessage:
    return MemoryMessage(
        data=server_orchestrated_task_run_event.model_dump_json().encode(),
        attributes={},
    )


@pytest.fixture
def hello_event_message(hello_event: ReceivedEvent) -> MemoryMessage:
    return MemoryMessage(
        data=hello_event.model_dump_json().encode(),
        attributes={},
    )


async def test_handle_client_orchestrated_task_run_event(
    task_run_recorder_handler: MessageHandler,
    client_orchestrated_task_run_event: ReceivedEvent,
    client_orchestrated_task_run_event_message: MemoryMessage,
    caplog: pytest.LogCaptureFixture,
):
    with caplog.at_level("INFO"):
        await task_run_recorder_handler(client_orchestrated_task_run_event_message)

    assert "Received event" in caplog.text
    assert str(client_orchestrated_task_run_event.id) in caplog.text


async def test_skip_non_task_run_event(
    task_run_recorder_handler: MessageHandler,
    hello_event: ReceivedEvent,
    hello_event_message: MemoryMessage,
    caplog: pytest.LogCaptureFixture,
):
    with caplog.at_level("INFO"):
        await task_run_recorder_handler(hello_event_message)

    assert "Received event" not in caplog.text
    assert str(hello_event.id) not in caplog.text


async def test_skip_server_side_orchestrated_task_run(
    task_run_recorder_handler: MessageHandler,
    server_orchestrated_task_run_event: ReceivedEvent,
    server_orchestrated_task_run_event_message: MemoryMessage,
    caplog: pytest.LogCaptureFixture,
):
    with caplog.at_level("INFO"):
        await task_run_recorder_handler(server_orchestrated_task_run_event_message)

    assert "Received event" not in caplog.text
    assert str(server_orchestrated_task_run_event.id) not in caplog.text
