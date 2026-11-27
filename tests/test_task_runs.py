import asyncio
import threading
import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Self
from unittest.mock import MagicMock, patch

import httpx
import pytest
from websockets.exceptions import ConnectionClosedError

from prefect import task
from prefect.client.schemas.filters import TaskRunFilter
from prefect.client.schemas.sorting import TaskRunSort
from prefect.events import emit_event
from prefect.server.events.pipeline import EventsPipeline
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
    async def test_wait_for_task_run_in_cached_state(
        self, emitting_events_pipeline: EventsPipeline
    ):
        """
        A cached task run finishes in a `Cached` state, so its final event is
        `prefect.task-run.Cached`. Regression test for
        https://github.com/PrefectHQ/prefect/issues/15427
        """
        cache_key = str(uuid.uuid4())

        @task(cache_key_fn=lambda *args, **kwargs: cache_key, persist_result=True)
        async def test_task() -> int:
            return 42

        await run_task_async(task=test_task)

        task_run_id = uuid.uuid4()
        await run_task_async(task=test_task, task_run_id=task_run_id)
        # Store the events so the waiter receives them when it subscribes
        await emitting_events_pipeline.process_events()

        state = await TaskRunWaiter.wait_for_task_run(task_run_id)

        assert state is not None
        assert state.is_completed()
        assert state.name == "Cached"

    @pytest.mark.timeout(20)
    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_wait_for_task_run_keeps_waiting_through_retries(
        self, emitting_events_pipeline: EventsPipeline
    ):
        """
        A retried task run passes through `AwaitingRetry` and `Retrying`, which are
        not final states.
        """
        attempts = 0

        @task(retries=1, retry_delay_seconds=2)
        async def test_task() -> int:
            nonlocal attempts
            attempts += 1
            await asyncio.sleep(1)
            if attempts == 1:
                raise ValueError("fail the first attempt")
            return 42

        task_run_id = uuid.uuid4()
        run = asyncio.create_task(
            run_task_async(task=test_task, task_run_id=task_run_id)
        )

        state = await TaskRunWaiter.wait_for_task_run(task_run_id)

        assert state is not None
        assert state.is_completed()
        assert await run == 42

    @pytest.mark.timeout(20)
    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_wait_for_task_run_in_completed_state_named_pending(
        self, emitting_events_pipeline: EventsPipeline
    ):
        """
        A final state can have the name of a non-final state type, so its event is
        `prefect.task-run.Pending`.
        """

        @task
        async def test_task() -> State:
            return Completed(name="Pending")

        task_run_id = uuid.uuid4()
        await run_task_async(task=test_task, task_run_id=task_run_id)
        # Store the events so the waiter receives them when it subscribes
        await emitting_events_pipeline.process_events()

        state = await TaskRunWaiter.wait_for_task_run(task_run_id)

        assert state is not None
        assert state.is_completed()
        assert state.name == "Pending"

    @pytest.mark.timeout(20)
    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_wait_for_task_run_with_state_type_only_in_payload(
        self, emitting_events_pipeline: EventsPipeline
    ):
        """
        A final state event without a `prefect.state-type` label still wakes the
        waiter through the state type in its payload.
        """
        task_run_id = uuid.uuid4()
        emit_event(
            event="prefect.task-run.Completed",
            resource={"prefect.resource.id": f"prefect.task-run.{task_run_id}"},
            payload={"validated_state": {"type": "COMPLETED", "name": "Completed"}},
            id=uuid.uuid4(),
        )
        # Store the event so the waiter receives it when it subscribes
        await emitting_events_pipeline.process_events()

        state = await TaskRunWaiter.wait_for_task_run(task_run_id)

        assert state is not None
        assert state.is_completed()

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


class RecoveringEventStream(EndingEventStream):
    """Stay open without replaying events once the server is available again."""

    def __init__(self) -> None:
        super().__init__(setup_error=True)
        self.connected = threading.Event()

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        self.connected.set()
        return self

    async def __anext__(self) -> None:
        await asyncio.Event().wait()


