import asyncio
import signal
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import anyio
import pytest
from pydantic import BaseModel

from prefect import flow, task
from prefect.filesystems import LocalFileSystem
from prefect.futures import PrefectDistributedFuture
from prefect.settings import (
    PREFECT_API_URL,
    PREFECT_UI_URL,
    temporary_settings,
)
from prefect.task_worker import TaskWorker, serve
from prefect.tasks import task_input_hash

pytestmark = pytest.mark.usefixtures("use_hosted_api_server")


# model defined outside of the test function to avoid pickling issues
# on pydantic v1 / Python 3.8, see https://github.com/cloudpipe/cloudpickle/issues/408
class BreakfastSpot(BaseModel):
    name: str
    location: str


class City(BaseModel):
    name: str
    best_breakfast_spot: BreakfastSpot


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
def bar_task():
    @task
    async def bar(x, y=1) -> int:
        return x + y

    return bar


@pytest.fixture
def mock_task_worker_start(monkeypatch):
    monkeypatch.setattr(
        "prefect.task_worker.TaskWorker.start", mock_start := AsyncMock()
    )
    return mock_start


@pytest.fixture
def mock_create_subscription(monkeypatch):
    monkeypatch.setattr(
        "prefect.task_worker.TaskWorker._subscribe_to_task_scheduling",
        create_subscription := AsyncMock(),
    )
    return create_subscription


@pytest.fixture
def mock_subscription(monkeypatch):
    monkeypatch.setattr(
        "prefect.task_worker.Subscription", mock_subscription := MagicMock()
    )
    return mock_subscription


async def test_task_worker_does_not_run_against_ephemeral_api():
    with pytest.raises(ValueError):
        with temporary_settings({PREFECT_API_URL: None}):
            await TaskWorker(...)._subscribe_to_task_scheduling()


async def test_task_worker_basic_context_management():
    async with TaskWorker(...) as task_worker:
        assert task_worker.started is True
        assert (await task_worker._client.hello()).status_code == 200

    assert task_worker.started is False
    with pytest.raises(RuntimeError, match="client has been closed"):
        await task_worker._client.hello()


async def test_handle_sigterm(mock_create_subscription):
    task_worker = TaskWorker(...)

    with patch("sys.exit") as mock_exit, patch.object(
        task_worker, "stop", new_callable=AsyncMock
    ) as mock_stop:
        await task_worker.start()

        mock_create_subscription.assert_called_once()

        task_worker.handle_sigterm(signal.SIGTERM, None)

        mock_exit.assert_called_once_with(0)
        mock_stop.assert_called_once()


async def test_task_worker_client_id_is_set():
    with patch("socket.gethostname", return_value="foo"), patch(
        "os.getpid", return_value=42
    ):
        task_worker = TaskWorker(...)
        task_worker._client = MagicMock(api_url="http://localhost:4200")

        assert task_worker.client_id == "foo-42"


async def test_task_worker_stays_running_on_errors(monkeypatch):
    # regression test for https://github.com/PrefectHQ/prefect/issues/13911
    # previously any error with submitting the task run would be raised
    # and uncaught, causing the task worker to stop and this test to fail

    @task
    def empty_task():
        pass

    @contextmanager
    def always_error(*args, **kwargs):
        raise ValueError("oops")

    monkeypatch.setattr("prefect.task_engine.SyncTaskRunEngine.start", always_error)

    task_worker = TaskWorker(empty_task)

    empty_task.apply_async()

    with anyio.move_on_after(1):
        await task_worker.start()


async def test_task_worker_emits_run_ui_url_upon_submission(
    foo_task, prefect_client, caplog
):
    task_worker = TaskWorker(foo_task)

    task_run_future = foo_task.apply_async((42,))
    task_run = await prefect_client.read_task_run(task_run_future.task_run_id)

    with temporary_settings({PREFECT_UI_URL: "http://test/api"}):
        await task_worker.execute_task_run(task_run)

    assert "in the UI: http://test/api/runs/task-run/" in caplog.text


