import asyncio
import inspect
import os
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, AsyncGenerator, Iterable, Tuple
from unittest import mock

import pytest
from exceptiongroup import ExceptionGroup, catch

import prefect.results
from prefect import Task, task, unmapped
from prefect.blocks.core import Block
from prefect.client.orchestration import get_client
from prefect.client.schemas import TaskRun
from prefect.client.schemas.objects import StateType
from prefect.filesystems import LocalFileSystem
from prefect.results import ResultFactory
from prefect.server.api.task_runs import TaskQueue
from prefect.server.schemas.core import TaskRun as ServerTaskRun
from prefect.server.services.task_scheduling import TaskSchedulingTimeouts
from prefect.settings import (
    PREFECT_LOCAL_STORAGE_PATH,
    PREFECT_TASK_SCHEDULING_DEFAULT_STORAGE_BLOCK,
    PREFECT_TASK_SCHEDULING_PENDING_TASK_TIMEOUT,
    temporary_settings,
)
from prefect.task_worker import TaskWorker
from prefect.utilities.hashing import hash_objects

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient


async def result_factory_from_task(task) -> ResultFactory:
    return await ResultFactory.from_autonomous_task(task)


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

    result_factory = await result_factory_from_task(foo_task)
    await result_factory.read_parameters(
        task_run.state.state_details.task_parameters_id
    )


async def test_task_submission_with_parameters_reuses_default_storage_block(
    foo_task: Task, tmp_path: Path, prefect_client
):
    with temporary_settings(
        {
            PREFECT_TASK_SCHEDULING_DEFAULT_STORAGE_BLOCK: "local-file-system/my-tasks",
            PREFECT_LOCAL_STORAGE_PATH: tmp_path / "some-storage",
        }
    ):
        # The block will not exist initially
        with pytest.raises(ValueError, match="Unable to find block document"):
            await Block.load("local-file-system/my-tasks")

        foo_task_without_result_storage = foo_task.with_options(result_storage=None)
        task_run_future_a = foo_task_without_result_storage.apply_async((42,))

        storage_before = await Block.load("local-file-system/my-tasks")
        assert isinstance(storage_before, LocalFileSystem)
        assert storage_before.basepath == str(tmp_path / "some-storage")

        foo_task_without_result_storage = foo_task.with_options(result_storage=None)
        task_run_future_b = foo_task_without_result_storage.apply_async((24,))

        storage_after = await Block.load("local-file-system/my-tasks")
        assert isinstance(storage_after, LocalFileSystem)

        result_factory = await result_factory_from_task(foo_task)
        task_run_a = await prefect_client.read_task_run(task_run_future_a.task_run_id)
        task_run_b = await prefect_client.read_task_run(task_run_future_b.task_run_id)
        assert await result_factory.read_parameters(
            task_run_a.state.state_details.task_parameters_id
        ) == {"parameters": {"x": 42}, "context": mock.ANY}
        assert await result_factory.read_parameters(
            task_run_b.state.state_details.task_parameters_id
        ) == {"parameters": {"x": 24}, "context": mock.ANY}


async def test_task_submission_creates_a_scheduled_task_run(
    foo_task_with_result_storage, prefect_client
):
    task_run_future = foo_task_with_result_storage.apply_async((42,))
    task_run = await prefect_client.read_task_run(task_run_future.task_run_id)
    assert task_run.state.is_scheduled()
    assert task_run.state.state_details.deferred is True

    result_factory = await result_factory_from_task(foo_task_with_result_storage)

    parameters = await result_factory.read_parameters(
        task_run.state.state_details.task_parameters_id
    )

    assert parameters == {"parameters": {"x": 42}, "context": mock.ANY}


async def test_sync_task_not_awaitable_in_async_context(foo_task, prefect_client):
    task_run_future = foo_task.apply_async((42,))
    task_run = await prefect_client.read_task_run(task_run_future.task_run_id)
    assert task_run.state.is_scheduled()

    result_factory = await result_factory_from_task(foo_task)

    parameters = await result_factory.read_parameters(
        task_run.state.state_details.task_parameters_id
    )

    assert parameters == {"parameters": {"x": 42}, "context": mock.ANY}


