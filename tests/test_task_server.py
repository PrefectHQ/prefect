import signal
from unittest.mock import AsyncMock, patch

import pytest

from prefect import task
from prefect.client.schemas.objects import TaskRun
from prefect.settings import (
    PREFECT_EXPERIMENTAL_ENABLE_TASK_SCHEDULING,
    temporary_settings,
)
from prefect.task_server import TaskServer, serve


@pytest.fixture(autouse=True)
def enable_task_scheduling_delete_failed_submissions():
    with temporary_settings({PREFECT_EXPERIMENTAL_ENABLE_TASK_SCHEDULING: True}):
        yield


@pytest.fixture
def foo_task():
    @task
    def foo(x):
        return x

    return foo


@pytest.fixture
def async_foo_task():
    @task
    async def async_foo():
        return 1

    return async_foo


@pytest.fixture
async def task_server(foo_task):
    return TaskServer(foo_task, tags={"tag1", "tag2"})


async def test_task_server_basic_context_management(task_server):
    async with task_server:
        assert task_server.started is True
        assert (await task_server._client.hello()).status_code == 200

    assert task_server.started is False
    with pytest.raises(RuntimeError, match="client has been closed"):
        await task_server._client.hello()


async def test_handle_sigterm():
    task_server = TaskServer(...)

    with patch("sys.exit") as mock_exit, patch.object(
        task_server, "_subscribe_to_task_scheduling", new_callable=AsyncMock
    ) as mock_subscribe, patch.object(
        task_server, "stop", new_callable=AsyncMock
    ) as mock_stop:
        await task_server.start()

        mock_subscribe.assert_called_once()

        task_server.handle_sigterm(signal.SIGTERM, None)

        mock_exit.assert_called_once_with(0)
        mock_stop.assert_called_once()


class TestServe:
    @pytest.fixture(autouse=True)
    def mock_task_server_start(self, monkeypatch):
        mock_start = AsyncMock()
        monkeypatch.setattr("prefect.task_server.TaskServer.start", mock_start)
        return mock_start

    async def test_serve_raises_if_task_scheduling_not_enabled(self, foo_task):
        with temporary_settings({PREFECT_EXPERIMENTAL_ENABLE_TASK_SCHEDULING: False}):
            with pytest.raises(
                RuntimeError,
                match="set PREFECT_EXPERIMENTAL_ENABLE_TASK_SCHEDULING to True",
            ):
                await serve(foo_task)

    def test_serve_basic_sync_task(self, foo_task, mock_task_server_start):
        serve(foo_task)
        mock_task_server_start.assert_called_once()

        task_run = foo_task.submit(42)

        assert isinstance(task_run, TaskRun)

        assert task_run.state.is_scheduled()

    async def test_serve_basic_async_task(self, async_foo_task, mock_task_server_start):
        await serve(async_foo_task)
        mock_task_server_start.assert_called_once()

        task_run = await async_foo_task.submit()

        assert isinstance(task_run, TaskRun)

        assert task_run.state.is_scheduled()