@pytest.mark.usefixtures("mock_task_worker_start")
class TestServe:
    async def test_serve_basic_sync_task(self, foo_task, mock_task_worker_start):
        await serve(foo_task)
        mock_task_worker_start.assert_called_once()

        task_run_future = foo_task.apply_async((42,))

        assert isinstance(task_run_future, PrefectDistributedFuture)

        assert task_run_future.state.is_scheduled()

    async def test_serve_basic_async_task(self, async_foo_task, mock_task_worker_start):
        await serve(async_foo_task)
        mock_task_worker_start.assert_called_once()

        task_run_future = async_foo_task.apply_async((42,))

        assert isinstance(task_run_future, PrefectDistributedFuture)

        assert task_run_future.state.is_scheduled()


async def test_task_worker_can_execute_a_single_async_single_task_run(
    async_foo_task, prefect_client, events_pipeline
):
    task_worker = TaskWorker(async_foo_task)

    task_run_future = async_foo_task.apply_async((42,))
    task_run = await prefect_client.read_task_run(task_run_future.task_run_id)

    await task_worker.execute_task_run(task_run)

    await events_pipeline.process_events()

    updated_task_run = await prefect_client.read_task_run(task_run_future.task_run_id)

    assert updated_task_run.state.is_completed()

    assert await updated_task_run.state.result() == 42


async def test_task_worker_can_execute_a_single_sync_single_task_run(
    foo_task, prefect_client, events_pipeline
):
    task_worker = TaskWorker(foo_task)

    task_run_future = foo_task.apply_async((42,))
    task_run = await prefect_client.read_task_run(task_run_future.task_run_id)

    await task_worker.execute_task_run(task_run)

    await events_pipeline.process_events()

    updated_task_run = await prefect_client.read_task_run(task_run_future.task_run_id)

    assert updated_task_run.state.is_completed()

    assert await updated_task_run.state.result() == 42


class TestTaskWorkerTaskRunRetries:
    async def test_task_run_via_task_worker_respects_retry_policy(
        self, prefect_client, events_pipeline
    ):
        count = 0

        @task(retries=1, persist_result=True)
        def task_with_retry():
            nonlocal count
            if count == 0:
                count += 1
                raise ValueError("maybe next time")
            count += 1
            return count

        task_worker = TaskWorker(task_with_retry)

        task_run_future = task_with_retry.apply_async()
        task_run = await prefect_client.read_task_run(task_run_future.task_run_id)

        await task_worker.execute_task_run(task_run)
        await events_pipeline.process_events()

        updated_task_run = await prefect_client.read_task_run(
            task_run_future.task_run_id
        )

        assert updated_task_run.state.is_completed()

        assert await updated_task_run.state.result() == 2

        assert count == 2

    @pytest.mark.parametrize(
        "should_retry",
        [lambda task, task_run, state: True, lambda task, task_run, state: False],
        ids=["will_retry", "wont_retry"],
    )
    async def test_task_run_via_task_worker_respects_retry_condition_fn(
        self, should_retry, prefect_client, events_pipeline
    ):
        count = 0

        will_retry = should_retry(None, None, None)

        expected_count = 2 if will_retry else 1

        expected_state = "COMPLETED" if will_retry else "FAILED"

        @task(retries=1, retry_condition_fn=should_retry)
        def task_with_retry_condition_fn():
            nonlocal count
            if count == 0:
                count += 1
                raise RuntimeError("doh")
            count += 1
            return count

        task_worker = TaskWorker(task_with_retry_condition_fn)

        task_run_future = task_with_retry_condition_fn.apply_async()
        task_run = await prefect_client.read_task_run(task_run_future.task_run_id)

        await task_worker.execute_task_run(task_run)
        await events_pipeline.process_events()

        updated_task_run = await prefect_client.read_task_run(
            task_run_future.task_run_id
        )

        assert updated_task_run.state.type == expected_state

        assert count == expected_count


