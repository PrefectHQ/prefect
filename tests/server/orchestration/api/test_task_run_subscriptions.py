import os
import socket
from collections import Counter
from contextlib import contextmanager
from typing import Generator, List
from uuid import uuid4

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient, WebSocketTestSession

from prefect.client.schemas import TaskRun
from prefect.server import models
from prefect.server.schemas.core import TaskRun as ServerTaskRun
from prefect.server.task_delivery import TaskRunDeliveryManager

pytestmark = pytest.mark.clear_db


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
def authenticated_socket(
    app_or_client: FastAPI | TestClient,
) -> Generator[WebSocketTestSession, None, None]:
    socket: WebSocketTestSession
    if isinstance(app_or_client, TestClient):
        client = app_or_client
        with client.websocket_connect(
            "/api/task_runs/subscriptions/scheduled",
            subprotocols=["prefect"],
        ) as socket:
            auth_dance(socket)
            yield socket
    else:
        with TestClient(app_or_client) as client:
            with client.websocket_connect(
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


def enqueue(socket: WebSocketTestSession, *task_runs_to_enqueue: ServerTaskRun) -> None:
    with socket.portal_factory() as portal:
        for task_run in task_runs_to_enqueue:
            portal.call(TaskRunDeliveryManager.active().publish, task_run)


@pytest.fixture
def taskA_run1() -> ServerTaskRun:
    return ServerTaskRun(
        id=uuid4(),
        flow_run_id=None,
        task_key="mytasks.taskA",
        dynamic_key="mytasks.taskA-1",
    )


def test_receiving_task_run(app: FastAPI, taskA_run1: TaskRun, client_id: str):
    with authenticated_socket(app) as socket:
        socket.send_json(
            {"type": "subscribe", "keys": ["mytasks.taskA"], "client_id": client_id}
        )
        enqueue(socket, taskA_run1)

        (received,) = drain(socket)

    assert received.id == taskA_run1.id


@pytest.fixture
def taskA_run2() -> ServerTaskRun:
    return ServerTaskRun(
        flow_run_id=None,
        task_key="mytasks.taskA",
        dynamic_key="mytasks.taskA-1",
    )


def test_acknowledging_between_each_run(
    app: FastAPI, taskA_run1: TaskRun, taskA_run2: TaskRun, client_id: str
):
    with authenticated_socket(app) as socket:
        socket.send_json(
            {"type": "subscribe", "keys": ["mytasks.taskA"], "client_id": client_id}
        )
        enqueue(socket, taskA_run1, taskA_run2)

        (first, second) = drain(socket, 2)

        assert first.task_key == "mytasks.taskA"
        assert second.task_key == "mytasks.taskA"
        assert {first.id, second.id} == {taskA_run1.id, taskA_run2.id}


@pytest.fixture
def mixed_bag_of_tasks() -> list[ServerTaskRun]:
    return [
        ServerTaskRun(
            id=uuid4(),
            flow_run_id=None,
            task_key="mytasks.taskA",
            dynamic_key="mytasks.taskA-1",
        ),
        ServerTaskRun(
            id=uuid4(),
            flow_run_id=None,
            task_key="mytasks.taskA",
            dynamic_key="mytasks.taskA-1",
        ),
        # this one should not be delivered
        ServerTaskRun(
            id=uuid4(),
            flow_run_id=None,
            task_key="nope.not.this.one",
            dynamic_key="nope.not.this.one-1",
        ),
        ServerTaskRun(
            id=uuid4(),
            flow_run_id=None,
            task_key="other_tasks.taskB",
            dynamic_key="other_tasks.taskB-1",
        ),
    ]


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
        enqueue(socket, *mixed_bag_of_tasks)

        received = drain(socket, 3)

    assert Counter(r.task_key for r in received) == {
        "mytasks.taskA": 2,
        "other_tasks.taskB": 1,
    }


@pytest.fixture
def ten_task_A_runs() -> List[ServerTaskRun]:
    queued: List[ServerTaskRun] = []
    for _ in range(10):
        run = ServerTaskRun(
            id=uuid4(),
            flow_run_id=None,
            task_key="mytasks.taskA",
            dynamic_key="mytasks.taskA-1",
        )
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
        enqueue(first, *ten_task_A_runs)

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
    with TestClient(app) as client:
        with authenticated_socket(client) as socket:
            socket.send_json(
                {"type": "subscribe", "keys": ["mytasks.taskA"], "client_id": client_id}
            )
            enqueue(socket, taskA_run1)

            received = socket.receive_json()
            assert received["id"] == str(taskA_run1.id)

            # Disconnect without acknowledging the task run.
            socket.close()

        with authenticated_socket(client) as socket:
            socket.send_json(
                {"type": "subscribe", "keys": ["mytasks.taskA"], "client_id": client_id}
            )

            (received,) = drain(socket)
            assert received.id == taskA_run1.id


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
    ):
        with TestClient(app) as client:
            for _ in range(num_connections):
                with authenticated_socket(client) as socket:
                    socket.send_json(
                        {"type": "subscribe", "keys": task_keys, "client_id": client_id}
                    )

                response = client.post("api/task_workers/filter")
                assert response.status_code == 200
                tracked_workers = response.json()
                assert len(tracked_workers) == expected_workers

                for worker in tracked_workers:
                    assert worker["identifier"] == client_id
                    assert set(worker["task_keys"]) == set(task_keys)
