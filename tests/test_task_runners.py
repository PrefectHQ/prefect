import threading
import time
import uuid
from concurrent.futures import Future
from pathlib import Path
from typing import Any, Callable, Iterable, Optional
from uuid import UUID

import pytest

from prefect.client.orchestration import PrefectClient
from prefect.context import TagsContext, tags
from prefect.events import emit_event
from prefect.events.schemas.events import Event
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


@task(task_run_name=f"my_test_task_{uuid.uuid4()}")
def my_test_task(param1: Any, param2: Any) -> tuple[Any, Any]:
    return param1, param2


@task(task_run_name=f"my_test_async_task_{uuid.uuid4()}")
async def my_test_async_task(param1: Any, param2: Any) -> tuple[Any, Any]:
    return param1, param2


@task(task_run_name=f"context_matters_{uuid.uuid4()}")
def context_matters(param1: Any = None, param2: Any = None) -> set[str]:
    return TagsContext.get().current_tags


@task(task_run_name=f"context_matters_async_{uuid.uuid4()}")
async def context_matters_async(param1: Any = None, param2: Any = None) -> set[str]:
    return TagsContext.get().current_tags


@task(task_run_name=f"task_that_raises_exception_{uuid.uuid4()}")
def task_that_raises_exception() -> None:
    raise ValueError("Test exception from subprocess")


@task(task_run_name=f"async_task_that_raises_exception_{uuid.uuid4()}")
async def async_task_that_raises_exception() -> None:
    raise RuntimeError("Test async exception from subprocess")


@task(task_run_name=f"task_with_large_data_{uuid.uuid4()}")
def task_with_large_data(data: list[int]) -> tuple[int, int]:
    # Process large data structure
    return len(data), sum(data)


@task(task_run_name=f"task_with_unpicklable_param_{uuid.uuid4()}")
def task_with_unpicklable_param(func: Callable[[int], Any]) -> Any:
    # This will fail because lambdas can't be pickled normally
    return func(42)


@task(task_run_name=f"slow_task_{uuid.uuid4()}")
def slow_task(duration: float = 0.1) -> str:
    import time

    time.sleep(duration)
    return "completed"


