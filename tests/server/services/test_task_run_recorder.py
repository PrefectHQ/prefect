import asyncio
from datetime import timedelta
from itertools import permutations
from typing import AsyncGenerator
from uuid import UUID

import pendulum
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.events.schemas.events import ReceivedEvent
from prefect.server.models.flow_runs import create_flow_run
from prefect.server.models.task_run_states import (
    read_task_run_state,
    read_task_run_states,
)
from prefect.server.models.task_runs import read_task_run
from prefect.server.schemas.core import FlowRun, TaskRunPolicy
from prefect.server.schemas.states import StateDetails, StateType
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


def message(event: ReceivedEvent) -> MemoryMessage:
    return MemoryMessage(
        data=event.model_dump_json().encode(),
        attributes={},
    )


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
            "task_run": {
                "name": "my_task",
                "task_key": "add-0bf8d992",
                "dynamic_key": "add-0bf8d992-4bb2bae02a7f4ac6afaf493d28a57d96",
                "empirical_policy": {
                    "max_retries": 0,
                    "retry_delay_seconds": 0,
                    "retries": 0,
                    "retry_delay": 0,
                },
                "tags": [],
                "task_inputs": {"x": [], "y": []},
                "run_count": 1,
                "flow_run_run_count": 0,
                "expected_start_time": pendulum.datetime(
                    2022, 1, 2, 3, 4, 5, 5, "UTC"
                ).isoformat(),
                "start_time": pendulum.datetime(
                    2022, 1, 2, 3, 4, 5, 5, "UTC"
                ).isoformat(),
                "end_time": pendulum.datetime(
                    2022, 1, 2, 3, 4, 5, 6, "UTC"
                ).isoformat(),
                "total_run_time": 0.002024,
                "estimated_run_time": 0,
                "estimated_start_time_delta": 0,
            },
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


async def test_handle_client_orchestrated_task_run_event(
    task_run_recorder_handler: MessageHandler,
    client_orchestrated_task_run_event: ReceivedEvent,
    caplog: pytest.LogCaptureFixture,
):
    with caplog.at_level("DEBUG"):
        await task_run_recorder_handler(message(client_orchestrated_task_run_event))

    assert "Recorded task run state change" in caplog.text
    assert str(client_orchestrated_task_run_event.id) in caplog.text


async def test_skip_non_task_run_event(
    task_run_recorder_handler: MessageHandler,
    hello_event: ReceivedEvent,
    caplog: pytest.LogCaptureFixture,
):
    with caplog.at_level("DEBUG"):
        await task_run_recorder_handler(message(hello_event))

    assert "Received event" not in caplog.text
    assert str(hello_event.id) not in caplog.text


async def test_skip_server_side_orchestrated_task_run(
    task_run_recorder_handler: MessageHandler,
    server_orchestrated_task_run_event: ReceivedEvent,
    caplog: pytest.LogCaptureFixture,
):
    with caplog.at_level("INFO"):
        await task_run_recorder_handler(message(server_orchestrated_task_run_event))

    assert "Received event" not in caplog.text
    assert str(server_orchestrated_task_run_event.id) not in caplog.text


@pytest.fixture
async def flow_run(session: AsyncSession, flow):
    flow_run = await create_flow_run(
        session=session,
        flow_run=FlowRun(
            id=UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
            flow_id=flow.id,
        ),
    )
    await session.commit()
    return flow_run


