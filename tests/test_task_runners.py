import time
import uuid
from concurrent.futures import Future
from pathlib import Path
from typing import Any, Callable, Iterable, Optional
from uuid import UUID

import pytest

from prefect.client.orchestration import PrefectClient
from prefect.context import TagsContext, tags
from prefect.filesystems import LocalFileSystem
from prefect.flows import flow
from prefect.futures import PrefectFuture, PrefectWrappedFuture
from prefect.results import _default_storages
from prefect.settings import (
    PREFECT_DEFAULT_RESULT_STORAGE_BLOCK,
    PREFECT_TASK_RUNNER_THREAD_POOL_MAX_WORKERS,
    PREFECT_TASK_SCHEDULING_DEFAULT_STORAGE_BLOCK,
    PREFECT_TASKS_RUNNER_PROCESS_POOL_MAX_WORKERS,
    temporary_settings,
)
from prefect.states import Completed, Running
from prefect.task_runners import (
    PrefectTaskRunner,
    ProcessPoolTaskRunner,
    ThreadPoolTaskRunner,
)
from prefect.task_worker import TaskWorker
from prefect.tasks import task


@task
def my_test_task(param1: Any, param2: Any) -> tuple[Any, Any]:
    return param1, param2


@task
async def my_test_async_task(param1: Any, param2: Any) -> tuple[Any, Any]:
    return param1, param2


@task
def context_matters(param1: Any = None, param2: Any = None) -> set[str]:
    return TagsContext.get().current_tags


@task
async def context_matters_async(param1: Any = None, param2: Any = None) -> set[str]:
    return TagsContext.get().current_tags


@task
def task_that_raises_exception() -> None:
    raise ValueError("Test exception from subprocess")


@task
async def async_task_that_raises_exception() -> None:
    raise RuntimeError("Test async exception from subprocess")


@task
def task_with_large_data(data: list[int]) -> tuple[int, int]:
    # Process large data structure
    return len(data), sum(data)


@task
def task_with_unpicklable_param(func: Callable[[int], Any]) -> Any:
    # This will fail because lambdas can't be pickled normally
    return func(42)


@task
def slow_task(duration: float = 0.1) -> str:
    import time

    time.sleep(duration)
    return "completed"


class MockFuture(PrefectWrappedFuture[Any, Future[Any]]):
    def __init__(self, data: Any = 42):
        super().__init__(uuid.uuid4(), Future[Any]())
        self._data = data
        self._state = Running()

    def wait(self, timeout: Optional[float] = None) -> None:
        self._state = Completed(data=self._data)

    def result(
        self,
        timeout: Optional[float] = None,
        raise_on_failure: bool = True,
    ) -> Any:
        self.wait()
        return self._state.result()

    @property
    def state(self) -> Any:
        return self._state