async def test_async_task_submission_creates_a_scheduled_task_run(
    async_foo_task_with_result_storage, prefect_client
):
    task_run_future = async_foo_task_with_result_storage.apply_async((42,))
    task_run = await prefect_client.read_task_run(task_run_future.task_run_id)
    assert task_run.state.is_scheduled()

    result_factory = await result_factory_from_task(async_foo_task_with_result_storage)

    parameters = await result_factory.read_parameters(
        task_run.state.state_details.task_parameters_id
    )

    assert parameters == {"parameters": {"x": 42}, "context": mock.ANY}


async def test_scheduled_tasks_are_enqueued_server_side(
    foo_task_with_result_storage: Task, prefect_client
):
    task_run_future = foo_task_with_result_storage.apply_async((42,))
    task_run = await prefect_client.read_task_run(task_run_future.task_run_id)
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


@pytest.fixture
def enabled_task_scheduling_pending_task_timeout():
    with temporary_settings({PREFECT_TASK_SCHEDULING_PENDING_TASK_TIMEOUT: 30}):
        yield


async def test_scheduled_tasks_are_restored_at_server_startup(
    foo_task_with_result_storage: Task,
    prefect_client: "PrefectClient",
    enabled_task_scheduling_pending_task_timeout: None,
):
    # run one iteration of the timeouts service
    service = TaskSchedulingTimeouts()
    await service.start(loops=1)

    # schedule a task
    task_run_future = foo_task_with_result_storage.apply_async((42,))
    task_run = await prefect_client.read_task_run(task_run_future.task_run_id)
    assert task_run.state.is_scheduled()

    # pull the task from the queue to make sure it's cleared; this simulates when a task
    # server pulls a task, then the prefect server dies
    enqueued: TaskRun = await TaskQueue.for_key(task_run.task_key).get()
    assert enqueued.id == task_run.id

    # verify there is no other task in queue
    with pytest.raises(asyncio.QueueEmpty):
        await TaskQueue.for_key(task_run.task_key).get_nowait()

    # Run another loop to show that the task is NOT re-enqueued after the first run
    await service.start(loops=1)

    with pytest.raises(asyncio.QueueEmpty):
        await TaskQueue.for_key(task_run.task_key).get_nowait()

    # now emulate that we've restarted the Prefect server by resetting the
    # TaskSchedulingTimeouts service
    service = TaskSchedulingTimeouts()
    await service.start(loops=1)

    # the task will still be SCHEDULED
    task_run = await prefect_client.read_task_run(task_run.id)
    assert task_run.state.type == StateType.SCHEDULED

    # ...and it should be re-enqueued
    enqueued: TaskRun = await TaskQueue.for_key(task_run.task_key).get()
    assert enqueued.id == task_run.id