@pytest.fixture
def pending_event(flow_run) -> ReceivedEvent:
    occurred = pendulum.datetime(2024, 1, 1, 0, 0, 0, 0, "UTC")
    return ReceivedEvent(
        occurred=occurred,
        event="prefect.task-run.Pending",
        resource={
            "prefect.resource.id": "prefect.task-run.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "prefect.resource.name": "my_task",
            "prefect.state-message": "",
            "prefect.state-type": "PENDING",
            "prefect.state-name": "Pending",
            "prefect.state-timestamp": occurred.isoformat(),
            "prefect.orchestration": "client",
        },
        related=[
            {
                "prefect.resource.id": "prefect.flow-run.ffffffff-ffff-ffff-ffff-ffffffffffff",
                "prefect.resource.role": "flow-run",
            },
        ],
        payload={
            "intended": {"from": None, "to": "PENDING"},
            "initial_state": None,
            "validated_state": {
                "type": "PENDING",
                "name": "Pending",
                "message": "Hi there!",
                "state_details": {
                    "pause_reschedule": False,
                    "untrackable_result": False,
                },
                "data": None,
            },
            "task_run": {
                "task_key": "my_task-abcdefg",
                "dynamic_key": "1",
                "empirical_policy": {
                    "max_retries": 2,
                    "retries": 3,
                    "retry_delay": 4,
                    "retry_delay_seconds": 5.0,
                },
                "expected_start_time": "2024-01-01T00:00:00Z",
                "estimated_start_time_delta": 0.1,
                "name": "my_task",
                "tags": [
                    "tag-1",
                    "tag-2",
                ],
                "task_inputs": {
                    "x": [{"input_type": "parameter", "name": "x"}],
                    "y": [{"input_type": "parameter", "name": "y"}],
                },
            },
        },
        received=occurred + timedelta(seconds=1),
        follows=None,
        id=UUID("11111111-1111-1111-1111-111111111111"),
    )


@pytest.fixture
def running_event(flow_run) -> ReceivedEvent:
    occurred = pendulum.datetime(2024, 1, 1, 0, 1, 0, 0, "UTC")
    return ReceivedEvent(
        occurred=occurred,
        event="prefect.task-run.Running",
        resource={
            "prefect.resource.id": "prefect.task-run.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "prefect.resource.name": "my_task",
            "prefect.state-message": "",
            "prefect.state-type": "RUNNING",
            "prefect.state-name": "Running",
            "prefect.state-timestamp": occurred.isoformat(),
            "prefect.orchestration": "client",
        },
        related=[
            {
                "prefect.resource.id": "prefect.flow-run.ffffffff-ffff-ffff-ffff-ffffffffffff",
                "prefect.resource.role": "flow-run",
            },
        ],
        payload={
            "intended": {"from": "PENDING", "to": "RUNNING"},
            "initial_state": {
                "type": "PENDING",
                "name": "Pending",
                "message": "",
                "state_details": {
                    "pause_reschedule": False,
                    "untrackable_result": False,
                },
            },
            "validated_state": {
                "type": "RUNNING",
                "name": "Running",
                "message": "Weeeeeee look at me go!",
                "state_details": {
                    "pause_reschedule": False,
                    "untrackable_result": False,
                },
                "data": None,
            },
            "task_run": {
                "task_key": "my_task-abcdefg",
                "dynamic_key": "1",
                "empirical_policy": {
                    "max_retries": 2,
                    "retries": 3,
                    "retry_delay": 4,
                    "retry_delay_seconds": 5.0,
                },
                "estimated_run_time": 6.0,
                "expected_start_time": "2024-01-01T00:00:00Z",
                "estimated_start_time_delta": 0.1,
                "flow_run_run_count": 7,
                "name": "my_task",
                "run_count": 8,
                "start_time": "2024-01-01T00:01:00Z",
                "tags": [
                    "tag-1",
                    "tag-2",
                ],
                "task_inputs": {
                    "x": [{"input_type": "parameter", "name": "x"}],
                    "y": [{"input_type": "parameter", "name": "y"}],
                },
                "total_run_time": 9.0,
            },
        },
        received=occurred + timedelta(seconds=1),
        follows=UUID("11111111-1111-1111-1111-111111111111"),
        id=UUID("22222222-2222-2222-2222-222222222222"),
    )


@pytest.fixture
def completed_event(flow_run) -> ReceivedEvent:
    occurred = pendulum.datetime(2024, 1, 1, 0, 2, 0, 0, "UTC")
    return ReceivedEvent(
        occurred=occurred,
        event="prefect.task-run.Completed",
        resource={
            "prefect.resource.id": "prefect.task-run.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "prefect.resource.name": "my_task",
            "prefect.state-message": "",
            "prefect.state-type": "COMPLETED",
            "prefect.state-name": "Completed",
            "prefect.state-timestamp": occurred.isoformat(),
            "prefect.orchestration": "client",
        },
        related=[
            {
                "prefect.resource.id": "prefect.flow-run.ffffffff-ffff-ffff-ffff-ffffffffffff",
                "prefect.resource.role": "flow-run",
            },
        ],
        payload={
            "intended": {"from": "RUNNING", "to": "COMPLETED"},
            "initial_state": {
                "type": "RUNNING",
                "name": "Running",
                "message": "",
                "state_details": {
                    "pause_reschedule": False,
                    "untrackable_result": False,
                },
            },
            "validated_state": {
                "type": "COMPLETED",
                "name": "Completed",
                "message": "Stick a fork in me, I'm done",
                "state_details": {
                    "pause_reschedule": False,
                    "untrackable_result": False,
                },
                "data": {"type": "unpersisted"},
            },
            "task_run": {
                # required fields
                "task_key": "my_task-abcdefg",
                "dynamic_key": "1",
                # Only set the end_time, to test partial updates
                "end_time": "2024-01-01T00:02:00Z",
            },
        },
        received=occurred + timedelta(seconds=1),
        follows=UUID("22222222-2222-2222-2222-222222222222"),
        id=UUID("33333333-3333-3333-3333-333333333333"),
    )