class TestThreadPoolTaskRunner:
    @pytest.fixture(autouse=True)
    def default_storage_setting(self, tmp_path):
        name = str(uuid.uuid4())
        LocalFileSystem(basepath=tmp_path).save(name)
        with temporary_settings(
            {
                PREFECT_DEFAULT_RESULT_STORAGE_BLOCK: f"local-file-system/{name}",
                PREFECT_TASK_SCHEDULING_DEFAULT_STORAGE_BLOCK: f"local-file-system/{name}",
            }
        ):
            yield

    def test_duplicate(self):
        runner = ThreadPoolTaskRunner(max_workers=100)
        duplicate_runner = runner.duplicate()
        assert isinstance(duplicate_runner, ThreadPoolTaskRunner)
        assert duplicate_runner is not runner
        assert duplicate_runner == runner

    def test_runner_must_be_started(self):
        runner = ThreadPoolTaskRunner()
        with pytest.raises(RuntimeError, match="Task runner is not started"):
            runner.submit(my_test_task, {})

    def test_set_max_workers(self):
        with ThreadPoolTaskRunner(max_workers=2) as runner:
            assert runner._executor._max_workers == 2

    def test_set_max_workers_through_settings(self):
        with temporary_settings({PREFECT_TASK_RUNNER_THREAD_POOL_MAX_WORKERS: 5}):
            with ThreadPoolTaskRunner() as runner:
                assert runner._executor._max_workers == 5

    def test_submit_sync_task(self):
        with ThreadPoolTaskRunner() as runner:
            parameters = {"param1": 1, "param2": 2}
            future = runner.submit(my_test_task, parameters)
            assert isinstance(future, PrefectFuture)
            assert isinstance(future.task_run_id, UUID)
            assert isinstance(future.wrapped_future, Future)

            assert future.result() == (1, 2)

    def test_submit_async_task(self):
        with ThreadPoolTaskRunner() as runner:
            parameters = {"param1": 1, "param2": 2}
            future = runner.submit(my_test_async_task, parameters)
            assert isinstance(future, PrefectFuture)
            assert isinstance(future.task_run_id, UUID)
            assert isinstance(future.wrapped_future, Future)

            assert future.result() == (1, 2)

    def test_submit_sync_task_receives_context(self):
        with tags("tag1", "tag2"):
            with ThreadPoolTaskRunner() as runner:
                future = runner.submit(context_matters, {})
                assert isinstance(future, PrefectFuture)
                assert isinstance(future.task_run_id, UUID)
                assert isinstance(future.wrapped_future, Future)

                assert future.result() == {"tag1", "tag2"}

    def test_submit_async_task_receives_context(self):
        with tags("tag1", "tag2"):
            with ThreadPoolTaskRunner() as runner:
                future = runner.submit(context_matters_async, {})
                assert isinstance(future, PrefectFuture)
                assert isinstance(future.task_run_id, UUID)
                assert isinstance(future.wrapped_future, Future)

                assert future.result() == {"tag1", "tag2"}

    def test_map_sync_task(self):
        with ThreadPoolTaskRunner() as runner:
            parameters = {"param1": [1, 2, 3], "param2": [4, 5, 6]}
            futures = runner.map(my_test_task, parameters)
            assert isinstance(futures, Iterable)
            assert all(isinstance(future, PrefectFuture) for future in futures)
            assert all(isinstance(future.task_run_id, UUID) for future in futures)
            assert all(isinstance(future.wrapped_future, Future) for future in futures)

            results = [future.result() for future in futures]
            assert results == [(1, 4), (2, 5), (3, 6)]

    def test_map_async_task(self):
        with ThreadPoolTaskRunner() as runner:
            parameters = {"param1": [1, 2, 3], "param2": [4, 5, 6]}
            futures = runner.map(my_test_async_task, parameters)
            assert isinstance(futures, Iterable)
            assert all(isinstance(future, PrefectFuture) for future in futures)
            assert all(isinstance(future.task_run_id, UUID) for future in futures)
            assert all(isinstance(future.wrapped_future, Future) for future in futures)

            results = [future.result() for future in futures]
            assert results == [(1, 4), (2, 5), (3, 6)]

    def test_map_sync_task_with_context(self):
        with tags("tag1", "tag2"):
            with ThreadPoolTaskRunner() as runner:
                parameters = {"param1": [1, 2, 3], "param2": [4, 5, 6]}
                futures = runner.map(context_matters, parameters)
                assert isinstance(futures, Iterable)
                assert all(isinstance(future, PrefectFuture) for future in futures)
                assert all(isinstance(future.task_run_id, UUID) for future in futures)
                assert all(
                    isinstance(future.wrapped_future, Future) for future in futures
                )

                results = [future.result() for future in futures]
                assert results == [{"tag1", "tag2"}] * 3

    def test_map_async_task_with_context(self):
        with tags("tag1", "tag2"):
            with ThreadPoolTaskRunner() as runner:
                parameters = {"param1": [1, 2, 3], "param2": [4, 5, 6]}
                futures = runner.map(context_matters_async, parameters)
                assert isinstance(futures, Iterable)
                assert all(isinstance(future, PrefectFuture) for future in futures)
                assert all(isinstance(future.task_run_id, UUID) for future in futures)
                assert all(
                    isinstance(future.wrapped_future, Future) for future in futures
                )

                results = [future.result() for future in futures]
                assert results == [{"tag1", "tag2"}] * 3

    def test_map_with_future_resolved_to_list(self):
        with ThreadPoolTaskRunner() as runner:
            future = MockFuture(data=[1, 2, 3])
            parameters = {"param1": future, "param2": future}
            futures = runner.map(my_test_task, parameters)
            assert isinstance(futures, Iterable)
            assert all(isinstance(future, PrefectFuture) for future in futures)
            assert all(isinstance(future.task_run_id, UUID) for future in futures)
            assert all(isinstance(future.wrapped_future, Future) for future in futures)

            results = [future.result() for future in futures]
            assert results == [(1, 1), (2, 2), (3, 3)]

    def test_handles_recursively_submitted_tasks(self):
        """
        Regression test for https://github.com/PrefectHQ/prefect/issues/14194.

        This test ensures that the ThreadPoolTaskRunner doesn't place an upper limit on the
        number of submitted tasks active at once. The highest default max workers on a
        ThreadPoolExecutor is 32, so this test submits 33 tasks recursively, which will
        deadlock without the ThreadPoolTaskRunner setting the max_workers to sys.maxsize.
        """

        @task
        def recursive_task(n):
            if n == 0:
                return n
            time.sleep(0.1)
            future = recursive_task.submit(n - 1)
            return future.result()

        @flow
        def test_flow():
            return recursive_task.submit(33)

        assert test_flow().result() == 0


