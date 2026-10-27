import asyncio
import threading
import uuid
from collections.abc import Generator
from typing import Self
from unittest.mock import MagicMock, patch

import httpx
import pytest
from websockets.exceptions import ConnectionClosedError

from prefect import task
from prefect.client.schemas.filters import TaskRunFilter
from prefect.states import Completed, State
from prefect.task_engine import run_task_async
from prefect.task_runs import TaskRunWaiter


class TestTaskRunWaiter:
    @pytest.fixture(autouse=True)
    def teardown(self):
        yield

        TaskRunWaiter.instance().stop()

    def test_instance_returns_singleton(self):
        assert TaskRunWaiter.instance() is TaskRunWaiter.instance()

    def test_instance_returns_instance_after_stop(self):
        instance = TaskRunWaiter.instance()
        instance.stop()
        assert TaskRunWaiter.instance() is not instance

    @pytest.mark.timeout(20)
    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_wait_for_task_run(self, prefect_client, emitting_events_pipeline):
        """This test will fail with a timeout error if waiting is not working correctly."""

        @task
        async def test_task():
            await asyncio.sleep(1)

        task_run_id = uuid.uuid4()
        asyncio.create_task(run_task_async(task=test_task, task_run_id=task_run_id))

        await TaskRunWaiter.wait_for_task_run(task_run_id)

        await emitting_events_pipeline.process_events()

        task_run = await prefect_client.read_task_run(task_run_id)
        assert task_run.state.is_completed()

    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_wait_for_task_run_with_timeout(self):
        @task
        async def test_task():
            await asyncio.sleep(5)

        task_run_id = uuid.uuid4()
        run = asyncio.create_task(
            run_task_async(task=test_task, task_run_id=task_run_id)
        )

        await TaskRunWaiter.wait_for_task_run(task_run_id, timeout=1)

        # TaskRunWaiter stopped waiting before the task finished
        assert not run.done()
        await run

    @pytest.mark.timeout(20)
    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_non_singleton_mode(self, prefect_client, emitting_events_pipeline):
        waiter = TaskRunWaiter()
        assert waiter is not TaskRunWaiter.instance()

        @task
        async def test_task():
            await asyncio.sleep(1)

        task_run_id = uuid.uuid4()
        asyncio.create_task(run_task_async(task=test_task, task_run_id=task_run_id))

        await waiter.wait_for_task_run(task_run_id)

        await emitting_events_pipeline.process_events()

        task_run = await prefect_client.read_task_run(task_run_id)
        assert task_run.state.is_completed()

        waiter.stop()

    @pytest.mark.timeout(20)
    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_handles_concurrent_task_runs(
        self, prefect_client, emitting_events_pipeline
    ):
        @task
        async def fast_task():
            await asyncio.sleep(1)

        @task
        async def slow_task():
            await asyncio.sleep(5)

        task_run_id_1 = uuid.uuid4()
        task_run_id_2 = uuid.uuid4()

        asyncio.create_task(run_task_async(task=fast_task, task_run_id=task_run_id_1))
        asyncio.create_task(run_task_async(task=slow_task, task_run_id=task_run_id_2))

        await TaskRunWaiter.wait_for_task_run(task_run_id_1)

        await emitting_events_pipeline.process_events()

        task_run_1 = await prefect_client.read_task_run(task_run_id_1)
        task_run_2 = await prefect_client.read_task_run(task_run_id_2)

        assert task_run_1.state.is_completed()
        assert not task_run_2.state.is_completed()

        await TaskRunWaiter.wait_for_task_run(task_run_id_2)

        await emitting_events_pipeline.process_events()

        task_run_1 = await prefect_client.read_task_run(task_run_id_1)
        task_run_2 = await prefect_client.read_task_run(task_run_id_2)

        assert task_run_1.state.is_completed()
        assert task_run_2.state.is_completed()