class FakeTaskRunsAPI:
    """Stands in for the API client, serving final task run states."""

    def __init__(self):
        self.final_states: dict[uuid.UUID, State] = {}
        self.failing = False
        self.failures_remaining = 0
        self.page_size = 200
        self.max_filter_ids: int | None = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        pass

    async def read_task_runs(
        self, task_run_filter: TaskRunFilter, sort: TaskRunSort, offset: int = 0
    ) -> list[MagicMock]:
        if self.failing or self.failures_remaining:
            self.failures_remaining = max(0, self.failures_remaining - 1)
            raise httpx.ConnectError("down")
        assert task_run_filter.id is not None and task_run_filter.id.any_ is not None
        if self.max_filter_ids is not None:
            assert len(task_run_filter.id.any_) <= self.max_filter_ids
        matching = [
            task_run_id
            for task_run_id in sorted(task_run_filter.id.any_, reverse=True)
            if task_run_id in self.final_states
        ]
        return [
            MagicMock(id=task_run_id, state=self.final_states[task_run_id])
            for task_run_id in matching[offset : offset + self.page_size]
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

    @pytest.mark.timeout(20)
    @pytest.mark.parametrize("transient_api_failures", [0, 1])
    async def test_restarted_stream_reconciles_older_completions(
        self,
        api: FakeTaskRunsAPI,
        monkeypatch: pytest.MonkeyPatch,
        transient_api_failures: int,
    ):
        waited_id, callback_id = uuid.uuid4(), uuid.uuid4()
        old_timestamp = datetime.now(UTC) - timedelta(minutes=2)
        final_state = Completed(timestamp=old_timestamp)
        api.final_states.update(
            {waited_id: final_state, callback_id: Completed(timestamp=old_timestamp)}
        )
        api.failing = True
        stream = RecoveringEventStream()
        called = threading.Event()
        callback = MagicMock(side_effect=called.set)

        def restore_transports(attempt: int) -> float:
            # The outer backoff runs only after delivery has exhausted polling.
            stream.setup_error = False
            api.failing = False
            api.failures_remaining = transient_api_failures
            return 0

        monkeypatch.setattr("prefect.task_runs.reconnect_delay", restore_transports)
        with patch("prefect.task_runs.get_events_subscriber", stream):
            TaskRunWaiter.add_done_callback(callback_id, callback)
            waiting = asyncio.create_task(TaskRunWaiter.wait_for_task_run(waited_id))
            try:
                assert await asyncio.to_thread(stream.connected.wait, 10)
                assert await asyncio.wait_for(waiting, timeout=5) is final_state
                assert await asyncio.to_thread(called.wait, 5)
                callback.assert_called_once_with()
                assert api.failures_remaining == 0
            finally:
                waiting.cancel()
                await asyncio.gather(waiting, return_exceptions=True)

    async def test_polling_batches_ids_and_pages_callback_only_runs(
        self, api: FakeTaskRunsAPI
    ):
        api.max_filter_ids = 999
        api.page_size = 7
        task_run_ids = [uuid.uuid4() for _ in range(1001)]
        callbacks = {task_run_id: MagicMock() for task_run_id in task_run_ids}
        stream = RecoveringEventStream()
        stream.setup_error = False
        with patch("prefect.task_runs.get_events_subscriber", stream):
            for task_run_id, callback in callbacks.items():
                TaskRunWaiter.add_done_callback(task_run_id, callback)
            api.final_states.update(
                {task_run_id: Completed() for task_run_id in task_run_ids}
            )

            await TaskRunWaiter.instance()._check_waited_task_runs()

        for callback in callbacks.values():
            callback.assert_called_once_with()

    @pytest.mark.timeout(20)
    async def test_polling_pages_through_waited_task_runs(self, api: FakeTaskRunsAPI):
        api.page_size = 2
        task_run_ids = [uuid.uuid4() for _ in range(5)]
        with patch("prefect.task_runs.get_events_subscriber", EndingEventStream()):
            waiting = [
                asyncio.create_task(TaskRunWaiter.wait_for_task_run(task_run_id))
                for task_run_id in task_run_ids
            ]
            await asyncio.sleep(0.1)
            final_states = {task_run_id: Completed() for task_run_id in task_run_ids}
            api.final_states.update(final_states)

            results = await asyncio.wait_for(asyncio.gather(*waiting), timeout=10)

        assert results == [final_states[task_run_id] for task_run_id in task_run_ids]

    @pytest.mark.timeout(20)
    async def test_raising_done_callback_does_not_stop_polling(
        self, api: FakeTaskRunsAPI, caplog: pytest.LogCaptureFixture
    ):
        failing_id, waited_id = uuid.uuid4(), uuid.uuid4()
        with patch("prefect.task_runs.get_events_subscriber", EndingEventStream()):
            TaskRunWaiter.add_done_callback(
                failing_id, MagicMock(side_effect=RuntimeError("boom"))
            )
            api.final_states[failing_id] = Completed()
            await asyncio.sleep(0.1)

            waiting = asyncio.create_task(TaskRunWaiter.wait_for_task_run(waited_id))
            final_state = Completed()
            api.final_states[waited_id] = final_state

            assert await asyncio.wait_for(waiting, timeout=10) is final_state
        assert "Error in done callback" in caplog.text
        assert "TaskRunWaiter lost both" not in caplog.text