class TestTaskWorkerTaskResults:
    async def test_task_run_via_task_worker_persists_result(
        self, prefect_client, events_pipeline
    ):
        @task
        def some_task():
            return 42

        task_worker = TaskWorker(some_task)

        task_run_future = some_task.apply_async()
        task_run = await prefect_client.read_task_run(task_run_future.task_run_id)

        await task_worker.execute_task_run(task_run)
        await events_pipeline.process_events()

        updated_task_run = await prefect_client.read_task_run(
            task_run_future.task_run_id
        )

        assert updated_task_run.state.is_completed()

        assert await updated_task_run.state.result() == 42

    @pytest.mark.parametrize(
        "storage_key",
        [f"foo-{uuid.uuid4()}", "{parameters[x]}"],
        ids=["static", "dynamic"],
    )
    async def test_task_run_via_task_worker_respects_result_storage_key(
        self, storage_key, prefect_client, events_pipeline
    ):
        if "foo" in storage_key:
            x = storage_key
        else:
            x = f"foo-{uuid.uuid4()}"

        @task(persist_result=True, result_storage_key=storage_key)
        def some_task(x):
            return x

        task_worker = TaskWorker(some_task)

        task_run_future = some_task.apply_async(kwargs={"x": x})
        task_run = await prefect_client.read_task_run(task_run_future.task_run_id)

        await task_worker.execute_task_run(task_run)
        await events_pipeline.process_events()

        updated_task_run = await prefect_client.read_task_run(
            task_run_future.task_run_id
        )

        assert updated_task_run.state.is_completed()

        assert await updated_task_run.state.result() == x

        if "foo" in storage_key:
            assert Path(updated_task_run.state.data.storage_key).name == storage_key
        else:
            assert Path(updated_task_run.state.data.storage_key).name == x

    async def test_task_run_via_task_worker_with_complex_result_type(
        self, prefect_client, events_pipeline
    ):
        @task(persist_result=True)
        def americas_third_largest_city() -> City:
            return City(
                name="Chicago",
                best_breakfast_spot=BreakfastSpot(
                    name="The Bongo Room",
                    location="Wicker Park",
                ),
            )

        task_worker = TaskWorker(americas_third_largest_city)

        task_run_future = americas_third_largest_city.apply_async()
        task_run = await prefect_client.read_task_run(task_run_future.task_run_id)

        await task_worker.execute_task_run(task_run)
        await events_pipeline.process_events()
        updated_task_run = await prefect_client.read_task_run(
            task_run_future.task_run_id
        )

        assert updated_task_run.state.is_completed()

        assert await updated_task_run.state.result() == City(
            name="Chicago",
            best_breakfast_spot=BreakfastSpot(
                name="The Bongo Room",
                location="Wicker Park",
            ),
        )

    async def test_task_run_via_task_worker_respects_caching(
        self,
        async_foo_task,
        prefect_client,
        caplog,
        events_pipeline,
    ):
        count = 0

        @task(cache_key_fn=task_input_hash)
        async def task_with_cache(x):
            nonlocal count
            count += 1
            return count

        task_worker = TaskWorker(task_with_cache)

        task_run_future = task_with_cache.apply_async((42,))
        task_run = await prefect_client.read_task_run(task_run_future.task_run_id)

        await task_worker.execute_task_run(task_run)
        await events_pipeline.process_events()

        updated_task_run = await prefect_client.read_task_run(
            task_run_future.task_run_id
        )

        assert updated_task_run.state.is_completed()

        assert await updated_task_run.state.result() == 1

        new_task_run_future = task_with_cache.apply_async((42,))
        task_run = await prefect_client.read_task_run(new_task_run_future.task_run_id)

        with caplog.at_level("INFO"):
            await task_worker.execute_task_run(task_run)
        await events_pipeline.process_events()

        new_updated_task_run = await prefect_client.read_task_run(
            task_run_future.task_run_id
        )

        assert "Finished in state Cached(type=COMPLETED)" in caplog.text

        assert await new_updated_task_run.state.result() == 1

        assert count == 1

    async def test_task_run_via_task_worker_receives_result_of_task_dependency(
        self, prefect_client, foo_task, bar_task, events_pipeline
    ):
        """
        A regression test for #13512
        """
        foo = foo_task.with_options(persist_result=True)
        bar = bar_task.with_options(persist_result=True)

        task_worker = TaskWorker(foo, bar)

        foo_task_run_future = foo.apply_async((42,))
        foo_task_run = await prefect_client.read_task_run(
            foo_task_run_future.task_run_id
        )
        bar_task_run_future = bar.apply_async((foo_task_run_future,))
        bar_task_run = await prefect_client.read_task_run(
            bar_task_run_future.task_run_id
        )

        await task_worker.execute_task_run(foo_task_run)
        await events_pipeline.process_events()
        assert foo_task_run_future.result() == 42

        await task_worker.execute_task_run(bar_task_run)
        await events_pipeline.process_events()
        assert bar_task_run_future.result() == 43

    async def test_task_run_via_task_worker_handles_mix_of_args_and_task_dependencies(
        self, foo_task, bar_task, prefect_client, events_pipeline
    ):
        foo = foo_task.with_options(persist_result=True)
        bar = bar_task.with_options(persist_result=True)

        task_worker = TaskWorker(foo, bar)

        foo_task_run_future = foo.apply_async((42,))
        foo_task_run = await prefect_client.read_task_run(
            foo_task_run_future.task_run_id
        )
        bar_task_run_future = bar.apply_async(kwargs={"x": foo_task_run_future, "y": 5})
        bar_task_run = await prefect_client.read_task_run(
            bar_task_run_future.task_run_id
        )

        await task_worker.execute_task_run(foo_task_run)
        await events_pipeline.process_events()
        assert foo_task_run_future.result() == 42

        await task_worker.execute_task_run(bar_task_run)
        await events_pipeline.process_events()
        assert bar_task_run_future.result() == 47


