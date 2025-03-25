import asyncio
import os
import socket
from collections import Counter
from contextlib import contextmanager
from typing import Generator, List
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient, WebSocketTestSession

from prefect.client.schemas import TaskRun
from prefect.server import models
from prefect.server.api import task_runs
from prefect.server.schemas import states as server_states
from prefect.server.schemas.core import TaskRun as ServerTaskRun


@pytest.fixture
def reset_task_queues() -> Generator[None, None, None]:
    task_runs.TaskQueue.reset()

    yield

    task_runs.TaskQueue.reset()


@pytest.fixture
def client_id() -> str:
    return f"{socket.gethostname()}-{os.getpid()}"


def auth_dance(socket: WebSocketTestSession):
    socket.send_json({"type": "auth", "token": None})
    response = socket.receive_json()
    assert response == {"type": "auth_success"}


def test_auth_dance(app: FastAPI):
    with authenticated_socket(app):
        assert True


@contextmanager
def authenticated_socket(app: FastAPI) -> Generator[WebSocketTestSession, None, None]:
    socket: WebSocketTestSession
    with TestClient(app).websocket_connect(
        "/api/task_runs/subscriptions/scheduled",
        subprotocols=["prefect"],
    ) as socket:
        auth_dance(socket)
        yield socket


def drain(
    socket: WebSocketTestSession, expecting: int = 1, quit: bool = True
) -> List[TaskRun]:
    messages = []

    while len(messages) < expecting:
        message = socket.receive_json()
        messages.append(TaskRun.model_validate(message))

        if quit and len(messages) == expecting:
            socket.send_json({"type": "quit"})
        else:
            socket.send_json({"type": "ack"})

    return messages


@pytest.fixture
async def taskA_run1(reset_task_queues) -> ServerTaskRun:
    queued = ServerTaskRun(
        id=uuid4(),
        flow_run_id=None,
        task_key="mytasks.taskA",
        dynamic_key="mytasks.taskA-1",
    )
    await task_runs.TaskQueue.enqueue(queued)
    return queued


def test_receiving_task_run(app: FastAPI, taskA_run1: TaskRun, client_id: str):
    with authenticated_socket(app) as socket:
        socket.send_json(
            {"type": "subscribe", "keys": ["mytasks.taskA"], "client_id": client_id}
        )

        (received,) = drain(socket)

    assert received.id == taskA_run1.id


@pytest.fixture
async def taskA_run2(reset_task_queues) -> ServerTaskRun:
    queued = ServerTaskRun(
        flow_run_id=None,
        task_key="mytasks.taskA",
        dynamic_key="mytasks.taskA-1",
    )
    await task_runs.TaskQueue.enqueue(queued)
    return queued


def test_acknowledging_between_each_run(
    app: FastAPI, taskA_run1: TaskRun, taskA_run2: TaskRun, client_id: str
):
    with authenticated_socket(app) as socket:
        socket.send_json(
            {"type": "subscribe", "keys": ["mytasks.taskA"], "client_id": client_id}
        )

        (first, second) = drain(socket, 2)

        assert first.task_key == "mytasks.taskA"
        assert second.task_key == "mytasks.taskA"
        assert {first.id, second.id} == {taskA_run1.id, taskA_run2.id}


@pytest.fixture
async def mixed_bag_of_tasks(reset_task_queues) -> None:
    await task_runs.TaskQueue.enqueue(
        TaskRun(  # type: ignore
            id=uuid4(),
            flow_run_id=None,
            task_key="mytasks.taskA",
            dynamic_key="mytasks.taskA-1",
        )
    )

    await task_runs.TaskQueue.enqueue(
        TaskRun(  # type: ignore
            id=uuid4(),
            flow_run_id=None,
            task_key="mytasks.taskA",
            dynamic_key="mytasks.taskA-1",
        )
    )

    # this one should not be delivered
    await task_runs.TaskQueue.enqueue(
        TaskRun(  # type: ignore
            id=uuid4(),
            flow_run_id=None,
            task_key="nope.not.this.one",
            dynamic_key="nope.not.this.one-1",
        )
    )

    await task_runs.TaskQueue.enqueue(
        TaskRun(  # type: ignore
            id=uuid4(),
            flow_run_id=None,
            task_key="other_tasks.taskB",
            dynamic_key="other_tasks.taskB-1",
        )
    )


