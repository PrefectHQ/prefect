import asyncio
import signal
from unittest.mock import AsyncMock, MagicMock, patch

import anyio
import pytest
from pydantic import BaseModel

import prefect.results
from prefect import flow, task
from prefect.exceptions import MissingResult
from prefect.filesystems import LocalFileSystem
from prefect.futures import PrefectDistributedFuture
from prefect.states import Running
from prefect.task_worker import TaskWorker, serve
from prefect.tasks import task_input_hash


@pytest.fixture(autouse=True)
async def clear_cached_filesystems():
    prefect.results._default_task_scheduling_storages.clear()
    yield
    prefect.results._default_task_scheduling_storages.clear()


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

        assert task_worker._client_id == "foo-42"


async def test_task_worker_handles_aborted_task_run_submission(
    foo_task, prefect_client, caplog
):
    task_worker = TaskWorker(foo_task)

    task_run_future = foo_task.apply_async((42,))

    new_state = Running()
    new_state.state_details.deferred = True
    await prefect_client.set_task_run_state(
        task_run_future.task_run_id,
        new_state,
        force=True,
    )

    task_run = await prefect_client.read_task_run(task_run_future.task_run_id)

    await task_worker.execute_task_run(task_run)

    assert "in a RUNNING state and cannot transition to a PENDING state." in caplog.text


async def test_task_worker_handles_deleted_task_run_submission(
    foo_task, prefect_client, caplog
):
    task_worker = TaskWorker(foo_task)

    task_run_future = foo_task.apply_async((42,))
    task_run = await prefect_client.read_task_run(task_run_future.task_run_id)

    await prefect_client.delete_task_run(task_run_future.task_run_id)

    await task_worker.execute_task_run(task_run)

    assert (
        f"Task run {task_run.id!r} not found. It may have been deleted." in caplog.text
    )


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
    async_foo_task, prefect_client
):
    task_worker = TaskWorker(async_foo_task)

    task_run_future = async_foo_task.apply_async((42,))
    task_run = await prefect_client.read_task_run(task_run_future.task_run_id)

    await task_worker.execute_task_run(task_run)

    updated_task_run = await prefect_client.read_task_run(task_run_future.task_run_id)

    assert updated_task_run.state.is_completed()

    assert await updated_task_run.state.result() == 42


async def test_task_worker_can_execute_a_single_sync_single_task_run(
    foo_task, prefect_client
):
    task_worker = TaskWorker(foo_task)

    task_run_future = foo_task.apply_async((42,))
    task_run = await prefect_client.read_task_run(task_run_future.task_run_id)

    await task_worker.execute_task_run(task_run)

    updated_task_run = await prefect_client.read_task_run(task_run_future.task_run_id)

    assert updated_task_run.state.is_completed()

    assert await updated_task_run.state.result() == 42


class TestTaskWorkerTaskRunRetries:
    async def test_task_run_via_task_worker_respects_retry_policy(self, prefect_client):
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
        self, should_retry, prefect_client
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

        updated_task_run = await prefect_client.read_task_run(
            task_run_future.task_run_id
        )

        assert updated_task_run.state.type == expected_state

        assert count == expected_count