async def test_recording_single_event(
    session: AsyncSession,
    pending_event: ReceivedEvent,
    task_run_recorder_handler: MessageHandler,
):
    pending_transition_time = pendulum.datetime(2024, 1, 1, 0, 0, 0, 0, "UTC")
    assert pending_event.occurred == pending_transition_time

    await task_run_recorder_handler(message(pending_event))

    task_run = await read_task_run(
        session=session,
        task_run_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
    )

    assert task_run

    assert task_run.id == UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    assert task_run.name == "my_task"
    assert task_run.flow_run_id == UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
    assert task_run.task_key == "my_task-abcdefg"
    assert task_run.dynamic_key == "1"
    assert task_run.tags == ["tag-1", "tag-2"]

    assert task_run.flow_run_run_count == 0
    assert task_run.run_count == 0
    assert task_run.total_run_time == timedelta(0)
    assert task_run.task_inputs == {
        "x": [{"input_type": "parameter", "name": "x"}],
        "y": [{"input_type": "parameter", "name": "y"}],
    }
    assert task_run.empirical_policy == TaskRunPolicy(
        max_retries=2,
        retries=3,
        retry_delay=4,
        retry_delay_seconds=5.0,
    )

    assert task_run.expected_start_time == pending_transition_time
    assert task_run.start_time is None
    assert task_run.end_time is None

    assert task_run.state_id == UUID("11111111-1111-1111-1111-111111111111")
    assert task_run.state_timestamp == pending_transition_time
    assert task_run.state_type == StateType.PENDING
    assert task_run.state_name == "Pending"
    assert task_run.state_timestamp == pending_transition_time

    state = await read_task_run_state(
        session=session,
        task_run_state_id=UUID("11111111-1111-1111-1111-111111111111"),
    )

    assert state

    assert state.id == UUID("11111111-1111-1111-1111-111111111111")
    assert state.type == StateType.PENDING
    assert state.name == "Pending"
    assert state.message == "Hi there!"
    assert state.timestamp == pending_transition_time
    assert state.state_details == StateDetails(
        flow_run_id=UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
        task_run_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        pause_reschedule=False,
        untrackable_result=False,
    )


async def test_updates_task_run_on_subsequent_state_changes(
    session: AsyncSession,
    pending_event: ReceivedEvent,
    running_event: ReceivedEvent,
    task_run_recorder_handler: MessageHandler,
):
    pending_transition_time = pendulum.datetime(2024, 1, 1, 0, 0, 0, 0, "UTC")
    assert pending_event.occurred == pending_transition_time

    running_transition_time = pendulum.datetime(2024, 1, 1, 0, 1, 0, 0, "UTC")
    assert running_event.occurred == running_transition_time

    await task_run_recorder_handler(message(pending_event))
    await task_run_recorder_handler(message(running_event))

    task_run = await read_task_run(
        session=session,
        task_run_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
    )

    assert task_run

    assert task_run.id == UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    assert task_run.name == "my_task"
    assert task_run.flow_run_id == UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
    assert task_run.task_key == "my_task-abcdefg"
    assert task_run.dynamic_key == "1"
    assert task_run.tags == ["tag-1", "tag-2"]

    assert task_run.flow_run_run_count == 7
    assert task_run.run_count == 8
    assert task_run.total_run_time == timedelta(seconds=9)
    assert task_run.task_inputs == {
        "x": [{"input_type": "parameter", "name": "x"}],
        "y": [{"input_type": "parameter", "name": "y"}],
    }
    assert task_run.empirical_policy == TaskRunPolicy(
        max_retries=2,
        retries=3,
        retry_delay=4,
        retry_delay_seconds=5.0,
    )

    assert task_run.expected_start_time == pending_transition_time
    assert task_run.start_time == running_transition_time
    assert task_run.end_time is None

    assert task_run.state_id == UUID("22222222-2222-2222-2222-222222222222")
    assert task_run.state_timestamp == running_transition_time
    assert task_run.state_type == StateType.RUNNING
    assert task_run.state_name == "Running"
    assert task_run.state_timestamp == running_transition_time

    state = await read_task_run_state(
        session=session,
        task_run_state_id=UUID("22222222-2222-2222-2222-222222222222"),
    )

    assert state

    assert state.id == UUID("22222222-2222-2222-2222-222222222222")
    assert state.type == StateType.RUNNING
    assert state.name == "Running"
    assert state.message == "Weeeeeee look at me go!"
    assert state.timestamp == running_transition_time
    assert state.state_details == StateDetails(
        flow_run_id=UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
        task_run_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        pause_reschedule=False,
        untrackable_result=False,
    )