class EndingEventStream:
    """Stands in for the events subscriber; every connection ends at once."""

    def __init__(self, error: Exception | None = None, setup_error: bool = False):
        self.error = error
        self.setup_error = setup_error
        self.factory_kwargs: dict[str, object] = {}

    def __call__(self, **kwargs: object) -> "EndingEventStream":
        self.factory_kwargs = kwargs
        return self

    async def __aenter__(self) -> Self:
        if self.setup_error:
            raise ConnectionError("down")
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        pass

    def __aiter__(self) -> "EndingEventStream":
        return self

    async def __anext__(self):
        if self.error is not None:
            raise self.error
        raise StopAsyncIteration


class FakeTaskRunsAPI:
    """Stands in for the API client, serving final task run states."""

    def __init__(self):
        self.final_states: dict[uuid.UUID, State] = {}
        self.failing = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        pass

    async def read_task_runs(
        self, task_run_filter: TaskRunFilter, limit: int
    ) -> list[MagicMock]:
        if self.failing:
            raise httpx.ConnectError("down")
        assert task_run_filter.id is not None and task_run_filter.id.any_ is not None
        return [
            MagicMock(id=task_run_id, state=self.final_states[task_run_id])
            for task_run_id in task_run_filter.id.any_
            if task_run_id in self.final_states
        ]


class TestTaskRunWaiterRecovery:
    @pytest.fixture(autouse=True)
    def fresh_waiter(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr("prefect.task_runs.TASK_RUN_POLLING_INTERVAL_SECONDS", 0.01)
        monkeypatch.setattr("prefect.task_runs.reconnect_delay", lambda attempt: 0.01)
        monkeypatch.setattr(
            "prefect._internal._observation_delivery.reconnect_delay",
            lambda attempt: 0.01,
        )
        TaskRunWaiter.instance().stop()
        yield
        TaskRunWaiter.instance().stop()

    @pytest.fixture
    def api(self) -> Generator[FakeTaskRunsAPI, None, None]:
        api = FakeTaskRunsAPI()
        with patch("prefect.task_runs.get_client", return_value=api):
            yield api

    @pytest.mark.timeout(20)
    @pytest.mark.parametrize(
        "stream",
        [
            EndingEventStream(),
            EndingEventStream(error=ConnectionClosedError(None, None)),
        ],
        ids=["clean-close", "failure"],
    )
    async def test_wait_returns_after_stream_ends(
        self, api: FakeTaskRunsAPI, stream: EndingEventStream
    ):
        task_run_id = uuid.uuid4()
        with patch("prefect.task_runs.get_events_subscriber", stream):
            waiting = asyncio.create_task(TaskRunWaiter.wait_for_task_run(task_run_id))
            await asyncio.sleep(0.1)
            assert not waiting.done()

            final_state = Completed()
            api.final_states[task_run_id] = final_state

            assert await asyncio.wait_for(waiting, timeout=10) is final_state

        assert stream.factory_kwargs["reconnection_attempts"] == 0

    @pytest.mark.timeout(20)
    async def test_done_callback_runs_once_after_stream_ends(
        self, api: FakeTaskRunsAPI
    ):
        task_run_id = uuid.uuid4()
        called = threading.Event()
        callback = MagicMock(side_effect=lambda: called.set())
        with patch("prefect.task_runs.get_events_subscriber", EndingEventStream()):
            TaskRunWaiter.add_done_callback(task_run_id, callback)
            api.final_states[task_run_id] = Completed()

            assert await asyncio.to_thread(called.wait, 10)
            await asyncio.sleep(0.1)

        callback.assert_called_once_with()

    @pytest.mark.timeout(20)
    async def test_restarts_after_stream_and_api_are_unavailable(
        self, api: FakeTaskRunsAPI, caplog: pytest.LogCaptureFixture
    ):
        task_run_id = uuid.uuid4()
        api.failing = True
        stream = EndingEventStream(setup_error=True)
        with patch("prefect.task_runs.get_events_subscriber", stream):
            waiting = asyncio.create_task(TaskRunWaiter.wait_for_task_run(task_run_id))
            async with asyncio.timeout(10):
                while "TaskRunWaiter lost both" not in caplog.text:
                    await asyncio.sleep(0.01)
            assert not waiting.done()

            final_state = Completed()
            api.final_states[task_run_id] = final_state
            api.failing = False

            assert await asyncio.wait_for(waiting, timeout=10) is final_state