def test_server_only_delivers_tasks_for_subscribed_keys(
    app: FastAPI,
    mixed_bag_of_tasks: List[TaskRun],
    client_id: str,
):
    with authenticated_socket(app) as socket:
        socket.send_json(
            {
                "type": "subscribe",
                "keys": ["mytasks.taskA", "other_tasks.taskB"],
                "client_id": client_id,
            }
        )

        received = drain(socket, 3)

    assert Counter(r.task_key for r in received) == {
        "mytasks.taskA": 2,
        "other_tasks.taskB": 1,
    }


@pytest.fixture
async def ten_task_A_runs(reset_task_queues) -> List[ServerTaskRun]:
    queued: List[ServerTaskRun] = []
    for _ in range(10):
        run = ServerTaskRun(
            id=uuid4(),
            flow_run_id=None,
            task_key="mytasks.taskA",
            dynamic_key="mytasks.taskA-1",
        )
        await task_runs.TaskQueue.enqueue(run)
        queued.append(run)
    return queued


def test_only_one_socket_gets_each_task_run(
    app: FastAPI, ten_task_A_runs: List[TaskRun], client_id: str
):
    received1: List[TaskRun] = []
    received2: List[TaskRun] = []

    with authenticated_socket(app) as first, authenticated_socket(app) as second:
        first.send_json(
            {"type": "subscribe", "keys": ["mytasks.taskA"], "client_id": client_id}
        )
        second.send_json(
            {"type": "subscribe", "keys": ["mytasks.taskA"], "client_id": client_id}
        )

        for i in range(5):
            received1 += drain(first, 1, quit=(i == 4))
            received2 += drain(second, 1, quit=(i == 4))

    received1_ids = {r.id for r in received1}
    received2_ids = {r.id for r in received2}

    # Each socket should have gotten some runs, and each run should have only been
    # sent to one of the sockets
    assert received1_ids, "Each socket should have gotten at least one run"
    assert received2_ids, "Each socket should have gotten at least one run"
    assert received1_ids.isdisjoint(received2_ids)

    queued_ids = {r.id for r in ten_task_A_runs}
    received_ids = received1_ids | received2_ids

    # While the asynchrony of this test means we won't necessarily get all 10,
    # we should be getting at least 5 task runs
    assert 5 <= len(received_ids) <= len(ten_task_A_runs)

    assert received_ids.issubset(queued_ids)


def test_server_redelivers_unacknowledged_runs(
    app: FastAPI, taskA_run1: TaskRun, client_id: str
):
    with authenticated_socket(app) as socket:
        socket.send_json(
            {"type": "subscribe", "keys": ["mytasks.taskA"], "client_id": client_id}
        )

        received = socket.receive_json()
        assert received["id"] == str(taskA_run1.id)

        # but importantly, disconnect without acknowledging the ping
        socket.close()

    with authenticated_socket(app) as socket:
        socket.send_json(
            {"type": "subscribe", "keys": ["mytasks.taskA"], "client_id": client_id}
        )

        (received,) = drain(socket)
        assert received.id == taskA_run1.id


@pytest.fixture
async def preexisting_runs(
    session: AsyncSession, reset_task_queues
) -> List[ServerTaskRun]:
    stored_runA = ServerTaskRun.model_validate(
        await models.task_runs.create_task_run(
            session,
            ServerTaskRun(
                flow_run_id=None,
                task_key="mytasks.taskA",
                dynamic_key="mytasks.taskA-1",
                state=server_states.Scheduled(state_details={"deferred": True}),
            ),
        )
    )

    stored_runB = ServerTaskRun.model_validate(
        await models.task_runs.create_task_run(
            session,
            ServerTaskRun(
                flow_run_id=None,
                task_key="mytasks.taskA",
                dynamic_key="mytasks.taskA-2",
                state=server_states.Scheduled(state_details={"deferred": True}),
            ),
        )
    )

    await session.commit()

    return [stored_runA, stored_runB]