class TestProcessPoolTaskRunner:
    @pytest.fixture(autouse=True)
    def default_storage_setting(self, tmp_path: Path):
        name = str(uuid.uuid4())
        LocalFileSystem(basepath=tmp_path).save(name)
        with temporary_settings(
            {
                PREFECT_DEFAULT_RESULT_STORAGE_BLOCK: f"local-file-system/{name}",
                PREFECT_TASK_SCHEDULING_DEFAULT_STORAGE_BLOCK: f"local-file-system/{name}",
            }
        ):
            yield

    def test_duplicate(self):
        runner = ProcessPoolTaskRunner(max_workers=4)
        duplicate_runner = runner.duplicate()
        assert isinstance(duplicate_runner, ProcessPoolTaskRunner)
        assert duplicate_runner is not runner
        assert duplicate_runner == runner

    def test_runner_must_be_started(self):
        runner = ProcessPoolTaskRunner()
        with pytest.raises(RuntimeError, match="Task runner is not started"):
            runner.submit(my_test_task, {})

    def test_set_max_workers(self):
        with ProcessPoolTaskRunner(max_workers=2) as runner:
            assert runner._executor._max_workers == 2

    def test_set_max_workers_through_settings(self):
        with temporary_settings({PREFECT_TASKS_RUNNER_PROCESS_POOL_MAX_WORKERS: 3}):
            with ProcessPoolTaskRunner() as runner:
                assert runner._executor._max_workers == 3

    def test_default_max_workers_uses_cpu_count(self):
        import multiprocessing

        with ProcessPoolTaskRunner() as runner:
            # Should default to cpu_count when setting is None
            assert runner._max_workers == multiprocessing.cpu_count()

    def test_submit_sync_task(self):
        with ProcessPoolTaskRunner() as runner:
            parameters = {"param1": 1, "param2": 2}
            future = runner.submit(my_test_task, parameters)
            assert isinstance(future, PrefectFuture)
            assert isinstance(future.task_run_id, UUID)

            result = future.result()
            assert result == (1, 2)

    def test_submit_async_task(self):
        with ProcessPoolTaskRunner() as runner:
            parameters = {"param1": 3, "param2": 4}
            future = runner.submit(my_test_async_task, parameters)
            assert isinstance(future, PrefectFuture)
            assert isinstance(future.task_run_id, UUID)

            result = future.result()
            assert result == (3, 4)

    def test_submit_sync_task_receives_context(self):
        with tags("tag1", "tag2"):
            with ProcessPoolTaskRunner() as runner:
                future = runner.submit(context_matters, {})
                assert isinstance(future, PrefectFuture)
                assert isinstance(future.task_run_id, UUID)

                result = future.result()
                assert result == {"tag1", "tag2"}

    def test_submit_async_task_receives_context(self):
        with tags("tag1", "tag2"):
            with ProcessPoolTaskRunner() as runner:
                future = runner.submit(context_matters_async, {})
                assert isinstance(future, PrefectFuture)
                assert isinstance(future.task_run_id, UUID)

                result = future.result()
                assert result == {"tag1", "tag2"}

    def test_map_sync_task(self):
        with ProcessPoolTaskRunner() as runner:
            parameters = {"param1": [1, 2, 3], "param2": [4, 5, 6]}
            futures = runner.map(my_test_task, parameters)
            assert isinstance(futures, Iterable)
            assert all(isinstance(future, PrefectFuture) for future in futures)
            assert all(isinstance(future.task_run_id, UUID) for future in futures)

            results = [future.result() for future in futures]
            assert results == [(1, 4), (2, 5), (3, 6)]

    def test_map_async_task(self):
        with ProcessPoolTaskRunner() as runner:
            parameters = {"param1": [1, 2, 3], "param2": [4, 5, 6]}
            futures = runner.map(my_test_async_task, parameters)
            assert isinstance(futures, Iterable)
            assert all(isinstance(future, PrefectFuture) for future in futures)
            assert all(isinstance(future.task_run_id, UUID) for future in futures)

            results = [future.result() for future in futures]
            assert results == [(1, 4), (2, 5), (3, 6)]

    def test_map_sync_task_with_context(self):
        with tags("tag1", "tag2"):
            with ProcessPoolTaskRunner() as runner:
                parameters = {"param1": [1, 2, 3], "param2": [4, 5, 6]}
                futures = runner.map(context_matters, parameters)
                assert isinstance(futures, Iterable)
                assert all(isinstance(future, PrefectFuture) for future in futures)
                assert all(isinstance(future.task_run_id, UUID) for future in futures)

                results = [future.result() for future in futures]
                assert results == [{"tag1", "tag2"}] * 3

    def test_map_async_task_with_context(self):
        with tags("tag1", "tag2"):
            with ProcessPoolTaskRunner() as runner:
                parameters = {"param1": [1, 2, 3], "param2": [4, 5, 6]}
                futures = runner.map(context_matters_async, parameters)
                assert isinstance(futures, Iterable)
                assert all(isinstance(future, PrefectFuture) for future in futures)
                assert all(isinstance(future.task_run_id, UUID) for future in futures)

                results = [future.result() for future in futures]
                assert results == [{"tag1", "tag2"}] * 3

    def test_map_with_future_resolved_to_list(self):
        with ProcessPoolTaskRunner() as runner:
            future = MockFuture(data=[1, 2, 3])
            parameters = {"param1": future, "param2": future}
            futures = runner.map(my_test_task, parameters)
            assert isinstance(futures, Iterable)
            assert all(isinstance(future, PrefectFuture) for future in futures)
            assert all(isinstance(future.task_run_id, UUID) for future in futures)

            results = [future.result() for future in futures]
            assert results == [(1, 1), (2, 2), (3, 3)]

    def test_task_raises_exception(self):
        with ProcessPoolTaskRunner() as runner:
            future = runner.submit(task_that_raises_exception, {})

            with pytest.raises(ValueError, match="Test exception from subprocess"):
                future.result()

    def test_async_task_raises_exception(self):
        with ProcessPoolTaskRunner() as runner:
            future = runner.submit(async_task_that_raises_exception, {})

            with pytest.raises(
                RuntimeError, match="Test async exception from subprocess"
            ):
                future.result()

    def test_submit_task_with_large_parameters(self):
        large_data = list(range(10000))
        with ProcessPoolTaskRunner() as runner:
            future = runner.submit(task_with_large_data, {"data": large_data})
            result = future.result()
            assert result == (10000, sum(range(10000)))

    def test_cancel_all(self):
        with ProcessPoolTaskRunner(max_workers=1) as runner:
            # Submit a slow task
            runner.submit(slow_task, {"duration": 1.0})

            # Cancel all tasks
            runner.cancel_all()

            # The executor should be shut down
            assert runner._executor is None

    def test_executor_shutdown_on_exit(self):
        runner = ProcessPoolTaskRunner()
        with runner:
            assert runner._executor is not None

        # After exiting context, executor should be shut down
        assert runner._executor is None

    def test_equality(self):
        runner1 = ProcessPoolTaskRunner(max_workers=4)
        runner2 = ProcessPoolTaskRunner(max_workers=4)
        runner3 = ProcessPoolTaskRunner(max_workers=2)

        assert runner1 == runner2
        assert runner1 != runner3
        assert runner1 != "not a runner"

    def test_handles_recursively_submitted_tasks(self):
        """
        Test similar to ThreadPoolTaskRunner but adapted for ProcessPool.
        This ensures ProcessPoolTaskRunner can handle recursive task submission.
        """

        @task
        def recursive_task(n):
            if n == 0:
                return n
            time.sleep(0.1)
            future = recursive_task.submit(n - 1)
            return future.result()

        @flow(task_runner=ProcessPoolTaskRunner())
        def test_flow():
            return recursive_task.submit(5)  # Using smaller number for process pool

        assert test_flow().result() == 0


