import asyncio
import json
from asyncio import AbstractEventLoop, CancelledError, gather
from collections import Counter
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Callable, List
from unittest import mock
from unittest.mock import patch
from uuid import uuid4

import anyio
import httpx
import pytest
import websockets
from sqlalchemy.ext.asyncio import AsyncSession
from uvicorn import Config, Server

from prefect.client.schemas import TaskRun
from prefect.server import models
from prefect.server.api import task_runs
from prefect.server.api.server import create_app
from prefect.settings import (
    PREFECT_API_SERVICES_CANCELLATION_CLEANUP_ENABLED,
    PREFECT_API_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED,
    PREFECT_API_SERVICES_LATE_RUNS_ENABLED,
    PREFECT_API_SERVICES_PAUSE_EXPIRATIONS_ENABLED,
    PREFECT_API_SERVICES_SCHEDULER_ENABLED,
    PREFECT_EXPERIMENTAL_ENABLE_TASK_SCHEDULING,
    PREFECT_SERVER_ANALYTICS_ENABLED,
    temporary_settings,
)
from prefect.states import Scheduled

pytestmark = pytest.mark.skip(
    "Task run subscription tests are temporarily disabled until we can reduce "
    "their noise level"
)


@pytest.fixture(scope="module", autouse=True)
def services_disabled() -> None:
    with temporary_settings(
        {
            PREFECT_SERVER_ANALYTICS_ENABLED: False,
            PREFECT_API_SERVICES_SCHEDULER_ENABLED: False,
            PREFECT_API_SERVICES_LATE_RUNS_ENABLED: False,
            PREFECT_API_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED: False,
            PREFECT_API_SERVICES_PAUSE_EXPIRATIONS_ENABLED: False,
            PREFECT_API_SERVICES_CANCELLATION_CLEANUP_ENABLED: False,
            PREFECT_EXPERIMENTAL_ENABLE_TASK_SCHEDULING: True,
        }
    ):
        yield


@pytest.fixture(scope="module", autouse=True)
def disable_signal_handlers():
    """Disable uvicorn's signal handlers to avoid conflicts with pytest's"""
    with mock.patch.object(Server, "install_signal_handlers", lambda self: None):
        yield


@asynccontextmanager
async def running_prefect_server(
    event_loop: AbstractEventLoop, port: int
) -> AsyncGenerator[str, None]:
    api_url = f"http://localhost:{port}/api"

    app = create_app(ignore_cache=True)
    server = Server(Config(app=app, host="127.0.0.1", port=port))
    server_task = event_loop.create_task(server.serve())

    # Wait for the server to be ready
    async with httpx.AsyncClient() as client:
        response = None
        with anyio.move_on_after(20):
            while True:
                try:
                    response = await client.get(api_url + "/health")
                except httpx.ConnectError:
                    pass
                else:
                    if response.status_code == 200:
                        break
                await anyio.sleep(0.1)
        if response:
            response.raise_for_status()
        if not response:
            raise RuntimeError("Timed out while attempting to connect to test API")

    try:
        yield api_url
    finally:
        server_task.cancel()
        try:
            await server_task
        except CancelledError:
            pass


@pytest.fixture(scope="module")
async def prefect_server(
    unused_tcp_port_factory: Callable[[], int],
    event_loop: AbstractEventLoop,
) -> AsyncGenerator[str, None]:
    async with running_prefect_server(event_loop, unused_tcp_port_factory()) as api_url:
        yield api_url


@pytest.fixture(autouse=True)
async def reset_task_queues():
    task_runs.TaskQueue.reset()

    yield

    task_runs.TaskQueue.reset()


@pytest.fixture
async def socket_url(prefect_server: str) -> str:
    return prefect_server.replace("http", "ws", 1)


async def auth_dance(socket: websockets.WebSocketClientProtocol) -> None:
    await socket.send(json.dumps({"type": "auth", "token": None}))
    response = await socket.recv()
    assert json.loads(response) == {"type": "auth_success"}

    await socket.send(
        json.dumps(
            {
                "type": "subscribe",
                "keys": ["mytasks.taskA", "other_tasks.taskB"],
            }
        )
    )


@pytest.fixture
async def authenticated_socket(
    socket_url: str,
) -> AsyncGenerator[websockets.WebSocketClientProtocol, None]:
    async with websockets.connect(
        f"{socket_url}/task_runs/subscriptions/scheduled",
        subprotocols=["prefect"],
    ) as socket:
        await auth_dance(socket)
        yield socket


