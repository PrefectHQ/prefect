import asyncio
import uuid
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncGenerator, Iterable, Tuple
from unittest import mock

import pytest

import prefect.results
from prefect import Task, task, unmapped
from prefect.blocks.core import Block
from prefect.client.orchestration import get_client
from prefect.client.schemas import TaskRun
from prefect.filesystems import LocalFileSystem
from prefect.results import ResultStore, get_or_create_default_task_scheduling_storage
from prefect.server.schemas.core import TaskRun as ServerTaskRun
from prefect.server.schemas.states import Scheduled
from prefect.server.task_queue import get_task_queue_backend
from prefect.server.task_queue.memory import TaskQueueBackend as MemoryTaskQueueBackend
from prefect.settings import (
    PREFECT_TASK_SCHEDULING_DEFAULT_STORAGE_BLOCK,
    temporary_settings,
)
from prefect.task_worker import read_parameters

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient


def _make_task_run(task_key: str) -> ServerTaskRun:
    """Create a minimal TaskRun for queue testing."""
    return ServerTaskRun(
        id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        task_key=task_key,
        dynamic_key=str(uuid.uuid4()),
        state=Scheduled(),
    )


async def result_store_from_task(task: Task[Any, Any]) -> ResultStore:
    return await ResultStore(
        result_storage=await get_or_create_default_task_scheduling_storage()
    ).update_for_task(task)


@pytest.fixture
def local_filesystem(tmp_path: Path) -> LocalFileSystem:
    block = LocalFileSystem(basepath=str(tmp_path))
    block.save(f"test-fs-{uuid.uuid4()}", overwrite=True)
    return block


@pytest.fixture(autouse=True)
async def clear_scheduled_task_queues():
    await MemoryTaskQueueBackend().reset()
    yield
    await MemoryTaskQueueBackend().reset()


@pytest.fixture(autouse=True)
async def clear_cached_filesystems():
    prefect.results._default_storages.clear()
    yield
    prefect.results._default_storages.clear()


@pytest.fixture
def foo_task() -> Task[Any, int]:
    @task
    def foo(x: int) -> int:
        print(x)
        return x

    return foo


@pytest.fixture
def async_foo_task() -> Task[Any, int]:
    @task
    async def async_foo(x: int) -> int:
        print(x)
        return x

    return async_foo


@pytest.fixture
def foo_task_with_result_storage(
    foo_task: Task[Any, int], local_filesystem: LocalFileSystem
) -> Task[Any, int]:
    return foo_task.with_options(result_storage=local_filesystem)


@pytest.fixture
def async_foo_task_with_result_storage(
    async_foo_task: Task[Any, int], local_filesystem: LocalFileSystem
) -> Task[Any, int]:
    return async_foo_task.with_options(result_storage=local_filesystem)


async def test_task_submission_with_parameters_uses_default_storage(
    foo_task: Task[Any, int], prefect_client: "PrefectClient"
):
    foo_task_without_result_storage = foo_task.with_options(result_storage=None)
    task_run_future = foo_task_without_result_storage.apply_async((42,))
    task_run = await prefect_client.read_task_run(task_run_future.task_run_id)

    result_store = await result_store_from_task(foo_task)
    assert task_run.state is not None
    assert task_run.state.state_details is not None
    assert task_run.state.state_details.task_parameters_id is not None
    await read_parameters(result_store, task_run.state.state_details.task_parameters_id)


async def test_task_submission_with_parameters_reuses_default_storage_block(
    foo_task: Task[Any, int], tmp_path: Path, prefect_client: "PrefectClient"
):
    with temporary_settings(
        {
            PREFECT_TASK_SCHEDULING_DEFAULT_STORAGE_BLOCK: "local-file-system/my-tasks",
        }
    ):
        block = LocalFileSystem(basepath=str(tmp_path / "some-storage"))
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
        assert await read_parameters(
            result_store, task_run_a.state.state_details.task_parameters_id
        ) == {"parameters": {"x": 42}, "context": mock.ANY}
        assert await read_parameters(
            result_store, task_run_b.state.state_details.task_parameters_id
        ) == {"parameters": {"x": 24}, "context": mock.ANY}