class TestTaskWorkerTaskResults:
    @pytest.mark.parametrize("persist_result", [True, False], ids=["persisted", "not"])
    async def test_task_run_via_task_worker_respects_persist_result(
        self, persist_result, prefect_client
    ):
        @task(persist_result=persist_result)
        def some_task():
            return 42

        task_worker = TaskWorker(some_task)

        task_run_future = some_task.apply_async()
        task_run = await prefect_client.read_task_run(task_run_future.task_run_id)

        await task_worker.execute_task_run(task_run)

        updated_task_run = await prefect_client.read_task_run(
            task_run_future.task_run_id
        )

        assert updated_task_run.state.is_completed()

        if persist_result:
            assert await updated_task_run.state.result() == 42
        else:
            with pytest.raises(
                MissingResult,
                match="The result was not persisted|State data is missing",
            ):
                await updated_task_run.state.result()

    @pytest.mark.parametrize(
        "storage_key", ["foo", "{parameters[x]}"], ids=["static", "dynamic"]
    )
    async def test_task_run_via_task_worker_respects_result_storage_key(
        self, storage_key, prefect_client
    ):
        @task(persist_result=True, result_storage_key=storage_key)
        def some_task(x):
            return x

        task_worker = TaskWorker(some_task)

        task_run_future = some_task.apply_async(kwargs={"x": "foo"})
        task_run = await prefect_client.read_task_run(task_run_future.task_run_id)

        await task_worker.execute_task_run(task_run)

        updated_task_run = await prefect_client.read_task_run(
            task_run_future.task_run_id
        )

        assert updated_task_run.state.is_completed()

        assert await updated_task_run.state.result() == "foo"

        assert updated_task_run.state.data.storage_key == "foo"

    async def test_task_run_via_task_worker_with_complex_result_type(
        self, prefect_client
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
        self, async_foo_task, prefect_client, caplog
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

        updated_task_run = await prefect_client.read_task_run(
            task_run_future.task_run_id
        )

        assert updated_task_run.state.is_completed()

        assert await updated_task_run.state.result() == 1

        new_task_run_future = task_with_cache.apply_async((42,))
        task_run = await prefect_client.read_task_run(new_task_run_future.task_run_id)

        with caplog.at_level("INFO"):
            await task_worker.execute_task_run(task_run)

        new_updated_task_run = await prefect_client.read_task_run(
            task_run_future.task_run_id
        )

        assert "Finished in state Cached(type=COMPLETED)" in caplog.text

        assert await new_updated_task_run.state.result() == 1

        assert count == 1

    async def test_task_run_via_task_worker_receives_result_of_task_dependency(
        self, prefect_client, foo_task, bar_task
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
        assert foo_task_run_future.result() == 42

        await task_worker.execute_task_run(bar_task_run)
        assert bar_task_run_future.result() == 43

    async def test_task_run_via_task_worker_handles_mix_of_args_and_task_dependencies(
        self, foo_task, bar_task, prefect_client
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
        assert foo_task_run_future.result() == 42

        await task_worker.execute_task_run(bar_task_run)
        assert bar_task_run_future.result() == 47


class TestTaskWorkerTaskTags:
    async def test_task_run_via_task_worker_respects_tags(
        self, async_foo_task, prefect_client
    ):
        @task(tags=["foo", "bar"])
        async def task_with_tags(x):
            return x

        task_worker = TaskWorker(task_with_tags)

        task_run_future = task_with_tags.apply_async((42,))
        task_run = await prefect_client.read_task_run(task_run_future.task_run_id)

        await task_worker.execute_task_run(task_run)

        updated_task_run = await prefect_client.read_task_run(
            task_run_future.task_run_id
        )

        assert updated_task_run.state.is_completed()

        assert {"foo", "bar"} == set(updated_task_run.tags)


class TestTaskWorkerCustomTaskRunName:
    async def test_task_run_via_task_worker_respects_custom_task_run_name(
        self, async_foo_task, prefect_client
    ):
        async_foo_task_with_custom_name = async_foo_task.with_options(
            task_run_name="{x}"
        )

        task_worker = TaskWorker(async_foo_task_with_custom_name)

        task_run_future = async_foo_task_with_custom_name.apply_async((42,))
        task_run = await prefect_client.read_task_run(task_run_future.task_run_id)

        await task_worker.execute_task_run(task_run)

        updated_task_run = await prefect_client.read_task_run(
            task_run_future.task_run_id
        )

        assert updated_task_run.state.is_completed()

        assert updated_task_run.name == "42"


class TestTaskWorkerTaskStateHooks:
    async def test_task_run_via_task_worker_runs_on_completion_hook(
        self, async_foo_task, prefect_client, capsys
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

        updated_task_run = await prefect_client.read_task_run(
            task_run_future.task_run_id
        )

        assert updated_task_run.state.is_completed()

        assert "Running on_completion hook" in capsys.readouterr().out

    async def test_task_run_via_task_worker_runs_on_failure_hook(
        self, prefect_client, capsys
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

        updated_task_run = await prefect_client.read_task_run(
            task_run_future.task_run_id
        )

        assert updated_task_run.state.is_failed()

        assert "Running on_failure hook" in capsys.readouterr().out


class TestTaskWorkerNestedTasks:
    async def test_nested_task_run_via_task_worker(self, prefect_client):
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

        updated_task_run = await prefect_client.read_task_run(
            task_run_future.task_run_id
        )

        assert updated_task_run.state.is_completed()

        assert await updated_task_run.state.result() == 42

    async def test_nested_flow_run_via_task_worker(self, prefect_client):
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

    async def test_task_worker_respects_limit(self, mock_subscription, prefect_client):
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

        updated_task_run_1 = await prefect_client.read_task_run(task_run_1.id)
        updated_task_run_2 = await prefect_client.read_task_run(task_run_2.id)

        assert updated_task_run_1.state.is_completed()
        assert updated_task_run_2.state.is_scheduled()

    async def test_tasks_execute_when_limit_is_none(
        self, mock_subscription, prefect_client
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

        updated_task_run_1 = await prefect_client.read_task_run(task_run_1.id)
        updated_task_run_2 = await prefect_client.read_task_run(task_run_2.id)

        assert updated_task_run_1.state.is_completed()
        assert updated_task_run_2.state.is_completed()

    async def test_tasks_execute_when_capacity_frees_up(
        self, mock_subscription, prefect_client
    ):
        event = asyncio.Event()

        @task
        async def slow_task():
            await asyncio.sleep(1)
            if event.is_set():
                raise ValueError("Something went wrong! This event should not be set.")
            event.set()

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

        server_task = asyncio.create_task(task_worker.start())
        await event.wait()
        updated_task_run_1 = await prefect_client.read_task_run(task_run_1.id)
        updated_task_run_2 = await prefect_client.read_task_run(task_run_2.id)

        assert updated_task_run_1.state.is_completed()
        assert not updated_task_run_2.state.is_completed()

        # clear the event to allow the second task to complete
        event.clear()

        await event.wait()
        updated_task_run_2 = await prefect_client.read_task_run(task_run_2.id)

        assert updated_task_run_2.state.is_completed()

        server_task.cancel()
        await server_task

    async def test_execute_task_run_respects_limit(self, prefect_client):
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

        updated_task_run_1 = await prefect_client.read_task_run(task_run_1.id)
        updated_task_run_2 = await prefect_client.read_task_run(task_run_2.id)

        assert updated_task_run_1.state.is_completed()
        assert updated_task_run_2.state.is_scheduled()

    async def test_serve_respects_limit(self, prefect_client, mock_subscription):
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

        updated_task_run_1 = await prefect_client.read_task_run(task_run_1.id)
        updated_task_run_2 = await prefect_client.read_task_run(task_run_2.id)

        assert updated_task_run_1.state.is_completed()
        assert updated_task_run_2.state.is_scheduled()