class TestTaskWorkerTaskTags:
    async def test_task_run_via_task_worker_respects_tags(
        self, async_foo_task, prefect_client, events_pipeline
    ):
        @task(tags=["foo", "bar"])
        async def task_with_tags(x):
            return x

        task_worker = TaskWorker(task_with_tags)

        task_run_future = task_with_tags.apply_async((42,))
        task_run = await prefect_client.read_task_run(task_run_future.task_run_id)

        await task_worker.execute_task_run(task_run)
        await events_pipeline.process_events()

        updated_task_run = await prefect_client.read_task_run(
            task_run_future.task_run_id
        )

        assert updated_task_run.state.is_completed()

        assert {"foo", "bar"} == set(updated_task_run.tags)


class TestTaskWorkerCustomTaskRunName:
    async def test_task_run_via_task_worker_respects_custom_task_run_name(
        self, async_foo_task, prefect_client, events_pipeline
    ):
        async_foo_task_with_custom_name = async_foo_task.with_options(
            task_run_name="{x}"
        )

        task_worker = TaskWorker(async_foo_task_with_custom_name)

        task_run_future = async_foo_task_with_custom_name.apply_async((42,))
        task_run = await prefect_client.read_task_run(task_run_future.task_run_id)

        await task_worker.execute_task_run(task_run)
        await events_pipeline.process_events()

        updated_task_run = await prefect_client.read_task_run(
            task_run_future.task_run_id
        )

        assert updated_task_run.state.is_completed()

        assert updated_task_run.name == "42"


class TestTaskWorkerTaskStateHooks:
    async def test_task_run_via_task_worker_runs_on_completion_hook(
        self, async_foo_task, prefect_client, events_pipeline, capsys
    ):
        async_foo_task_with_on_completion_hook = async_foo_task.with_options(
            on_completion=[
                lambda task, task_run, state: print("Running on_completion hook")
            ]
        )

        task_worker = TaskWorker(async_foo_task_with_on_completion_hook)

        task_run_future = async_foo_task_with_on_completion_hook.apply_async((42,))
        task_run = await prefect_client.read_task_run(task_run_future.task_run_id)

        await task_worker.execute_task_run(task_run)
        await events_pipeline.process_events()

        updated_task_run = await prefect_client.read_task_run(
            task_run_future.task_run_id
        )

        assert updated_task_run.state.is_completed()

        assert "Running on_completion hook" in capsys.readouterr().out

    async def test_task_run_via_task_worker_runs_on_failure_hook(
        self, prefect_client, events_pipeline, capsys
    ):
        @task(
            on_failure=[lambda task, task_run, state: print("Running on_failure hook")]
        )
        def task_that_fails():
            raise ValueError("I failed")

        task_worker = TaskWorker(task_that_fails)

        task_run_future = task_that_fails.apply_async()
        task_run = await prefect_client.read_task_run(task_run_future.task_run_id)

        await task_worker.execute_task_run(task_run)
        await events_pipeline.process_events()

        updated_task_run = await prefect_client.read_task_run(
            task_run_future.task_run_id
        )

        assert updated_task_run.state.is_failed()

        assert "Running on_failure hook" in capsys.readouterr().out


