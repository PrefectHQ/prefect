import signal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from prefect import task
from prefect._internal.concurrency.api import create_call, from_async
from prefect.client.schemas.objects import TaskRun
from prefect.settings import (
    PREFECT_EXPERIMENTAL_ENABLE_TASK_SCHEDULING,
    temporary_settings,
)
from prefect.task_server import TaskServer, serve
from prefect.tasks import task_input_hash


@pytest.fixture(autouse=True)
def mock_settings():
    with temporary_settings(
        {
            PREFECT_EXPERIMENTAL_ENABLE_TASK_SCHEDULING: True,
        }
    ):
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
    async def async_foo(x):
        return x

    return async_foo


@pytest.fixture
def mock_task_server_start(monkeypatch):
    monkeypatch.setattr(
        "prefect.task_server.TaskServer.start", mock_start := AsyncMock()
    )
    return mock_start


@pytest.fixture
def task_task_runner_mock():
    task_runner = MagicMock()
    task_runner.start = MagicMock()
    return task_runner


@pytest.fixture
def mock_create_subscription(monkeypatch):
    monkeypatch.setattr(
        "prefect.task_server.TaskServer._subscribe_to_task_scheduling",
        create_subscription := AsyncMock(),
    )
    return create_subscription


async def test_task_server_basic_context_management():
    async with TaskServer(...) as task_server:
        assert task_server.started is True
        assert (await task_server._client.hello()).status_code == 200

    assert task_server.started is False
    with pytest.raises(RuntimeError, match="client has been closed"):
        await task_server._client.hello()


@pytest.mark.usefixtures("mock_create_subscription")
async def test_task_server_uses_same_task_runner_for_all_tasks(
    task_task_runner_mock, foo_task
):
    task_server = TaskServer(foo_task, task_runner=task_task_runner_mock)

    await task_server.start()

    foo_task.submit(x=42)
    foo_task.submit(x=43)

    task_task_runner_mock.start.assert_called_once()


async def test_handle_sigterm(mock_create_subscription):
    task_server = TaskServer(...)

    with patch("sys.exit") as mock_exit, patch.object(
        task_server, "stop", new_callable=AsyncMock
    ) as mock_stop:
        await task_server.start()

        mock_create_subscription.assert_called_once()

        await from_async.call_in_new_thread(
            create_call(task_server.handle_sigterm, signal.SIGTERM, None)
        )

        mock_exit.assert_called_once_with(0)
        mock_stop.assert_called_once()


@pytest.mark.usefixtures("mock_task_server_start")
class TestServe:
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

        task_run = await async_foo_task.submit(42)

        assert isinstance(task_run, TaskRun)

        assert task_run.state.is_scheduled()


async def test_task_server_can_execute_a_single_async_single_task_run(
    async_foo_task, prefect_client
):
    task_server = TaskServer(async_foo_task)

    task_run = await async_foo_task.submit(42)

    await task_server.execute_task_run(task_run)

    updated_task_run = await prefect_client.read_task_run(task_run.id)

    assert updated_task_run.state.is_completed()

    assert await updated_task_run.state.result() == 42


async def test_task_server_can_execute_a_single_sync_single_task_run(
    foo_task, prefect_client
):
    task_server = TaskServer(foo_task)

    task_run = foo_task.submit(42)

    await task_server.execute_task_run(task_run)

    updated_task_run = await prefect_client.read_task_run(task_run.id)

    assert updated_task_run.state.is_completed()

    assert await updated_task_run.state.result() == 42


async def test_task_runs_executed_via_task_server_respects_retry_policy(prefect_client):
    count = 0

    @task(retries=1, persist_result=True)
    def task_with_retry():
        nonlocal count
        if count == 0:
            count += 1
            raise ValueError("maybe next time")

        return count

    task_server = TaskServer(task_with_retry)

    task_run = task_with_retry.submit()

    await task_server.execute_task_run(task_run)

    updated_task_run = await prefect_client.read_task_run(task_run.id)

    assert updated_task_run.state.is_completed()

    assert await updated_task_run.state.result() == 1


async def test_task_run_via_task_server_with_complex_result_type(prefect_client):
    from pydantic.v1 import BaseModel

    class BreakfastSpot(BaseModel):
        name: str
        location: str

    class City(BaseModel):
        name: str
        best_breakfast_spot: BreakfastSpot

    @task(persist_result=True)
    def americas_third_largest_city() -> City:
        return City(
            name="Chicago",
            best_breakfast_spot=BreakfastSpot(
                name="The Bongo Room",
                location="Wicker Park",
            ),
        )

    task_server = TaskServer(americas_third_largest_city)

    task_run = americas_third_largest_city.submit()

    await task_server.execute_task_run(task_run)

    updated_task_run = await prefect_client.read_task_run(task_run.id)

    assert updated_task_run.state.is_completed()

    assert await updated_task_run.state.result() == City(
        name="Chicago",
        best_breakfast_spot=BreakfastSpot(
            name="The Bongo Room",
            location="Wicker Park",
        ),
    )


async def test_task_run_via_task_server_respects_caching(
    async_foo_task, prefect_client, caplog
):
    count = 0

    @task(cache_key_fn=task_input_hash)
    async def task_with_cache(x):
        nonlocal count
        count += 1
        return count

    task_server = TaskServer(task_with_cache)

    task_run = await task_with_cache.submit(42)

    await task_server.execute_task_run(task_run)

    updated_task_run = await prefect_client.read_task_run(task_run.id)

    assert updated_task_run.state.is_completed()

    assert await updated_task_run.state.result() == 1

    new_task_run = await task_with_cache.submit(42)

    with caplog.at_level("INFO"):
        await task_server.execute_task_run(new_task_run)

    new_updated_task_run = await prefect_client.read_task_run(task_run.id)

    assert "Finished in state Cached(type=COMPLETED)" in caplog.text

    assert await new_updated_task_run.state.result() == 1

    assert count == 1
