import asyncio
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, AsyncGenerator, Iterable, Tuple
from unittest import mock

import pytest

import prefect.results
from prefect import Task, task, unmapped
from prefect.blocks.core import Block
from prefect.client.orchestration import get_client
from prefect.client.schemas import TaskRun
from prefect.filesystems import LocalFileSystem
from prefect.results import ResultStore, get_or_create_default_task_scheduling_storage
from prefect.server.api.task_runs import TaskQueue
from prefect.server.schemas.core import TaskRun as ServerTaskRun
from prefect.settings import (
    PREFECT_TASK_SCHEDULING_DEFAULT_STORAGE_BLOCK,
    temporary_settings,
)

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient


async def result_store_from_task(task) -> ResultStore:
    return await ResultStore(
        result_storage=await get_or_create_default_task_scheduling_storage()
    ).update_for_task(task)


@pytest.fixture
def local_filesystem(tmp_path):
    block = LocalFileSystem(basepath=tmp_path)
    block.save("test-fs", overwrite=True)
    return block


@pytest.fixture(autouse=True)
async def clear_scheduled_task_queues():
    TaskQueue.reset()
    yield
    TaskQueue.reset()


@pytest.fixture(autouse=True)
async def clear_cached_filesystems():
    prefect.results._default_storages.clear()
    yield
    prefect.results._default_storages.clear()


@pytest.fixture
def foo_task() -> Task:
    @task
    def foo(x: int) -> int:
        print(x)
        return x

    return foo


@pytest.fixture
def async_foo_task() -> Task:
    @task
    async def async_foo(x: int) -> int:
        print(x)
        return x

    return async_foo


@pytest.fixture
def foo_task_with_result_storage(foo_task, local_filesystem):
    return foo_task.with_options(result_storage=local_filesystem)


@pytest.fixture
def async_foo_task_with_result_storage(async_foo_task, local_filesystem):
    return async_foo_task.with_options(result_storage=local_filesystem)


async def test_task_submission_with_parameters_uses_default_storage(
    foo_task, prefect_client
):
    foo_task_without_result_storage = foo_task.with_options(result_storage=None)
    task_run_future = foo_task_without_result_storage.apply_async((42,))
    task_run = await prefect_client.read_task_run(task_run_future.task_run_id)

    result_store = await result_store_from_task(foo_task)
    await result_store.read_parameters(task_run.state.state_details.task_parameters_id)


async def test_task_submission_with_parameters_reuses_default_storage_block(
    foo_task: Task, tmp_path: Path, prefect_client
):
    with temporary_settings(
        {
            PREFECT_TASK_SCHEDULING_DEFAULT_STORAGE_BLOCK: "local-file-system/my-tasks",
        }
    ):
        block = LocalFileSystem(basepath=tmp_path / "some-storage")
        await block.save("my-tasks", overwrite=True)

        foo_task_without_result_storage = foo_task.with_options(result_storage=None)
        task_run_future_a = foo_task_without_result_storage.apply_async((42,))

        storage_before = await Block.load("local-file-system/my-tasks")
        assert isinstance(storage_before, LocalFileSystem)
        assert storage_before.basepath == str(tmp_path / "some-storage")

        foo_task_without_result_storage = foo_task.with_options(result_storage=None)
        task_run_future_b = foo_task_without_result_storage.apply_async((24,))

        storage_after = await Block.load("local-file-system/my-tasks")
        assert isinstance(storage_after, LocalFileSystem)

        result_store = await result_store_from_task(foo_task)
        task_run_a = await prefect_client.read_task_run(task_run_future_a.task_run_id)
        task_run_b = await prefect_client.read_task_run(task_run_future_b.task_run_id)
        assert await result_store.read_parameters(
            task_run_a.state.state_details.task_parameters_id
        ) == {"parameters": {"x": 42}, "context": mock.ANY}
        assert await result_store.read_parameters(
            task_run_b.state.state_details.task_parameters_id
        ) == {"parameters": {"x": 24}, "context": mock.ANY}


async def test_task_submission_creates_a_scheduled_task_run(
    foo_task_with_result_storage, prefect_client
):
    task_run_future = foo_task_with_result_storage.apply_async((42,))
    task_run = await prefect_client.read_task_run(task_run_future.task_run_id)
    assert task_run.state.is_scheduled()
    assert task_run.state.state_details.deferred is True

    result_store = await result_store_from_task(foo_task_with_result_storage)

    parameters = await result_store.read_parameters(
        task_run.state.state_details.task_parameters_id
    )

    assert parameters == {"parameters": {"x": 42}, "context": mock.ANY}


async def test_sync_task_not_awaitable_in_async_context(foo_task, prefect_client):
    task_run_future = foo_task.apply_async((42,))
    task_run = await prefect_client.read_task_run(task_run_future.task_run_id)
    assert task_run.state.is_scheduled()

    result_store = await result_store_from_task(foo_task)

    parameters = await result_store.read_parameters(
        task_run.state.state_details.task_parameters_id
    )

    assert parameters == {"parameters": {"x": 42}, "context": mock.ANY}


async def test_async_task_submission_creates_a_scheduled_task_run(
    async_foo_task_with_result_storage, prefect_client
):
    task_run_future = async_foo_task_with_result_storage.apply_async((42,))
    task_run = await prefect_client.read_task_run(task_run_future.task_run_id)
    assert task_run.state.is_scheduled()

    result_store = await result_store_from_task(async_foo_task_with_result_storage)

    parameters = await result_store.read_parameters(
        task_run.state.state_details.task_parameters_id
    )

    assert parameters == {"parameters": {"x": 42}, "context": mock.ANY}