class TestTaskWorkerNestedTasks:
    async def test_nested_task_run_via_task_worker(
        self, prefect_client, events_pipeline
    ):
        @task
        def inner_task(x):
            return x

        @task
        def outer_task(x):
            return inner_task(x)

        task_worker = TaskWorker(outer_task)

        task_run_future = outer_task.apply_async((42,))
        task_run = await prefect_client.read_task_run(task_run_future.task_run_id)

        await task_worker.execute_task_run(task_run)
        await events_pipeline.process_events()
        updated_task_run = await prefect_client.read_task_run(
            task_run_future.task_run_id
        )

        assert updated_task_run.state.is_completed()

        assert await updated_task_run.state.result() == 42

    async def test_nested_flow_run_via_task_worker(
        self, prefect_client, events_pipeline
    ):
        @flow
        def inner_flow(x):
            return x

        @task
        def background_task(x):
            return inner_flow(x)

        task_worker = TaskWorker(background_task)

        task_run_future = background_task.apply_async((42,))
        task_run = await prefect_client.read_task_run(task_run_future.task_run_id)

        await task_worker.execute_task_run(task_run)
        await events_pipeline.process_events()

        updated_task_run = await prefect_client.read_task_run(
            task_run_future.task_run_id
        )

        assert updated_task_run.state.is_completed()

        assert await updated_task_run.state.result() == 42