@task(task_run_name=f"event_emitting_task_{uuid.uuid4()}")
def event_emitting_task() -> str:
    emit_event(
        event="prefect.process-pool.test-event",
        resource={"prefect.resource.id": "prefect.test.process-pool-event"},
    )
    return "emitted"


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

    def test_duplicate_preserves_subprocess_message_processors(self):
        def _processor_factory():
            def _processor(message_type, message_payload):
                return message_type, message_payload

            return _processor

        runner = ProcessPoolTaskRunner(
            max_workers=4,
            subprocess_message_processor_factories=[_processor_factory],
        )
        duplicate_runner = runner.duplicate()

        assert duplicate_runner.subprocess_message_processor_factories == (
            _processor_factory,
        )

    def test_duplicate_preserves_subprocess_message_processors_for_compat_subclass(
        self,
    ):
        class _CompatProcessPoolRunner(ProcessPoolTaskRunner):
            def __init__(self, max_workers=None):
                super().__init__(max_workers=max_workers)

        def _processor_factory():
            def _processor(message_type, message_payload):
                return message_type, message_payload

            return _processor

        runner = _CompatProcessPoolRunner(max_workers=4)
        runner.subprocess_message_processor_factories = [_processor_factory]

        duplicate_runner = runner.duplicate()

        assert isinstance(duplicate_runner, _CompatProcessPoolRunner)
        assert duplicate_runner.subprocess_message_processor_factories == (
            _processor_factory,
        )

    def test_subprocess_message_processors_property_updates_factories(self):
        def _processor_factory():
            def _processor(message_type, message_payload):
                return message_type, message_payload

            return _processor

        runner = ProcessPoolTaskRunner(max_workers=4)
        runner.subprocess_message_processor_factories = [_processor_factory]

        assert runner.subprocess_message_processor_factories == (_processor_factory,)

    def test_subprocess_message_processors_property_rejects_started_runner(self):
        runner = ProcessPoolTaskRunner(max_workers=1)
        runner._started = True

        with pytest.raises(
            RuntimeError,
            match="Cannot configure subprocess message processor factories while task runner is started",
        ):
            runner.subprocess_message_processor_factories = []

    def test_set_subprocess_message_processors_method_still_supported(self):
        def _processor_factory():
            def _processor(message_type, message_payload):
                return message_type, message_payload

            return _processor

        runner = ProcessPoolTaskRunner(max_workers=4)
        runner.set_subprocess_message_processor_factories([_processor_factory])

        assert runner.subprocess_message_processor_factories == (_processor_factory,)

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

    def test_submit_with_wait_for(self):
        """
        Test for issue #19113: ProcessPoolTaskRunner should handle wait_for without pickle errors.
        This ensures futures can be passed via wait_for and are resolved before subprocess execution.
        """

        @task
        def add_one(x: int) -> int:
            return x + 1

        @flow(task_runner=ProcessPoolTaskRunner(max_workers=2))
        def test_flow():
            future_a = add_one.submit(1)
            future_b = add_one.submit(2, wait_for=[future_a])
            future_c = add_one.submit(3, wait_for=[future_b])
            return future_a.result(), future_b.result(), future_c.result()

        result = test_flow()
        assert result == (2, 3, 4)

    def test_submit_with_future_as_parameter(self):
        """
        Test for issue #19113: ProcessPoolTaskRunner should handle futures as parameters.
        This ensures futures can be passed as task parameters and are resolved before subprocess execution.
        """

        @task
        def multiply_by_two(x: int) -> int:
            return x * 2

        @flow(task_runner=ProcessPoolTaskRunner(max_workers=2))
        def test_flow():
            future_a = multiply_by_two.submit(5)
            future_b = multiply_by_two.submit(future_a)  # Pass future as parameter
            return future_a.result(), future_b.result()

        result = test_flow()
        assert result == (10, 20)

    def test_submit_with_multiple_futures_as_parameters(self):
        """
        Test futures as parameters with multiple dependencies.
        Ensures complex future resolution works correctly.
        """

        @task
        def add(x: int, y: int) -> int:
            return x + y

        @flow(task_runner=ProcessPoolTaskRunner(max_workers=2))
        def test_flow():
            future_a = add.submit(1, 2)
            future_b = add.submit(3, 4)
            future_c = add.submit(future_a, future_b)  # Both params are futures
            return future_a.result(), future_b.result(), future_c.result()

        result = test_flow()
        assert result == (3, 7, 10)

    def test_submit_remains_non_blocking(self):
        """
        Test that submit() returns immediately even when waiting for futures.
        This ensures the fix maintains non-blocking behavior.
        """

        @task
        def slow_add(x: int, y: int) -> int:
            time.sleep(0.5)
            return x + y

        @flow(task_runner=ProcessPoolTaskRunner(max_workers=2))
        def test_flow():
            import time

            start = time.time()
            future_a = slow_add.submit(1, 2)
            future_b = slow_add.submit(3, 4, wait_for=[future_a])

            # submit() should return quickly, even though future_a hasn't completed
            submit_duration = time.time() - start
            assert submit_duration < 0.5, "submit() should be non-blocking"

            # Now wait for results
            return future_a.result(), future_b.result()

        result = test_flow()
        assert result == (3, 7)

    @pytest.mark.usefixtures("reset_worker_events")
    def test_subprocess_events_are_forwarded_with_related_resources(
        self, asserting_events_worker
    ):
        @flow(task_runner=ProcessPoolTaskRunner(max_workers=1))
        def test_flow():
            return event_emitting_task.submit().result()

        assert test_flow() == "emitted"

        asserting_events_worker.drain()
        matching_events = [
            event
            for event in asserting_events_worker._client.events
            if event.event == "prefect.process-pool.test-event"
        ]
        assert len(matching_events) == 1

        related_ids = {resource.id for resource in matching_events[0].related}
        assert any(
            resource_id.startswith("prefect.task-run.") for resource_id in related_ids
        )
        assert any(
            resource_id.startswith("prefect.flow-run.") for resource_id in related_ids
        )

    def test_subprocess_logs_are_forwarded_to_parent_log_worker(self, monkeypatch):
        from queue import Queue
        from unittest.mock import MagicMock

        from prefect import task_runners as task_runners_module

        runner = ProcessPoolTaskRunner(max_workers=1)
        runner._subprocess_message_queue = Queue()

        forwarded_log_worker = MagicMock()
        monkeypatch.setattr("prefect.task_runners.APILogWorker", forwarded_log_worker)

        forwarder_thread = threading.Thread(
            target=runner._forward_subprocess_messages, daemon=True
        )
        forwarder_thread.start()

        payload = {"message": "subprocess-log-forwarding"}
        runner._subprocess_message_queue.put(
            (task_runners_module._PROCESS_POOL_MESSAGE_TYPE_LOG, payload)
        )
        runner._subprocess_message_queue.put(
            task_runners_module._PROCESS_POOL_MESSAGE_QUEUE_SHUTDOWN
        )
        forwarder_thread.join(timeout=3)

        assert not forwarder_thread.is_alive()
        forwarded_log_worker.instance().send.assert_called_once_with(payload)

    def test_subprocess_message_processor_can_drop_duplicate_logs(self, monkeypatch):
        from queue import Queue
        from unittest.mock import MagicMock

        from prefect import task_runners as task_runners_module

        def _global_dedupe_processor_factory():
            seen_messages: set[tuple[str, int, str]] = set()

            def _processor(message_type, message_payload):
                if (
                    message_type != task_runners_module._PROCESS_POOL_MESSAGE_TYPE_LOG
                    or not isinstance(message_payload, dict)
                ):
                    return message_type, message_payload

                if message_payload.get("dedupe_scope") != "global":
                    return message_type, message_payload

                flow_run_id = message_payload.get("flow_run_id")
                level = message_payload.get("level")
                message = message_payload.get("message")
                if (
                    not isinstance(flow_run_id, str)
                    or not isinstance(level, int)
                    or not isinstance(message, str)
                ):
                    return message_type, message_payload

                dedupe_key = (flow_run_id, level, message)
                if dedupe_key in seen_messages:
                    return None
                seen_messages.add(dedupe_key)
                return message_type, message_payload

            return _processor

        runner = ProcessPoolTaskRunner(
            max_workers=1,
            subprocess_message_processor_factories=[_global_dedupe_processor_factory],
        )
        runner._subprocess_message_queue = Queue()

        forwarded_log_worker = MagicMock()
        monkeypatch.setattr("prefect.task_runners.APILogWorker", forwarded_log_worker)

        forwarder_thread = threading.Thread(
            target=runner._forward_subprocess_messages, daemon=True
        )
        forwarder_thread.start()

        tagged_payload_1 = {
            "flow_run_id": "flow-1",
            "task_run_id": "task-1",
            "name": "prefect.task_runs.custom_global",
            "level": 20,
            "timestamp": "2026-02-26T00:00:00+00:00",
            "dedupe_scope": "global",
            "message": "Running with dbt=1.x",
        }
        tagged_payload_2 = {
            **tagged_payload_1,
            "task_run_id": "task-2",
        }
        regular_payload = {
            "flow_run_id": "flow-1",
            "task_run_id": "task-3",
            "name": "prefect.task_runs",
            "level": 20,
            "timestamp": "2026-02-26T00:00:01+00:00",
            "message": "not deduped",
        }

        runner._subprocess_message_queue.put(
            (task_runners_module._PROCESS_POOL_MESSAGE_TYPE_LOG, tagged_payload_1)
        )
        runner._subprocess_message_queue.put(
            (task_runners_module._PROCESS_POOL_MESSAGE_TYPE_LOG, tagged_payload_2)
        )
        runner._subprocess_message_queue.put(
            (task_runners_module._PROCESS_POOL_MESSAGE_TYPE_LOG, regular_payload)
        )
        runner._subprocess_message_queue.put(
            (task_runners_module._PROCESS_POOL_MESSAGE_TYPE_LOG, regular_payload)
        )
        runner._subprocess_message_queue.put(
            task_runners_module._PROCESS_POOL_MESSAGE_QUEUE_SHUTDOWN
        )
        forwarder_thread.join(timeout=3)

        assert not forwarder_thread.is_alive()
        sent_payloads = [
            call.args[0] for call in forwarded_log_worker.instance().send.call_args_list
        ]
        assert sent_payloads.count(tagged_payload_1) == 1
        assert sent_payloads.count(regular_payload) == 2

    def test_subprocess_message_processor_can_transform_log_payload(self, monkeypatch):
        from queue import Queue
        from unittest.mock import MagicMock

        from prefect import task_runners as task_runners_module

        def _transform_processor_factory():
            def _processor(message_type, message_payload):
                if (
                    message_type != task_runners_module._PROCESS_POOL_MESSAGE_TYPE_LOG
                    or not isinstance(message_payload, dict)
                ):
                    return message_type, message_payload
                transformed_payload = dict(message_payload)
                transformed_payload["message"] = (
                    f"transformed::{transformed_payload.get('message', '')}"
                )
                return message_type, transformed_payload

            return _processor

        runner = ProcessPoolTaskRunner(
            max_workers=1,
            subprocess_message_processor_factories=[_transform_processor_factory],
        )
        runner._subprocess_message_queue = Queue()

        forwarded_log_worker = MagicMock()
        monkeypatch.setattr("prefect.task_runners.APILogWorker", forwarded_log_worker)

        forwarder_thread = threading.Thread(
            target=runner._forward_subprocess_messages, daemon=True
        )
        forwarder_thread.start()

        payload = {"message": "subprocess-log-forwarding"}
        runner._subprocess_message_queue.put(
            (task_runners_module._PROCESS_POOL_MESSAGE_TYPE_LOG, payload)
        )
        runner._subprocess_message_queue.put(
            task_runners_module._PROCESS_POOL_MESSAGE_QUEUE_SHUTDOWN
        )
        forwarder_thread.join(timeout=3)

        assert not forwarder_thread.is_alive()
        forwarded_log_worker.instance().send.assert_called_once_with(
            {"message": "transformed::subprocess-log-forwarding"}
        )

    def test_subprocess_event_forwarding_disables_after_runtime_error(
        self, monkeypatch
    ):
        from queue import Queue
        from unittest.mock import MagicMock

        from prefect import task_runners as task_runners_module

        runner = ProcessPoolTaskRunner(max_workers=1)
        runner._subprocess_message_queue = Queue()

        forwarded_events_worker = MagicMock()
        forwarded_events_worker.instance.return_value.send.side_effect = RuntimeError(
            "worker stopped"
        )
        monkeypatch.setattr(
            "prefect.task_runners.EventsWorker", forwarded_events_worker
        )

        forwarder_thread = threading.Thread(
            target=runner._forward_subprocess_messages, daemon=True
        )
        forwarder_thread.start()

        event_payload = Event(
            event="prefect.process-pool.test-event",
            resource={"prefect.resource.id": "prefect.test.process-pool-event"},
        )

        runner._subprocess_message_queue.put(
            (task_runners_module._PROCESS_POOL_MESSAGE_TYPE_EVENT, event_payload)
        )
        runner._subprocess_message_queue.put(
            (task_runners_module._PROCESS_POOL_MESSAGE_TYPE_EVENT, event_payload)
        )
        runner._subprocess_message_queue.put(
            task_runners_module._PROCESS_POOL_MESSAGE_QUEUE_SHUTDOWN
        )
        forwarder_thread.join(timeout=3)

        assert not forwarder_thread.is_alive()
        forwarded_events_worker.instance.assert_called_once()
        forwarded_events_worker.instance.return_value.send.assert_called_once_with(
            event_payload
        )

    def test_subprocess_log_forwarding_disables_after_runtime_error(self, monkeypatch):
        from queue import Queue
        from unittest.mock import MagicMock

        from prefect import task_runners as task_runners_module

        runner = ProcessPoolTaskRunner(max_workers=1)
        runner._subprocess_message_queue = Queue()

        forwarded_log_worker = MagicMock()
        forwarded_log_worker.instance.return_value.send.side_effect = RuntimeError(
            "worker stopped"
        )
        monkeypatch.setattr("prefect.task_runners.APILogWorker", forwarded_log_worker)

        forwarder_thread = threading.Thread(
            target=runner._forward_subprocess_messages, daemon=True
        )
        forwarder_thread.start()

        payload = {"message": "subprocess-log-forwarding"}
        runner._subprocess_message_queue.put(
            (task_runners_module._PROCESS_POOL_MESSAGE_TYPE_LOG, payload)
        )
        runner._subprocess_message_queue.put(
            (task_runners_module._PROCESS_POOL_MESSAGE_TYPE_LOG, payload)
        )
        runner._subprocess_message_queue.put(
            task_runners_module._PROCESS_POOL_MESSAGE_QUEUE_SHUTDOWN
        )
        forwarder_thread.join(timeout=3)

        assert not forwarder_thread.is_alive()
        forwarded_log_worker.instance.assert_called_once()
        forwarded_log_worker.instance.return_value.send.assert_called_once_with(payload)

    def test_initialize_process_pool_worker_without_queue_resets_forwarding(
        self, monkeypatch
    ):
        from unittest.mock import MagicMock

        from prefect import task_runners as task_runners_module

        set_client_override = MagicMock()
        set_log_sink = MagicMock()
        monkeypatch.setattr(
            "prefect.task_runners.EventsWorker.set_client_override", set_client_override
        )
        monkeypatch.setattr("prefect.task_runners.set_api_log_sink", set_log_sink)

        task_runners_module._initialize_process_pool_worker(None)

        set_client_override.assert_called_once_with(None)
        set_log_sink.assert_called_once_with(None)

    def test_initialize_process_pool_worker_with_queue_sets_forwarding(
        self, monkeypatch
    ):
        from queue import Queue
        from unittest.mock import MagicMock

        from prefect import task_runners as task_runners_module

        message_queue = Queue()
        set_client_override = MagicMock()
        set_log_sink = MagicMock()
        monkeypatch.setattr(
            "prefect.task_runners.EventsWorker.set_client_override", set_client_override
        )
        monkeypatch.setattr("prefect.task_runners.set_api_log_sink", set_log_sink)

        task_runners_module._initialize_process_pool_worker(message_queue)

        set_client_override.assert_called_once_with(
            task_runners_module.ProcessPoolForwardingEventsClient,
            event_queue=message_queue,
            item_type=task_runners_module._PROCESS_POOL_MESSAGE_TYPE_EVENT,
        )

        set_log_sink.assert_called_once()
        log_sink = set_log_sink.call_args.args[0]
        payload = {"message": "forward-me"}
        log_sink(payload)

        assert message_queue.get_nowait() == (
            task_runners_module._PROCESS_POOL_MESSAGE_TYPE_LOG,
            payload,
        )

    def test_stop_message_forwarding_keeps_state_if_thread_is_still_alive(self):
        from unittest.mock import MagicMock

        from prefect import task_runners as task_runners_module

        runner = ProcessPoolTaskRunner(max_workers=1)
        message_queue = MagicMock()
        forwarding_thread = MagicMock()
        forwarding_thread.is_alive.return_value = True

        runner._subprocess_message_queue = message_queue
        runner._message_forwarding_thread = forwarding_thread

        runner._stop_message_forwarding()

        message_queue.put_nowait.assert_called_once_with(
            task_runners_module._PROCESS_POOL_MESSAGE_QUEUE_SHUTDOWN
        )
        forwarding_thread.join.assert_called_once_with(timeout=5)
        message_queue.close.assert_not_called()
        message_queue.join_thread.assert_not_called()
        assert runner._subprocess_message_queue is message_queue
        assert runner._message_forwarding_thread is forwarding_thread

    def test_stop_message_forwarding_cleans_up_when_thread_stops(self):
        from unittest.mock import MagicMock

        from prefect import task_runners as task_runners_module

        runner = ProcessPoolTaskRunner(max_workers=1)
        message_queue = MagicMock()
        forwarding_thread = MagicMock()
        forwarding_thread.is_alive.return_value = False

        runner._subprocess_message_queue = message_queue
        runner._message_forwarding_thread = forwarding_thread

        runner._stop_message_forwarding()

        message_queue.put_nowait.assert_called_once_with(
            task_runners_module._PROCESS_POOL_MESSAGE_QUEUE_SHUTDOWN
        )
        forwarding_thread.join.assert_called_once_with(timeout=5)
        message_queue.close.assert_called_once()
        message_queue.join_thread.assert_called_once()
        assert runner._subprocess_message_queue is None
        assert runner._message_forwarding_thread is None


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