async def test_updates_only_fields_that_are_set(
    session: AsyncSession,
    pending_event: ReceivedEvent,
    running_event: ReceivedEvent,
    completed_event: ReceivedEvent,
    task_run_recorder_handler: MessageHandler,
):
    pending_transition_time = pendulum.datetime(2024, 1, 1, 0, 0, 0, 0, "UTC")
    assert pending_event.occurred == pending_transition_time

    running_transition_time = pendulum.datetime(2024, 1, 1, 0, 1, 0, 0, "UTC")
    assert running_event.occurred == running_transition_time

    completed_transition_time = pendulum.datetime(2024, 1, 1, 0, 2, 0, 0, "UTC")
    assert completed_event.occurred == completed_transition_time

    await task_run_recorder_handler(message(pending_event))
    await task_run_recorder_handler(message(running_event))
    await task_run_recorder_handler(message(completed_event))

    task_run = await read_task_run(
        session=session,
        task_run_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
    )

    assert task_run

    # The Completed transition here in the tests only sets the end_time, so we
    # would expect all the other values to reflect what was set in the Running
    # transition.

    assert task_run.id == UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    assert task_run.name == "my_task"
    assert task_run.flow_run_id == UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
    assert task_run.task_key == "my_task-abcdefg"
    assert task_run.dynamic_key == "1"
    assert task_run.tags == ["tag-1", "tag-2"]

    assert task_run.flow_run_run_count == 7
    assert task_run.run_count == 8
    assert task_run.total_run_time == timedelta(seconds=9)
    assert task_run.task_inputs == {
        "x": [{"input_type": "parameter", "name": "x"}],
        "y": [{"input_type": "parameter", "name": "y"}],
    }
    assert task_run.empirical_policy == TaskRunPolicy(
        max_retries=2,
        retries=3,
        retry_delay=4,
        retry_delay_seconds=5.0,
    )

    assert task_run.expected_start_time == pending_transition_time
    assert task_run.start_time == running_transition_time
    assert task_run.end_time == completed_transition_time

    assert task_run.state_id == UUID("33333333-3333-3333-3333-333333333333")
    assert task_run.state_type == StateType.COMPLETED
    assert task_run.state_name == "Completed"
    assert task_run.state_timestamp == completed_transition_time

    state = await read_task_run_state(
        session=session,
        task_run_state_id=UUID("33333333-3333-3333-3333-333333333333"),
    )

    assert state

    assert state.id == UUID("33333333-3333-3333-3333-333333333333")
    assert state.type == StateType.COMPLETED
    assert state.name == "Completed"
    assert state.message == "Stick a fork in me, I'm done"
    assert state.timestamp == completed_transition_time
    assert state.state_details == StateDetails(
        flow_run_id=UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
        task_run_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        pause_reschedule=False,
        untrackable_result=False,
    )


