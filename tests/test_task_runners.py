import asyncio
import uuid
from concurrent.futures import Future
from typing import Any, Iterable, Optional
from uuid import UUID

import pytest

from prefect._internal.concurrency.api import create_call, from_async
from prefect.context import TagsContext, tags
from prefect.futures import PrefectFuture, PrefectWrappedFuture
from prefect.results import _default_task_scheduling_storages
from prefect.states import Completed, Running
from prefect.task_runners import PrefectTaskRunner, ThreadPoolTaskRunner
from prefect.task_server import serve
from prefect.tasks import task


@task
def my_test_task(param1, param2):
    return param1, param2


@task
async def my_test_async_task(param1, param2):
    return param1, param2


@task
def context_matters(param1=None, param2=None):
    return TagsContext.get().current_tags


@task
async def context_matters_async(param1=None, param2=None):
    return TagsContext.get().current_tags


class MockFuture(PrefectWrappedFuture):
    def __init__(self, data: Any = 42):
        super().__init__(uuid.uuid4(), Future())
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
    def test_duplicate(self):
        runner = ThreadPoolTaskRunner()
        duplicate_runner = runner.duplicate()
        assert isinstance(duplicate_runner, ThreadPoolTaskRunner)
        assert duplicate_runner is not runner

    def test_runner_must_be_started(self):
        runner = ThreadPoolTaskRunner()
        with pytest.raises(RuntimeError, match="Task runner is not started"):
            runner.submit(my_test_task, {})

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


class TestPrefectTaskRunner:
    @pytest.fixture(autouse=True)
    def clear_cache(self):
        _default_task_scheduling_storages.clear()

    @pytest.fixture
    async def task_server(self, use_hosted_api_server):
        call = from_async.call_soon_in_new_thread(
            create_call(
                serve,
                my_test_task,
                my_test_async_task,
                context_matters,
                context_matters_async,
            )
        )
        # Give the server time to start
        await asyncio.sleep(0.1)
        yield
        call.cancel()

    def test_duplicate(self):
        runner = PrefectTaskRunner()
        duplicate_runner = runner.duplicate()
        assert isinstance(duplicate_runner, PrefectTaskRunner)
        assert duplicate_runner is not runner

    def test_runner_must_be_started(self):
        runner = PrefectTaskRunner()
        with pytest.raises(RuntimeError, match="Task runner is not started"):
            runner.submit(my_test_task, {})

    @pytest.mark.usefixtures("task_server")
    def test_submit_sync_task(self):
        with PrefectTaskRunner() as runner:
            parameters = {"param1": 1, "param2": 2}
            future = runner.submit(my_test_task, parameters)
            assert isinstance(future, PrefectFuture)
            assert isinstance(future.task_run_id, UUID)

            assert future.result() == (1, 2)

    @pytest.mark.usefixtures("task_server")
    def test_submit_async_task(self):
        with PrefectTaskRunner() as runner:
            parameters = {"param1": 1, "param2": 2}
            future = runner.submit(my_test_async_task, parameters)
            assert isinstance(future, PrefectFuture)
            assert isinstance(future.task_run_id, UUID)

            assert future.result() == (1, 2)

    @pytest.mark.usefixtures("task_server")
    def test_submit_sync_task_receives_context(self):
        with tags("tag1", "tag2"):
            with PrefectTaskRunner() as runner:
                future = runner.submit(context_matters, {})
                assert isinstance(future, PrefectFuture)
                assert isinstance(future.task_run_id, UUID)

                assert future.result() == {"tag1", "tag2"}

    @pytest.mark.usefixtures("task_server")
    def test_submit_async_task_receives_context(self):
        with tags("tag1", "tag2"):
            with PrefectTaskRunner() as runner:
                future = runner.submit(context_matters_async, {})
                assert isinstance(future, PrefectFuture)
                assert isinstance(future.task_run_id, UUID)

                assert future.result() == {"tag1", "tag2"}

    @pytest.mark.usefixtures("task_server")
    def test_map_sync_task(self):
        with PrefectTaskRunner() as runner:
            parameters = {"param1": [1, 2, 3], "param2": [4, 5, 6]}
            futures = runner.map(my_test_task, parameters)
            assert isinstance(futures, Iterable)
            assert all(isinstance(future, PrefectFuture) for future in futures)
            assert all(isinstance(future.task_run_id, UUID) for future in futures)

            results = [future.result() for future in futures]
            assert results == [(1, 4), (2, 5), (3, 6)]

    @pytest.mark.usefixtures("task_server")
    def test_map_async_task(self):
        with PrefectTaskRunner() as runner:
            parameters = {"param1": [1, 2, 3], "param2": [4, 5, 6]}
            futures = runner.map(my_test_async_task, parameters)
            assert isinstance(futures, Iterable)
            assert all(isinstance(future, PrefectFuture) for future in futures)
            assert all(isinstance(future.task_run_id, UUID) for future in futures)

            results = [future.result() for future in futures]
            assert results == [(1, 4), (2, 5), (3, 6)]

    @pytest.mark.usefixtures("task_server")
    def test_map_sync_task_with_context(self):
        with tags("tag1", "tag2"):
            with PrefectTaskRunner() as runner:
                parameters = {"param1": [1, 2, 3], "param2": [4, 5, 6]}
                futures = runner.map(context_matters, parameters)
                assert isinstance(futures, Iterable)
                assert all(isinstance(future, PrefectFuture) for future in futures)
                assert all(isinstance(future.task_run_id, UUID) for future in futures)

                results = [future.result() for future in futures]
                assert results == [{"tag1", "tag2"}] * 3

    @pytest.mark.usefixtures("task_server")
    def test_map_async_task_with_context(self):
        with tags("tag1", "tag2"):
            with PrefectTaskRunner() as runner:
                parameters = {"param1": [1, 2, 3], "param2": [4, 5, 6]}
                futures = runner.map(context_matters_async, parameters)
                assert isinstance(futures, Iterable)
                assert all(isinstance(future, PrefectFuture) for future in futures)
                assert all(isinstance(future.task_run_id, UUID) for future in futures)

                results = [future.result() for future in futures]
                assert results == [{"tag1", "tag2"}] * 3

    @pytest.mark.usefixtures("task_server")
    def test_map_with_future_resolved_to_list(self):
        with PrefectTaskRunner() as runner:
            future = MockFuture(data=[1, 2, 3])
            parameters = {"param1": future, "param2": future}
            futures = runner.map(my_test_task, parameters)
            assert isinstance(futures, Iterable)
            assert all(isinstance(future, PrefectFuture) for future in futures)
            assert all(isinstance(future.task_run_id, UUID) for future in futures)

            results = [future.result() for future in futures]
            assert results == [(1, 1), (2, 2), (3, 3)]