def test_server_restores_scheduled_task_runs_at_startup(
    app: FastAPI,
    preexisting_runs: List[TaskRun],
    client_id: str,
):
    with authenticated_socket(app) as socket:
        socket.send_json(
            {"type": "subscribe", "keys": ["mytasks.taskA"], "client_id": client_id}
        )

        received = drain(socket, expecting=len(preexisting_runs))

        assert {r.id for r in received} == {r.id for r in preexisting_runs}


class TestQueueLimit:
    async def test_task_queue_scheduled_size_limit(self):
        task_key = "test_limit"
        max_scheduled_size = 2

        task_runs.TaskQueue.configure_task_key(
            task_key, scheduled_size=max_scheduled_size, retry_size=1
        )

        queue = task_runs.TaskQueue.for_key(task_key)

        for _ in range(max_scheduled_size):
            task_run = ServerTaskRun(
                id=uuid4(),
                flow_run_id=None,
                task_key=task_key,
                dynamic_key=f"{task_key}-1",
            )
            await queue.put(task_run)

        with (
            patch("asyncio.sleep", return_value=None),
            pytest.raises(asyncio.TimeoutError),
        ):
            extra_task_run = ServerTaskRun(
                id=uuid4(),
                flow_run_id=None,
                task_key=task_key,
                dynamic_key=f"{task_key}-2",
            )
            await asyncio.wait_for(queue.put(extra_task_run), timeout=0.01)

        assert queue._scheduled_queue.qsize() == max_scheduled_size, (
            "Queue size should be at its configured limit"
        )

    async def test_task_queue_retry_size_limit(self):
        task_key = "test_retry_limit"
        max_retry_size = 1

        task_runs.TaskQueue.configure_task_key(
            task_key, scheduled_size=2, retry_size=max_retry_size
        )

        queue = task_runs.TaskQueue.for_key(task_key)

        task_run = ServerTaskRun(
            id=uuid4(), flow_run_id=None, task_key=task_key, dynamic_key=f"{task_key}-1"
        )
        await queue.retry(task_run)

        with (
            patch("asyncio.sleep", return_value=None),
            pytest.raises(asyncio.TimeoutError),
        ):
            extra_task_run = ServerTaskRun(
                id=uuid4(),
                flow_run_id=None,
                task_key=task_key,
                dynamic_key=f"{task_key}-2",
            )
            await asyncio.wait_for(queue.retry(extra_task_run), timeout=0.01)

        assert queue._retry_queue.qsize() == max_retry_size, (
            "Retry queue size should be at its configured limit"
        )


@pytest.fixture
def reset_tracker():
    models.task_workers.task_worker_tracker.reset()
    yield
    models.task_workers.task_worker_tracker.reset()


class TestTaskWorkerTracking:
    @pytest.mark.parametrize(
        "num_connections,task_keys,expected_workers",
        [
            (2, ["taskA", "taskB"], 1),
            (1, ["taskA", "taskB", "taskC"], 1),
        ],
        ids=["multiple_connections_single_worker", "single_connection_multiple_tasks"],
    )
    @pytest.mark.usefixtures("reset_tracker")
    async def test_task_worker_basic_tracking(
        self,
        app,
        num_connections,
        task_keys,
        expected_workers,
        client_id,
        test_client,
    ):
        for _ in range(num_connections):
            with authenticated_socket(app) as socket:
                socket.send_json(
                    {"type": "subscribe", "keys": task_keys, "client_id": client_id}
                )

            response = test_client.post("api/task_workers/filter")
            assert response.status_code == 200
            tracked_workers = response.json()
            assert len(tracked_workers) == expected_workers

            for worker in tracked_workers:
                assert worker["identifier"] == client_id
                assert set(worker["task_keys"]) == set(task_keys)