class TestTaskWorkerLimit:
    @pytest.fixture(autouse=True)
    async def register_localfilesystem(self):
        """Register LocalFileSystem before running tests to avoid race conditions."""
        await LocalFileSystem.register_type_and_schema()

    async def test_task_worker_limiter_gracefully_handles_same_task_run(
        self, prefect_client, events_pipeline
    ):
        @task
        def slow_task():
            import time

            time.sleep(1)

        task_worker = TaskWorker(slow_task, limit=1)

        task_run_future = slow_task.apply_async()
        task_run = await prefect_client.read_task_run(task_run_future.task_run_id)

        try:
            with anyio.move_on_after(1):
                # run same task, one should acquire a token
                # the other will gracefully be skipped.
                async with task_worker:
                    await asyncio.gather(
                        task_worker.execute_task_run(task_run),
                        task_worker.execute_task_run(task_run),
                    )
        except asyncio.exceptions.CancelledError:
            # we expect a cancelled error here
            pass

        await events_pipeline.process_events()

        updated_task_run = await prefect_client.read_task_run(task_run.id)
        assert updated_task_run.state.is_completed()

    async def test_task_worker_respects_limit(
        self, mock_subscription, prefect_client, events_pipeline
    ):
        @task
        def slow_task():
            import time

            time.sleep(1)

        task_worker = TaskWorker(slow_task, limit=1)

        task_run_future_1 = slow_task.apply_async()
        task_run_1 = await prefect_client.read_task_run(task_run_future_1.task_run_id)
        task_run_future_2 = slow_task.apply_async()
        task_run_2 = await prefect_client.read_task_run(task_run_future_2.task_run_id)

        async def mock_iter():
            yield task_run_1
            yield task_run_2
            # sleep for a second to ensure that task execution starts
            await asyncio.sleep(1)

        mock_subscription.return_value = mock_iter()

        # only one should run at a time, so we'll move on after 1 second
        # to ensure that the second task hasn't started
        with anyio.move_on_after(1):
            await task_worker.start()

        await events_pipeline.process_events()

        updated_task_run_1 = await prefect_client.read_task_run(task_run_1.id)
        updated_task_run_2 = await prefect_client.read_task_run(task_run_2.id)

        assert updated_task_run_1.state.is_completed()
        assert updated_task_run_2.state.is_scheduled()

    async def test_tasks_execute_when_limit_is_none(
        self, mock_subscription, prefect_client, events_pipeline
    ):
        @task
        def slow_task():
            import time

            time.sleep(1)

        task_worker = TaskWorker(slow_task, limit=None)

        task_run_future_1 = slow_task.apply_async()
        task_run_1 = await prefect_client.read_task_run(task_run_future_1.task_run_id)
        task_run_future_2 = slow_task.apply_async()
        task_run_2 = await prefect_client.read_task_run(task_run_future_2.task_run_id)

        async def mock_iter():
            yield task_run_1
            yield task_run_2
            # sleep for a second to ensure that task execution starts
            await asyncio.sleep(1)

        mock_subscription.return_value = mock_iter()

        # both should run at the same time, so we'll move on after 1 second
        # to ensure that the second task has started
        with anyio.move_on_after(1):
            await task_worker.start()

        await events_pipeline.process_events()

        updated_task_run_1 = await prefect_client.read_task_run(task_run_1.id)
        updated_task_run_2 = await prefect_client.read_task_run(task_run_2.id)

        assert updated_task_run_1.state.is_completed()
        assert updated_task_run_2.state.is_completed()

    async def test_tasks_execute_when_capacity_frees_up(
        self, mock_subscription, prefect_client, events_pipeline
    ):
        execution_order = []

        @task
        async def slow_task(task_id: str):
            execution_order.append(f"{task_id} start")
            await asyncio.sleep(0.1)  # Simulating some work
            execution_order.append(f"{task_id} end")

        task_worker = TaskWorker(slow_task, limit=1)

        task_run_future_1 = slow_task.apply_async(("task1",))
        task_run_1 = await prefect_client.read_task_run(task_run_future_1.task_run_id)
        task_run_future_2 = slow_task.apply_async(("task2",))
        task_run_2 = await prefect_client.read_task_run(task_run_future_2.task_run_id)

        async def mock_iter():
            yield task_run_1
            yield task_run_2
            while len(execution_order) < 4:
                await asyncio.sleep(0.1)

        mock_subscription.return_value = mock_iter()

        server_task = asyncio.create_task(task_worker.start())

        try:
            # Wait for both tasks to complete
            await asyncio.sleep(2)

            await events_pipeline.process_events()

            # Verify the execution order
            assert execution_order == [
                "task1 start",
                "task1 end",
                "task2 start",
                "task2 end",
            ], "Tasks should execute sequentially"

            # Verify the states of both tasks
            updated_task_run_1 = await prefect_client.read_task_run(task_run_1.id)
            updated_task_run_2 = await prefect_client.read_task_run(task_run_2.id)

            assert updated_task_run_1.state.is_completed()
            assert updated_task_run_2.state.is_completed()

        finally:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    async def test_execute_task_run_respects_limit(
        self, prefect_client, events_pipeline
    ):
        @task
        def slow_task():
            import time

            time.sleep(1)

        task_worker = TaskWorker(slow_task, limit=1)

        task_run_future_1 = slow_task.apply_async()
        task_run_1 = await prefect_client.read_task_run(task_run_future_1.task_run_id)
        task_run_future_2 = slow_task.apply_async()
        task_run_2 = await prefect_client.read_task_run(task_run_future_2.task_run_id)

        try:
            with anyio.move_on_after(1):
                # start task worker first to avoid race condition between two execute_task_run calls
                async with task_worker:
                    await asyncio.gather(
                        task_worker.execute_task_run(task_run_1),
                        task_worker.execute_task_run(task_run_2),
                    )
        except asyncio.exceptions.CancelledError:
            # We want to cancel the second task run, so this is expected
            pass

        await events_pipeline.process_events()

        updated_task_run_1 = await prefect_client.read_task_run(task_run_1.id)
        updated_task_run_2 = await prefect_client.read_task_run(task_run_2.id)

        assert updated_task_run_1.state.is_completed()
        assert updated_task_run_2.state.is_scheduled()

    async def test_serve_respects_limit(
        self, prefect_client, mock_subscription, events_pipeline
    ):
        @task
        def slow_task():
            import time

            time.sleep(1)

        task_run_future_1 = slow_task.apply_async()
        task_run_1 = await prefect_client.read_task_run(task_run_future_1.task_run_id)
        task_run_future_2 = slow_task.apply_async()
        task_run_2 = await prefect_client.read_task_run(task_run_future_2.task_run_id)

        async def mock_iter():
            yield task_run_1
            yield task_run_2
            # sleep for a second to ensure that task execution starts
            await asyncio.sleep(1)

        mock_subscription.return_value = mock_iter()

        # only one should run at a time, so we'll move on after 1 second
        # to ensure that the second task hasn't started
        with anyio.move_on_after(1):
            await serve(slow_task, limit=1)

        await events_pipeline.process_events()

        updated_task_run_1 = await prefect_client.read_task_run(task_run_1.id)
        updated_task_run_2 = await prefect_client.read_task_run(task_run_2.id)

        assert updated_task_run_1.state.is_completed()
        assert updated_task_run_2.state.is_scheduled()