async def test_updates_task_run_on_out_of_order_state_change(
    session: AsyncSession,
    pending_event: ReceivedEvent,
    running_event: ReceivedEvent,
    completed_event: ReceivedEvent,
    task_run_recorder_handler: MessageHandler,
):
    pending_transition_time = pendulum.datetime(2024, 1, 1, 0, 0, 0, 0, "UTC")
    assert pending_event.occurred == pending_transition_time

    running_transition_time = pendulum.datetime(2024, 1, 1, 0, 1, 0, 0, "UTC")
    assert running_event.occurred == running_transition_time

    # force the completed event to an older time so that it won't update the task run
    completed_event.occurred = running_transition_time - timedelta(seconds=1)
    completed_transition_time = completed_event.occurred

    await task_run_recorder_handler(message(pending_event))
    await task_run_recorder_handler(message(running_event))
    await task_run_recorder_handler(message(completed_event))

    task_run = await read_task_run(
        session=session,
        task_run_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
    )

    assert task_run

    # We expect that the task run will still be showing the denormalized info from
    # the prior state change, not the completed state change, because the timestamp
    # of the completed state is older.  This isn't a sensible thing to happen in
    # the wild, but we want to be explicit about the behavior when that happens...

    assert task_run.id == UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    assert task_run.name == "my_task"
    assert task_run.flow_run_id == UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
    assert task_run.task_key == "my_task-abcdefg"
    assert task_run.dynamic_key == "1"
    assert task_run.tags == ["tag-1", "tag-2"]

    assert task_run.flow_run_run_count == 7
    assert task_run.run_count == 8
    assert task_run.total_run_time == timedelta(seconds=9)
    assert task_run.task_inputs == {
        "x": [{"input_type": "parameter", "name": "x"}],
        "y": [{"input_type": "parameter", "name": "y"}],
    }
    assert task_run.empirical_policy == TaskRunPolicy(
        max_retries=2,
        retries=3,
        retry_delay=4,
        retry_delay_seconds=5.0,
    )

    assert task_run.expected_start_time == pending_transition_time
    assert task_run.start_time == running_transition_time
    assert task_run.end_time is None

    assert task_run.state_id == UUID("22222222-2222-2222-2222-222222222222")
    assert task_run.state_timestamp == running_transition_time
    assert task_run.state_type == StateType.RUNNING
    assert task_run.state_name == "Running"
    assert task_run.state_timestamp == running_transition_time
    # ...however, the new completed state _is_ recorded

    state = await read_task_run_state(
        session=session,
        task_run_state_id=UUID("33333333-3333-3333-3333-333333333333"),
    )

    assert state

    assert state.id == UUID("33333333-3333-3333-3333-333333333333")
    assert state.type == StateType.COMPLETED
    assert state.name == "Completed"
    assert state.message == "Stick a fork in me, I'm done"
    assert state.timestamp == completed_transition_time
    assert state.state_details == StateDetails(
        flow_run_id=UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
        task_run_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        pause_reschedule=False,
        untrackable_result=False,
    )


@pytest.mark.parametrize(
    "event_order",
    list(permutations(["PENDING", "RUNNING", "COMPLETED"])),
    ids=lambda x: "->".join(x),
)
async def test_task_run_recorder_handles_all_out_of_order_permutations(
    session: AsyncSession,
    pending_event: ReceivedEvent,
    running_event: ReceivedEvent,
    completed_event: ReceivedEvent,
    task_run_recorder_handler: MessageHandler,
    event_order: tuple,
):
    # Set up event times
    base_time = pendulum.datetime(2024, 1, 1, 0, 0, 0, 0, "UTC")
    pending_event.occurred = base_time
    running_event.occurred = base_time.add(minutes=1)
    completed_event.occurred = base_time.add(minutes=2)

    event_map = {
        "PENDING": pending_event,
        "RUNNING": running_event,
        "COMPLETED": completed_event,
    }

    # Process events in the specified order
    for event_name in event_order:
        await task_run_recorder_handler(message(event_map[event_name]))

    # Verify the task run always has the "final" state
    task_run = await read_task_run(
        session=session,
        task_run_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
    )

    assert task_run
    assert task_run.state_type == StateType.COMPLETED
    assert task_run.state_name == "Completed"
    assert task_run.state_timestamp == completed_event.occurred

    # Verify all states are recorded
    states = await read_task_run_states(session, task_run.id)
    assert len(states) == 3

    state_types = set(state.type for state in states)
    assert state_types == {StateType.PENDING, StateType.RUNNING, StateType.COMPLETED}
