import signal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

import prefect.results
from prefect import flow, get_client, task
from prefect.client.schemas.objects import TaskRun
from prefect.exceptions import MissingResult
from prefect.settings import (
    PREFECT_EXPERIMENTAL_ENABLE_TASK_SCHEDULING,
    temporary_settings,
)
from prefect.states import Running
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
    async def bar(foo_run: TaskRun) -> int:
        async with get_client() as client:
            updated_foo_run = await client.read_task_run(foo_run.id)

        x = await updated_foo_run.state.result()
        y = x + 1
        return y

    return bar


@pytest.fixture
def mock_task_server_start(monkeypatch):
    monkeypatch.setattr(
        "prefect.task_server.TaskServer.start", mock_start := AsyncMock()
    )
    return mock_start


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


async def test_handle_sigterm(mock_create_subscription):
    task_server = TaskServer(...)

    with patch("sys.exit") as mock_exit, patch.object(
        task_server, "stop", new_callable=AsyncMock
    ) as mock_stop:
        await task_server.start()

        mock_create_subscription.assert_called_once()

        task_server.handle_sigterm(signal.SIGTERM, None)

        mock_exit.assert_called_once_with(0)
        mock_stop.assert_called_once()


async def test_task_server_client_id_is_set():
    with patch("socket.gethostname", return_value="foo"), patch(
        "os.getpid", return_value=42
    ):
        task_server = TaskServer(...)
        task_server._client = MagicMock(api_url="http://localhost:4200")

        assert task_server._client_id == "foo-42"


async def test_task_server_handles_aborted_task_run_submission(
    foo_task, prefect_client, caplog
):
    task_server = TaskServer(foo_task)

    task_run = foo_task.apply_async(42)

    await prefect_client.set_task_run_state(task_run.id, Running(), force=True)

    await task_server.execute_task_run(task_run)

    assert "in a RUNNING state and cannot transition to a PENDING state." in caplog.text


async def test_task_server_handles_deleted_task_run_submission(
    foo_task, prefect_client, caplog
):
    task_server = TaskServer(foo_task)

    task_run = foo_task.apply_async(42)

    await prefect_client.delete_task_run(task_run.id)

    await task_server.execute_task_run(task_run)

    assert (
        f"Task run {task_run.id!r} not found. It may have been deleted." in caplog.text
    )


@pytest.mark.usefixtures("mock_task_server_start")
class TestServe:
    async def test_serve_raises_if_task_scheduling_not_enabled(self, foo_task):
        with temporary_settings({PREFECT_EXPERIMENTAL_ENABLE_TASK_SCHEDULING: False}):
            with pytest.raises(
                RuntimeError,
                match="set PREFECT_EXPERIMENTAL_ENABLE_TASK_SCHEDULING to True",
            ):
                await serve(foo_task)

    async def test_serve_basic_sync_task(self, foo_task, mock_task_server_start):
        await serve(foo_task)
        mock_task_server_start.assert_called_once()

        task_run = foo_task.apply_async(42)

        assert isinstance(task_run, TaskRun)

        assert task_run.state.is_scheduled()

    async def test_serve_basic_async_task(self, async_foo_task, mock_task_server_start):
        await serve(async_foo_task)
        mock_task_server_start.assert_called_once()

        task_run = async_foo_task.apply_async(42)

        assert isinstance(task_run, TaskRun)

        assert task_run.state.is_scheduled()


async def test_task_server_can_execute_a_single_async_single_task_run(
    async_foo_task, prefect_client
):
    task_server = TaskServer(async_foo_task)

    task_run = async_foo_task.apply_async(42)

    await task_server.execute_task_run(task_run)

    updated_task_run = await prefect_client.read_task_run(task_run.id)

    assert updated_task_run.state.is_completed()

    assert await updated_task_run.state.result() == 42


async def test_task_server_can_execute_a_single_sync_single_task_run(
    foo_task, prefect_client
):
    task_server = TaskServer(foo_task)

    task_run = foo_task.apply_async(42)

    await task_server.execute_task_run(task_run)

    updated_task_run = await prefect_client.read_task_run(task_run.id)

    assert updated_task_run.state.is_completed()

    assert await updated_task_run.state.result() == 42