async def test_task_submission_creates_a_scheduled_task_run(
    foo_task_with_result_storage: Task[Any, int], prefect_client: "PrefectClient"
):
    task_run_future = foo_task_with_result_storage.apply_async((42,))
    task_run = await prefect_client.read_task_run(task_run_future.task_run_id)
    assert task_run.state is not None
    assert task_run.state.is_scheduled()
    assert task_run.state.state_details.deferred is True

    result_store = await result_store_from_task(foo_task_with_result_storage)

    parameters = await read_parameters(
        result_store, task_run.state.state_details.task_parameters_id
    )

    assert parameters == {"parameters": {"x": 42}, "context": mock.ANY}


async def test_sync_task_not_awaitable_in_async_context(
    foo_task: Task[Any, int], prefect_client: "PrefectClient"
):
    task_run_future = foo_task.apply_async((42,))
    task_run = await prefect_client.read_task_run(task_run_future.task_run_id)
    assert task_run.state.is_scheduled()

    result_store = await result_store_from_task(foo_task)

    parameters = await read_parameters(
        result_store, task_run.state.state_details.task_parameters_id
    )

    assert parameters == {"parameters": {"x": 42}, "context": mock.ANY}


async def test_async_task_submission_creates_a_scheduled_task_run(
    async_foo_task_with_result_storage: Task[Any, int],
    prefect_client: "PrefectClient",
):
    task_run_future = async_foo_task_with_result_storage.apply_async((42,))
    task_run = await prefect_client.read_task_run(task_run_future.task_run_id)
    assert task_run.state.is_scheduled()

    result_store = await result_store_from_task(async_foo_task_with_result_storage)

    parameters = await read_parameters(
        result_store, task_run.state.state_details.task_parameters_id
    )

    assert parameters == {"parameters": {"x": 42}, "context": mock.ANY}


async def test_scheduled_tasks_are_enqueued_server_side(
    foo_task_with_result_storage: Task[Any, int],
    in_memory_prefect_client: "PrefectClient",
    monkeypatch: pytest.MonkeyPatch,
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

    backend = get_task_queue_backend()
    enqueued_run: ServerTaskRun = await backend.get(client_run.task_key)

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
    foo_task: Task[Any, int],
):
    # Regression test for https://github.com/PrefectHQ/prefect/issues/13674
    # where executing a task would cause it to be enqueue server-side
    # and executed twice.
    foo_task(x=42)

    backend = get_task_queue_backend()
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(backend.get(foo_task.task_key), timeout=0.1)


@pytest.fixture
async def prefect_client() -> AsyncGenerator["PrefectClient", None]:
    async with get_client() as client:
        yield client


class TestCall:
    async def test_call(self, async_foo_task: Task[Any, int]):
        result = await async_foo_task(42)

        assert result == 42

    async def test_call_with_return_state(self, async_foo_task: Task[Any, int]):
        state = await async_foo_task(42, return_state=True)

        assert state.is_completed()

        assert await state.result() == 42