async def test_scheduled_tasks_are_enqueued_server_side(
    foo_task_with_result_storage: Task,
    in_memory_prefect_client: "PrefectClient",
    monkeypatch,
):
    # Need to mock `get_client` to return the in-memory client because we are directly inspecting
    # changes in the server-side task queue. Ideally, we'd be able to inspect the task queue via
    # the REST API for this test, but that's not currently possible.
    # TODO: Add ways to inspect the task queue via the REST API
    monkeypatch.setattr(prefect.tasks, "get_client", lambda: in_memory_prefect_client)

    task_run_future = foo_task_with_result_storage.apply_async((42,))
    task_run = await in_memory_prefect_client.read_task_run(task_run_future.task_run_id)
    client_run: TaskRun = task_run
    assert client_run.state.is_scheduled()

    enqueued_run: ServerTaskRun = await TaskQueue.for_key(client_run.task_key).get()

    # The server-side task run in the queue should be the same as the one returned
    # to the client, but some of the calculated fields will be populated server-side
    # after orchestration in a way that differs by microseconds, or the
    # created/updated dates are populated.

    assert client_run.estimated_start_time_delta is not None
    assert enqueued_run.estimated_start_time_delta is not None
    assert (
        client_run.estimated_start_time_delta - enqueued_run.estimated_start_time_delta
        < timedelta(seconds=10)
    )
    client_run.estimated_start_time_delta = enqueued_run.estimated_start_time_delta

    enqueued_run_dict = enqueued_run.model_dump()
    client_run_dict = client_run.model_dump()

    client_run_dict["state"].pop("created")
    client_run_dict["state"].pop("updated")

    assert enqueued_run_dict == client_run_dict


async def test_tasks_are_not_enqueued_server_side_when_executed_directly(
    foo_task: Task,
):
    # Regression test for https://github.com/PrefectHQ/prefect/issues/13674
    # where executing a task would cause it to be enqueue server-side
    # and executed twice.
    foo_task(x=42)

    with pytest.raises(asyncio.QueueEmpty):
        TaskQueue.for_key(foo_task.task_key).get_nowait()


@pytest.fixture
async def prefect_client() -> AsyncGenerator["PrefectClient", None]:
    async with get_client() as client:
        yield client


class TestCall:
    async def test_call(self, async_foo_task):
        result = await async_foo_task(42)

        assert result == 42

    async def test_call_with_return_state(self, async_foo_task):
        state = await async_foo_task(42, return_state=True)

        assert state.is_completed()

        assert await state.result() == 42


class TestMap:
    async def test_map(self, async_foo_task):
        task_runs = async_foo_task.map([1, 2, 3], deferred=True)

        assert len(task_runs) == 3

        result_store = await result_store_from_task(async_foo_task)

        for i, task_run in enumerate(task_runs):
            assert task_run.state.is_scheduled()
            assert await result_store.read_parameters(
                task_run.state.state_details.task_parameters_id
            ) == {"parameters": {"x": i + 1}, "context": mock.ANY}

    async def test_map_with_implicitly_unmapped_kwargs(self):
        @task
        def bar(x: int, unmappable: int) -> Tuple[int, int]:
            return (x, unmappable)

        task_runs = bar.map([1, 2, 3], unmappable=42, deferred=True)

        assert len(task_runs) == 3

        result_store = await result_store_from_task(bar)

        for i, task_run in enumerate(task_runs):
            assert task_run.state.is_scheduled()
            assert await result_store.read_parameters(
                task_run.state.state_details.task_parameters_id
            ) == {"parameters": {"x": i + 1, "unmappable": 42}, "context": mock.ANY}

    async def test_async_map_with_implicitly_unmapped_kwargs(self):
        @task
        async def bar(x: int, unmappable: int) -> Tuple[int, int]:
            return (x, unmappable)

        task_runs = bar.map([1, 2, 3], unmappable=42, deferred=True)

        assert len(task_runs) == 3

        result_store = await result_store_from_task(bar)

        for i, task_run in enumerate(task_runs):
            assert task_run.state.is_scheduled()
            assert await result_store.read_parameters(
                task_run.state.state_details.task_parameters_id
            ) == {"parameters": {"x": i + 1, "unmappable": 42}, "context": mock.ANY}

    async def test_map_with_explicit_unmapped_kwargs(self):
        @task
        def bar(x: int, mappable: Iterable) -> Tuple[int, Iterable]:
            return (x, mappable)

        task_runs = bar.map(
            [1, 2, 3], mappable=unmapped(["some", "iterable"]), deferred=True
        )

        assert len(task_runs) == 3

        result_store = await result_store_from_task(bar)

        for i, task_run in enumerate(task_runs):
            assert task_run.state.is_scheduled()
            assert await result_store.read_parameters(
                task_run.state.state_details.task_parameters_id
            ) == {
                "parameters": {"x": i + 1, "mappable": ["some", "iterable"]},
                "context": mock.ANY,
            }

    async def test_async_map_with_explicit_unmapped_kwargs(self):
        @task
        async def bar(x: int, mappable: Iterable) -> Tuple[int, Iterable]:
            return (x, mappable)

        task_runs = bar.map(
            [1, 2, 3], mappable=unmapped(["some", "iterable"]), deferred=True
        )

        assert len(task_runs) == 3

        result_store = await result_store_from_task(bar)

        for i, task_run in enumerate(task_runs):
            assert task_run.state.is_scheduled()
            assert await result_store.read_parameters(
                task_run.state.state_details.task_parameters_id
            ) == {
                "parameters": {"x": i + 1, "mappable": ["some", "iterable"]},
                "context": mock.ANY,
            }