async def test_receiving_task_run(
    authenticated_socket: websockets.WebSocketClientProtocol,
):
    queued = TaskRun(
        id=uuid4(),
        flow_run_id=None,
        task_key="mytasks.taskA",
        dynamic_key="mytasks.taskA-1",
    )
    await task_runs.TaskQueue.enqueue(queued)

    received = TaskRun.parse_raw(await authenticated_socket.recv())

    assert received.id == queued.id


async def test_receiving_ping_between_each_run(
    authenticated_socket: websockets.WebSocketClientProtocol,
):
    await task_runs.TaskQueue.enqueue(
        TaskRun(
            id=uuid4(),
            flow_run_id=None,
            task_key="mytasks.taskA",
            dynamic_key="mytasks.taskA-1",
        )
    )
    await task_runs.TaskQueue.enqueue(
        TaskRun(
            id=uuid4(),
            flow_run_id=None,
            task_key="mytasks.taskA",
            dynamic_key="mytasks.taskA-1",
        )
    )

    run = json.loads(await authenticated_socket.recv())
    assert run["task_key"] == "mytasks.taskA"

    ping = json.loads(await authenticated_socket.recv())
    assert ping["type"] == "ping"

    await authenticated_socket.send(json.dumps({"type": "pong"}))

    run = json.loads(await authenticated_socket.recv())
    assert run["task_key"] == "mytasks.taskA"

    ping = json.loads(await authenticated_socket.recv())
    assert ping["type"] == "ping"

    await authenticated_socket.send(json.dumps({"type": "pong"}))


async def drain(
    socket: websockets.WebSocketClientProtocol, timeout: float = 1
) -> List[TaskRun]:
    messages = []

    with anyio.move_on_after(timeout):
        while True:
            message = json.loads(await socket.recv())
            if message.get("type") == "ping":
                await socket.send(json.dumps({"type": "pong"}))
                continue
            messages.append(TaskRun.parse_obj(message))

    return messages


async def test_server_only_delivers_tasks_for_subscribed_keys(
    authenticated_socket: websockets.WebSocketClientProtocol,
):
    await task_runs.TaskQueue.enqueue(
        TaskRun(
            id=uuid4(),
            flow_run_id=None,
            task_key="mytasks.taskA",
            dynamic_key="mytasks.taskA-1",
        )
    )

    await task_runs.TaskQueue.enqueue(
        TaskRun(
            id=uuid4(),
            flow_run_id=None,
            task_key="mytasks.taskA",
            dynamic_key="mytasks.taskA-1",
        )
    )

    # this one should not be delivered
    await task_runs.TaskQueue.enqueue(
        TaskRun(
            id=uuid4(),
            flow_run_id=None,
            task_key="nope.not.this.one",
            dynamic_key="nope.not.this.one-1",
        )
    )

    await task_runs.TaskQueue.enqueue(
        TaskRun(
            id=uuid4(),
            flow_run_id=None,
            task_key="other_tasks.taskB",
            dynamic_key="other_tasks.taskB-1",
        )
    )

    received = await drain(authenticated_socket)

    assert Counter(r.task_key for r in received) == {
        "mytasks.taskA": 2,
        "other_tasks.taskB": 1,
    }


@pytest.fixture
async def another_socket(
    socket_url: str,
) -> AsyncGenerator[websockets.WebSocketClientProtocol, None]:
    async with websockets.connect(
        f"{socket_url}/task_runs/subscriptions/scheduled",
        subprotocols=["prefect"],
    ) as socket:
        await auth_dance(socket)
        yield socket


async def test_only_one_socket_gets_each_task_run(
    authenticated_socket: websockets.WebSocketClientProtocol,
    another_socket: websockets.WebSocketClientProtocol,
):
    queued: List[TaskRun] = []
    for _ in range(10):
        run = TaskRun(
            id=uuid4(),
            flow_run_id=None,
            task_key="mytasks.taskA",
            dynamic_key="mytasks.taskA-1",
        )
        await task_runs.TaskQueue.enqueue(run)
        queued.append(run)

    received1, received2 = await gather(
        drain(authenticated_socket),
        drain(another_socket),
    )

    received1_ids = {r.id for r in received1}
    received2_ids = {r.id for r in received2}

    # Each socket should have gotten some runs, and each run should have only been
    # sent to one of the sockets
    assert received1_ids, "Each socket should have gotten at least one run"
    assert received2_ids, "Each socket should have gotten at least one run"
    assert received1_ids.isdisjoint(received2_ids)

    queued_ids = {r.id for r in queued}
    received_ids = received1_ids | received2_ids

    # While the asynchrony of this test means we won't necessarily get all 10,
    # we should be getting at least 5 task runs
    assert 5 <= len(received_ids) <= len(queued)

    assert received_ids.issubset(queued_ids)