class TestPrefectTaskRunner:
    @pytest.fixture(autouse=True)
    def clear_cache(self):
        _default_storages.clear()

    @pytest.fixture
    async def task_worker(self, use_hosted_api_server):
        return TaskWorker(
            my_test_task,
            my_test_async_task,
            context_matters,
            context_matters_async,
        )

    def test_duplicate(self):
        runner = PrefectTaskRunner()
        duplicate_runner = runner.duplicate()
        assert isinstance(duplicate_runner, PrefectTaskRunner)
        assert duplicate_runner is not runner

    def test_runner_must_be_started(self):
        runner = PrefectTaskRunner()
        with pytest.raises(RuntimeError, match="Task runner is not started"):
            runner.submit(my_test_task, {})

    async def test_submit_sync_task(
        self, events_pipeline, task_worker: TaskWorker, prefect_client: PrefectClient
    ):
        with PrefectTaskRunner() as runner:
            parameters = {"param1": 1, "param2": 2}
            future = runner.submit(my_test_task, parameters)
            assert isinstance(future, PrefectFuture)
            assert isinstance(future.task_run_id, UUID)

            task_run = await prefect_client.read_task_run(future.task_run_id)
            await task_worker.execute_task_run(task_run)
            await events_pipeline.process_events()
            updated_task_run = await prefect_client.read_task_run(future.task_run_id)
            assert updated_task_run.state.is_completed()

            assert future.result(timeout=10) == (1, 2)

    async def test_submit_async_task(
        self, events_pipeline, task_worker: TaskWorker, prefect_client: PrefectClient
    ):
        with PrefectTaskRunner() as runner:
            parameters = {"param1": 1, "param2": 2}
            future = runner.submit(my_test_async_task, parameters)
            assert isinstance(future, PrefectFuture)
            assert isinstance(future.task_run_id, UUID)

            task_run = await prefect_client.read_task_run(future.task_run_id)
            await task_worker.execute_task_run(task_run)
            await events_pipeline.process_events()
            updated_task_run = await prefect_client.read_task_run(future.task_run_id)
            assert updated_task_run.state.is_completed()

            assert future.result(timeout=10) == (1, 2)

    async def test_submit_sync_task_receives_context(
        self, events_pipeline, task_worker: TaskWorker, prefect_client: PrefectClient
    ):
        with tags("tag1", "tag2"):
            with PrefectTaskRunner() as runner:
                future = runner.submit(context_matters, {})
                assert isinstance(future, PrefectFuture)
                assert isinstance(future.task_run_id, UUID)

                task_run = await prefect_client.read_task_run(future.task_run_id)
                await task_worker.execute_task_run(task_run)
                await events_pipeline.process_events()
                updated_task_run = await prefect_client.read_task_run(
                    future.task_run_id
                )
                assert updated_task_run.state.is_completed()

                assert future.result(timeout=10) == {"tag1", "tag2"}

    async def test_submit_async_task_receives_context(
        self, events_pipeline, task_worker: TaskWorker, prefect_client: PrefectClient
    ):
        with tags("tag1", "tag2"):
            with PrefectTaskRunner() as runner:
                future = runner.submit(context_matters_async, {})
                assert isinstance(future, PrefectFuture)
                assert isinstance(future.task_run_id, UUID)

                task_run = await prefect_client.read_task_run(future.task_run_id)
                await task_worker.execute_task_run(task_run)
                await events_pipeline.process_events()
                updated_task_run = await prefect_client.read_task_run(
                    future.task_run_id
                )
                assert updated_task_run.state.is_completed()

                assert future.result(timeout=10) == {"tag1", "tag2"}

    async def test_map_sync_task(self, events_pipeline, prefect_client: PrefectClient):
        with PrefectTaskRunner() as runner:
            parameters = {"param1": [1, 2, 3], "param2": [4, 5, 6]}
            futures = runner.map(my_test_task, parameters)
            assert isinstance(futures, Iterable)
            assert all(isinstance(future, PrefectFuture) for future in futures)
            assert all(isinstance(future.task_run_id, UUID) for future in futures)

            for future in futures:
                task_run = await prefect_client.read_task_run(future.task_run_id)
                await TaskWorker(my_test_task).execute_task_run(task_run)

            await events_pipeline.process_events()

            for future in futures:
                updated_task_run = await prefect_client.read_task_run(
                    future.task_run_id
                )
                assert updated_task_run.state.is_completed()

            results = [future.result(timeout=10) for future in futures]
            assert results == [(1, 4), (2, 5), (3, 6)]

    async def test_map_async_task(
        self, events_pipeline, task_worker: TaskWorker, prefect_client: PrefectClient
    ):
        with PrefectTaskRunner() as runner:
            parameters = {"param1": [1, 2, 3], "param2": [4, 5, 6]}
            futures = runner.map(my_test_async_task, parameters)
            assert isinstance(futures, Iterable)
            assert all(isinstance(future, PrefectFuture) for future in futures)
            assert all(isinstance(future.task_run_id, UUID) for future in futures)

            for future in futures:
                task_run = await prefect_client.read_task_run(future.task_run_id)
                await task_worker.execute_task_run(task_run)

            await events_pipeline.process_events()

            for future in futures:
                updated_task_run = await prefect_client.read_task_run(
                    future.task_run_id
                )
                assert updated_task_run.state.is_completed()

            results = [future.result(timeout=10) for future in futures]
            assert results == [(1, 4), (2, 5), (3, 6)]

    async def test_map_sync_task_with_context(
        self, events_pipeline, prefect_client: PrefectClient
    ):
        with tags("tag1", "tag2"):
            with PrefectTaskRunner() as runner:
                parameters = {"param1": [1, 2, 3], "param2": [4, 5, 6]}
                futures = runner.map(context_matters, parameters)
                assert isinstance(futures, Iterable)
                assert all(isinstance(future, PrefectFuture) for future in futures)
                assert all(isinstance(future.task_run_id, UUID) for future in futures)

            for future in futures:
                task_run = await prefect_client.read_task_run(future.task_run_id)
                await TaskWorker(context_matters).execute_task_run(task_run)

            await events_pipeline.process_events()

            for future in futures:
                updated_task_run = await prefect_client.read_task_run(
                    future.task_run_id
                )
                assert updated_task_run.state.is_completed()

                results = [future.result(timeout=10) for future in futures]
                assert results == [{"tag1", "tag2"}] * 3

    async def test_map_async_task_with_context(
        self, events_pipeline, task_worker: TaskWorker, prefect_client: PrefectClient
    ):
        with tags("tag1", "tag2"):
            with PrefectTaskRunner() as runner:
                parameters = {"param1": [1, 2, 3], "param2": [4, 5, 6]}
                futures = runner.map(context_matters_async, parameters)
                assert isinstance(futures, Iterable)
                assert all(isinstance(future, PrefectFuture) for future in futures)
                assert all(isinstance(future.task_run_id, UUID) for future in futures)

                for future in futures:
                    task_run = await prefect_client.read_task_run(future.task_run_id)
                    await task_worker.execute_task_run(task_run)

                await events_pipeline.process_events()

                for future in futures:
                    updated_task_run = await prefect_client.read_task_run(
                        future.task_run_id
                    )
                    assert updated_task_run.state.is_completed()

                results = [future.result(timeout=10) for future in futures]
                assert results == [{"tag1", "tag2"}] * 3

    async def test_map_with_future_resolved_to_list(
        self, events_pipeline, prefect_client: PrefectClient
    ):
        with PrefectTaskRunner() as runner:
            future = MockFuture(data=[1, 2, 3])
            parameters = {"param1": future, "param2": future}
            futures = runner.map(my_test_task, parameters)
            assert isinstance(futures, Iterable)
            assert all(isinstance(future, PrefectFuture) for future in futures)
            assert all(isinstance(future.task_run_id, UUID) for future in futures)

            for future in futures:
                task_run = await prefect_client.read_task_run(future.task_run_id)
                await TaskWorker(my_test_task).execute_task_run(task_run)

            await events_pipeline.process_events()

            for future in futures:
                updated_task_run = await prefect_client.read_task_run(
                    future.task_run_id
                )
                assert updated_task_run.state.is_completed()

            results = [future.result(timeout=10) for future in futures]
            assert results == [(1, 1), (2, 2), (3, 3)]