class TestTaskServerTaskRunRetries:
    async def test_task_run_via_task_server_respects_retry_policy(self, prefect_client):
        count = 0

        @task(retries=1, persist_result=True)
        def task_with_retry():
            nonlocal count
            if count == 0:
                count += 1
                raise ValueError("maybe next time")
            count += 1
            return count

        task_server = TaskServer(task_with_retry)

        task_run = task_with_retry.apply_async()

        await task_server.execute_task_run(task_run)

        updated_task_run = await prefect_client.read_task_run(task_run.id)

        assert updated_task_run.state.is_completed()

        assert await updated_task_run.state.result() == 2

        assert count == 2

    @pytest.mark.parametrize(
        "should_retry",
        [lambda task, task_run, state: True, lambda task, task_run, state: False],
        ids=["will_retry", "wont_retry"],
    )
    async def test_task_run_via_task_server_respects_retry_condition_fn(
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

        task_server = TaskServer(task_with_retry_condition_fn)

        task_run = task_with_retry_condition_fn.apply_async()

        await task_server.execute_task_run(task_run)

        updated_task_run = await prefect_client.read_task_run(task_run.id)

        assert updated_task_run.state.type == expected_state

        assert count == expected_count


class TestTaskServerTaskResults:
    @pytest.mark.parametrize("persist_result", [True, False], ids=["persisted", "not"])
    async def test_task_run_via_task_server_respects_persist_result(
        self, persist_result, prefect_client
    ):
        @task(persist_result=persist_result)
        def some_task():
            return 42

        task_server = TaskServer(some_task)

        task_run = some_task.apply_async()

        await task_server.execute_task_run(task_run)

        updated_task_run = await prefect_client.read_task_run(task_run.id)

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
    async def test_task_run_via_task_server_respects_result_storage_key(
        self, storage_key, prefect_client
    ):
        @task(persist_result=True, result_storage_key=storage_key)
        def some_task(x):
            return x

        task_server = TaskServer(some_task)

        task_run = some_task.apply_async(x="foo")

        await task_server.execute_task_run(task_run)

        updated_task_run = await prefect_client.read_task_run(task_run.id)

        assert updated_task_run.state.is_completed()

        assert await updated_task_run.state.result() == "foo"

        assert updated_task_run.state.data.storage_key == "foo"

    async def test_task_run_via_task_server_with_complex_result_type(
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

        task_server = TaskServer(americas_third_largest_city)

        task_run = americas_third_largest_city.apply_async()

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
        self, async_foo_task, prefect_client, caplog
    ):
        count = 0

        @task(cache_key_fn=task_input_hash)
        async def task_with_cache(x):
            nonlocal count
            count += 1
            return count

        task_server = TaskServer(task_with_cache)

        task_run = task_with_cache.apply_async(42)

        await task_server.execute_task_run(task_run)

        updated_task_run = await prefect_client.read_task_run(task_run.id)

        assert updated_task_run.state.is_completed()

        assert await updated_task_run.state.result() == 1

        new_task_run = task_with_cache.apply_async(42)

        with caplog.at_level("INFO"):
            await task_server.execute_task_run(new_task_run)

        new_updated_task_run = await prefect_client.read_task_run(task_run.id)

        assert "Finished in state Cached(type=COMPLETED)" in caplog.text

        assert await new_updated_task_run.state.result() == 1

        assert count == 1

    async def test_task_run_via_task_server_ignores_task_dependency(
        self, prefect_client, foo_task, bar_task
    ):
        """
        A regression test for #13512
        """
        foo = foo_task.with_options(persist_result=True)
        bar = bar_task.with_options(persist_result=True)

        task_server = TaskServer(foo, bar)

        foo_task_run = foo.apply_async(42)

        # Passing a TaskRun object as a dependency to another task run like this would
        # normally fail because we would discover the state (`TaskRun.state`), find it was
        # Pending, and then bail because the task wasn't complete. However, autonomous
        # tasks don't keep track of dependencies, so instead `bar` should receive the
        # TaskRun object as an argument.
        #
        # Ideally, though, we could wait for the TaskRun to complete in the same way that
        # we can when tasks receive PrefectFuture objects for runs that a task runner in
        # a flow is managing. For now, though, while we decide what else we want to do
        # in this situation, we'll pass objects through directly as arguments.
        bar_task_run = bar.apply_async(foo_task_run)

        await task_server.execute_task_run(foo_task_run)
        updated_task_run = await prefect_client.read_task_run(foo_task_run.id)
        assert updated_task_run.state.is_completed()
        assert await updated_task_run.state.result() == 42

        await task_server.execute_task_run(bar_task_run)
        updated_bar_task_run = await prefect_client.read_task_run(bar_task_run.id)
        assert updated_bar_task_run.state.is_completed()
        assert await updated_bar_task_run.state.result() == 43


class TestTaskServerTaskTags:
    async def test_task_run_via_task_server_respects_tags(
        self, async_foo_task, prefect_client
    ):
        @task(tags=["foo", "bar"])
        async def task_with_tags(x):
            return x

        task_server = TaskServer(task_with_tags)

        task_run = task_with_tags.apply_async(42)

        await task_server.execute_task_run(task_run)

        updated_task_run = await prefect_client.read_task_run(task_run.id)

        assert updated_task_run.state.is_completed()

        assert {"foo", "bar"} == set(updated_task_run.tags)


class TestTaskServerCustomTaskRunName:
    async def test_task_run_via_task_server_respects_custom_task_run_name(
        self, async_foo_task, prefect_client
    ):
        async_foo_task_with_custom_name = async_foo_task.with_options(
            task_run_name="{x}"
        )

        task_server = TaskServer(async_foo_task_with_custom_name)

        task_run = async_foo_task_with_custom_name.apply_async(42)

        await task_server.execute_task_run(task_run)

        updated_task_run = await prefect_client.read_task_run(task_run.id)

        assert updated_task_run.state.is_completed()

        assert updated_task_run.name == "42"


class TestTaskServerTaskStateHooks:
    async def test_task_run_via_task_server_runs_on_completion_hook(
        self, async_foo_task, prefect_client, capsys
    ):
        async_foo_task_with_on_completion_hook = async_foo_task.with_options(
            on_completion=[
                lambda task, task_run, state: print("Running on_completion hook")
            ]
        )

        task_server = TaskServer(async_foo_task_with_on_completion_hook)

        task_run = async_foo_task_with_on_completion_hook.apply_async(42)

        await task_server.execute_task_run(task_run)

        updated_task_run = await prefect_client.read_task_run(task_run.id)

        assert updated_task_run.state.is_completed()

        assert "Running on_completion hook" in capsys.readouterr().out

    async def test_task_run_via_task_server_runs_on_failure_hook(
        self, prefect_client, capsys
    ):
        @task(
            on_failure=[lambda task, task_run, state: print("Running on_failure hook")]
        )
        def task_that_fails():
            raise ValueError("I failed")

        task_server = TaskServer(task_that_fails)

        task_run = task_that_fails.apply_async()

        await task_server.execute_task_run(task_run)

        updated_task_run = await prefect_client.read_task_run(task_run.id)

        assert updated_task_run.state.is_failed()

        assert "Running on_failure hook" in capsys.readouterr().out


class TestTaskServerNestedTasks:
    async def test_nested_task_run_via_task_server(self, prefect_client):
        @task
        def inner_task(x):
            return x

        @task
        def outer_task(x):
            return inner_task(x)

        task_server = TaskServer(outer_task)

        task_run = outer_task.apply_async(42)

        await task_server.execute_task_run(task_run)

        updated_task_run = await prefect_client.read_task_run(task_run.id)

        assert updated_task_run.state.is_completed()

        assert await updated_task_run.state.result() == 42

    async def test_nested_flow_run_via_task_server(self, prefect_client):
        @flow
        def inner_flow(x):
            return x

        @task
        def background_task(x):
            return inner_flow(x)

        task_server = TaskServer(background_task)

        task_run = background_task.apply_async(42)

        await task_server.execute_task_run(task_run)

        updated_task_run = await prefect_client.read_task_run(task_run.id)

        assert updated_task_run.state.is_completed()

        assert await updated_task_run.state.result() == 42