class TestMap:
    async def test_map(self, async_foo_task: Task[Any, int]):
        task_runs = async_foo_task.map([1, 2, 3], deferred=True)

        assert len(task_runs) == 3

        result_store = await result_store_from_task(async_foo_task)

        for i, task_run in enumerate(task_runs):
            assert task_run.state.is_scheduled()
            assert await read_parameters(
                result_store, task_run.state.state_details.task_parameters_id
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
            assert task_run.state.state_details is not None
            assert task_run.state.state_details.task_parameters_id is not None
            assert await read_parameters(
                result_store, task_run.state.state_details.task_parameters_id
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
            assert task_run.state.state_details is not None
            assert task_run.state.state_details.task_parameters_id is not None
            assert await read_parameters(
                result_store, task_run.state.state_details.task_parameters_id
            ) == {"parameters": {"x": i + 1, "unmappable": 42}, "context": mock.ANY}

    async def test_map_with_explicit_unmapped_kwargs(self):
        @task
        def bar(x: int, mappable: Iterable[str]) -> Tuple[int, Iterable[str]]:
            return (x, mappable)

        task_runs = bar.map(
            [1, 2, 3], mappable=unmapped(["some", "iterable"]), deferred=True
        )

        assert len(task_runs) == 3

        result_store = await result_store_from_task(bar)

        for i, task_run in enumerate(task_runs):
            assert task_run.state.is_scheduled()
            assert task_run.state.state_details is not None
            assert task_run.state.state_details.task_parameters_id is not None
            assert await read_parameters(
                result_store, task_run.state.state_details.task_parameters_id
            ) == {
                "parameters": {"x": i + 1, "mappable": ["some", "iterable"]},
                "context": mock.ANY,
            }

    async def test_async_map_with_explicit_unmapped_kwargs(self):
        @task
        async def bar(x: int, mappable: Iterable[str]) -> Tuple[int, Iterable[str]]:
            return (x, mappable)

        task_runs = bar.map(
            [1, 2, 3], mappable=unmapped(["some", "iterable"]), deferred=True
        )

        assert len(task_runs) == 3

        result_store = await result_store_from_task(bar)

        for i, task_run in enumerate(task_runs):
            assert task_run.state.is_scheduled()
            assert task_run.state.state_details is not None
            assert task_run.state.state_details.task_parameters_id is not None
            assert await read_parameters(
                result_store, task_run.state.state_details.task_parameters_id
            ) == {
                "parameters": {"x": i + 1, "mappable": ["some", "iterable"]},
                "context": mock.ANY,
            }


async def test_prioritize_keys_round_robin():
    """prioritize_keys rotates the key list based on offset."""
    keys = ["a", "b", "c"]
    assert MemoryTaskQueueBackend.prioritize_keys(keys, 0) == ["a", "b", "c"]
    assert MemoryTaskQueueBackend.prioritize_keys(keys, 1) == ["b", "c", "a"]
    assert MemoryTaskQueueBackend.prioritize_keys(keys, 2) == ["c", "a", "b"]
    assert MemoryTaskQueueBackend.prioritize_keys(keys, 3) == ["a", "b", "c"]  # wraps


async def test_prioritize_keys_empty():
    assert MemoryTaskQueueBackend.prioritize_keys([], 5) == []


async def test_fixed_order_multiqueue_starves_later_keys():
    """Demonstrate that fixed iteration order (the old algorithm) causes starvation.

    This validates that our round-robin fix is solving a real problem by showing
    the old approach serves key_b LAST (after all 5 key_a items), while the new
    backend.get_many() serves key_b within the first 4 results.
    """
    backend = MemoryTaskQueueBackend()
    await backend.reset()

    for _ in range(5):
        await backend.enqueue(_make_task_run("key_a"))
    await backend.enqueue(_make_task_run("key_b"))

    # Old algorithm: fixed iteration order, no rotation (mimics pre-protocol MultiQueue)
    # Each call checks queues in the same order and returns the first available item.
    async def fixed_order_get_one(task_keys: list[str], timeout: float = 1):
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            for key in task_keys:  # always same order — key_a checked first
                scheduled, _ = backend._get_or_create_queues(key)
                try:
                    return scheduled.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            await asyncio.sleep(0.01)
        raise asyncio.TimeoutError

    old_results = []
    for _ in range(6):
        run = await fixed_order_get_one(["key_a", "key_b"])
        old_results.append(run.task_key)
    # Old algorithm: key_a monopolizes — key_b is served last
    assert old_results == ["key_a"] * 5 + ["key_b"], (
        f"Expected key_a to starve key_b with fixed order, got: {old_results}"
    )

    # Now verify the backend.get_many() does NOT starve key_b
    await backend.reset()
    for _ in range(5):
        await backend.enqueue(_make_task_run("key_a"))
    await backend.enqueue(_make_task_run("key_b"))

    new_results = []
    for i in range(6):
        try:
            task_run = await backend.get_many(["key_a", "key_b"], timeout=0.1, offset=i)
            new_results.append(task_run.task_key)
        except asyncio.TimeoutError:
            break

    # Round-robin: key_b should appear before all key_a items drain
    assert "key_b" in new_results[:4], (
        f"key_b should be served before all key_a items drain, got: {new_results}"
    )


async def test_multiqueue_retry_priority_per_key():
    """Retry items for a key are served before scheduled items for that key."""
    backend = MemoryTaskQueueBackend()
    await backend.reset()

    scheduled_run = _make_task_run("key_a")
    retry_run = _make_task_run("key_a")

    await backend.enqueue(scheduled_run)
    await backend.retry(retry_run)

    first = await backend.get_many(["key_a"], timeout=0.5, offset=0)
    assert first.id == retry_run.id, "Retry item should be served before scheduled"


async def test_get_task_queue_backend_rejects_invalid_module():
    """Factory raises ValueError when the configured module lacks TaskQueueBackend."""
    from prefect.settings import (
        PREFECT_TASK_SCHEDULING_BACKEND,
    )

    with temporary_settings({PREFECT_TASK_SCHEDULING_BACKEND: "json"}):
        with pytest.raises(ValueError, match="does not export a TaskQueueBackend"):
            get_task_queue_backend()