async def test_stuck_pending_tasks_are_reenqueued(
    foo_task_with_result_storage: Task,
    prefect_client: "PrefectClient",
    enabled_task_scheduling_pending_task_timeout: None,
):
    task_run_future = foo_task_with_result_storage.apply_async((42,))
    task_run = await prefect_client.read_task_run(task_run_future.task_run_id)
    assert task_run.state.is_scheduled()

    # now we simulate a stuck task by having the TaskWorker try to run it but fail
    server = TaskWorker(foo_task_with_result_storage)

    def assert_exception(exc_group: ExceptionGroup):
        assert len(exc_group.exceptions) == 1
        assert isinstance(exc_group.exceptions[0], ValueError)
        assert "woops" in str(exc_group.exceptions[0])

    with catch({ValueError: assert_exception}):
        with mock.patch(
            "prefect.task_worker.run_task_sync",
            side_effect=ValueError("woops"),
        ):
            await server.execute_task_run(task_run)

    # now the task will be in a stuck pending state
    task_run = await prefect_client.read_task_run(task_run.id)
    assert task_run.state.type == StateType.PENDING

    # first, run an iteration of the TaskSchedulingTimeouts loop service with the
    # setting disabled to demonstrate that it will not re-schedule the task
    with temporary_settings({PREFECT_TASK_SCHEDULING_PENDING_TASK_TIMEOUT: 0}):
        await TaskSchedulingTimeouts().start(loops=1)

    # the task will still be PENDING and not re-enqueued
    task_run = await prefect_client.read_task_run(task_run.id)
    assert task_run.state.type == StateType.PENDING

    # now run an iteration of the TaskSchedulingTimeouts loop service with an absurdly
    # long timeout so that it will never happen
    with temporary_settings({PREFECT_TASK_SCHEDULING_PENDING_TASK_TIMEOUT: 1000000}):
        await TaskSchedulingTimeouts().start(loops=1)

    # the task will still be PENDING
    task_run = await prefect_client.read_task_run(task_run.id)
    assert task_run.state.type == StateType.PENDING

    # now run an iteration of the TaskSchedulingTimeouts loop service with a short
    # timeout so we can sleep past it and ensure that this task run will get picked up
    with temporary_settings({PREFECT_TASK_SCHEDULING_PENDING_TASK_TIMEOUT: 0.1}):
        await asyncio.sleep(0.2)
        await TaskSchedulingTimeouts().start(loops=1)

    # now the task will now be SCHEDULED
    task_run = await prefect_client.read_task_run(task_run.id)
    assert task_run.state.type == StateType.SCHEDULED

    # ...and it should be re-enqueued
    enqueued: TaskRun = await TaskQueue.for_key(task_run.task_key).get()
    assert enqueued.id == task_run.id


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

        result_factory = await result_factory_from_task(async_foo_task)

        for i, task_run in enumerate(task_runs):
            assert task_run.state.is_scheduled()
            assert await result_factory.read_parameters(
                task_run.state.state_details.task_parameters_id
            ) == {"parameters": {"x": i + 1}, "context": mock.ANY}

    async def test_map_with_implicitly_unmapped_kwargs(self):
        @task
        def bar(x: int, unmappable: int) -> Tuple[int, int]:
            return (x, unmappable)

        task_runs = bar.map([1, 2, 3], unmappable=42, deferred=True)

        assert len(task_runs) == 3

        result_factory = await result_factory_from_task(bar)

        for i, task_run in enumerate(task_runs):
            assert task_run.state.is_scheduled()
            assert await result_factory.read_parameters(
                task_run.state.state_details.task_parameters_id
            ) == {"parameters": {"x": i + 1, "unmappable": 42}, "context": mock.ANY}

    async def test_async_map_with_implicitly_unmapped_kwargs(self):
        @task
        async def bar(x: int, unmappable: int) -> Tuple[int, int]:
            return (x, unmappable)

        task_runs = bar.map([1, 2, 3], unmappable=42, deferred=True)

        assert len(task_runs) == 3

        result_factory = await result_factory_from_task(bar)

        for i, task_run in enumerate(task_runs):
            assert task_run.state.is_scheduled()
            assert await result_factory.read_parameters(
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

        result_factory = await result_factory_from_task(bar)

        for i, task_run in enumerate(task_runs):
            assert task_run.state.is_scheduled()
            assert await result_factory.read_parameters(
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

        result_factory = await result_factory_from_task(bar)

        for i, task_run in enumerate(task_runs):
            assert task_run.state.is_scheduled()
            assert await result_factory.read_parameters(
                task_run.state.state_details.task_parameters_id
            ) == {
                "parameters": {"x": i + 1, "mappable": ["some", "iterable"]},
                "context": mock.ANY,
            }


class TestTaskKey:
    def test_task_key_includes_qualname_and_source_file_hash(self):
        def some_fn():
            pass

        t = Task(fn=some_fn)
        source_file = os.path.abspath(inspect.getsourcefile(some_fn))
        task_origin_hash = hash_objects(t.name, source_file)
        assert t.task_key == f"{some_fn.__qualname__}-{task_origin_hash}"

    def test_task_key_handles_unknown_source_file(self, monkeypatch):
        def some_fn():
            pass

        monkeypatch.setattr(inspect, "getsourcefile", lambda x: None)
        t = Task(fn=some_fn)
        assert t.task_key == f"{some_fn.__qualname__}-unknown-source-file"