async def test_server_redelivers_unacknowledged_runs(socket_url: str):
    run = TaskRun(
        id=uuid4(),
        flow_run_id=None,
        task_key="mytasks.taskA",
        dynamic_key="mytasks.taskA-1",
    )
    await task_runs.TaskQueue.enqueue(run)

    async with websockets.connect(
        f"{socket_url}/task_runs/subscriptions/scheduled",
        subprotocols=["prefect"],
    ) as socket1:
        await auth_dance(socket1)

        received = json.loads(await socket1.recv())
        assert received["id"] == str(run.id)

        ping = json.loads(await socket1.recv())
        assert ping["type"] == "ping"

        # but importantly, disconnect without acknowledging the ping

    async with websockets.connect(
        f"{socket_url}/task_runs/subscriptions/scheduled",
        subprotocols=["prefect"],
    ) as socket2:
        await auth_dance(socket2)

        received = json.loads(await socket2.recv())
        assert received["id"] == str(run.id)


async def test_server_restores_scheduled_task_runs_at_startup(
    session: AsyncSession, event_loop: AbstractEventLoop, unused_tcp_port: int
):
    stored_run = TaskRun(
        id=uuid4(),
        flow_run_id=None,
        task_key="mytasks.taskA",
        dynamic_key="mytasks.taskA-1",
        state=Scheduled(),
    )
    await models.task_runs.create_task_run(session, stored_run)
    await session.commit()

    async with running_prefect_server(event_loop, unused_tcp_port) as api_url:
        socket_url = api_url.replace("http", "ws", 1)

        async with websockets.connect(
            f"{socket_url}/task_runs/subscriptions/scheduled",
            subprotocols=["prefect"],
        ) as socket:
            await auth_dance(socket)

            received = json.loads(await socket.recv())
            assert received["id"] == str(stored_run.id)


class TestQueueLimit:
    async def test_task_queue_scheduled_size_limit(self):
        task_key = "test_limit"
        max_scheduled_size = 2

        task_runs.TaskQueue.configure_task_key(
            task_key, scheduled_size=max_scheduled_size, retry_size=1
        )

        queue = task_runs.TaskQueue.for_key(task_key)

        for _ in range(max_scheduled_size):
            task_run = TaskRun(
                id=uuid4(),
                flow_run_id=None,
                task_key=task_key,
                dynamic_key=f"{task_key}-1",
            )
            await queue.put(task_run)

        with patch("asyncio.sleep", return_value=None), pytest.raises(
            asyncio.TimeoutError
        ):
            extra_task_run = TaskRun(
                id=uuid4(),
                flow_run_id=None,
                task_key=task_key,
                dynamic_key=f"{task_key}-2",
            )
            await asyncio.wait_for(queue.put(extra_task_run), timeout=0.01)

        assert (
            queue._scheduled_queue.qsize() == max_scheduled_size
        ), "Queue size should be at its configured limit"

    async def test_task_queue_retry_size_limit(self):
        task_key = "test_retry_limit"
        max_retry_size = 1

        task_runs.TaskQueue.configure_task_key(
            task_key, scheduled_size=2, retry_size=max_retry_size
        )

        queue = task_runs.TaskQueue.for_key(task_key)

        task_run = TaskRun(
            id=uuid4(), flow_run_id=None, task_key=task_key, dynamic_key=f"{task_key}-1"
        )
        await queue.retry(task_run)

        with patch("asyncio.sleep", return_value=None), pytest.raises(
            asyncio.TimeoutError
        ):
            extra_task_run = TaskRun(
                id=uuid4(),
                flow_run_id=None,
                task_key=task_key,
                dynamic_key=f"{task_key}-2",
            )
            await asyncio.wait_for(queue.retry(extra_task_run), timeout=0.01)

        assert (
            queue._retry_queue.qsize() == max_retry_size
        ), "Retry queue size should be at its configured limit"
