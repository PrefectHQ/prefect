import asyncio
import contextlib
import multiprocessing
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional
from unittest.mock import ANY, MagicMock, call

import pytest

from prefect._internal.concurrency.api import create_call, from_async, from_sync
from prefect._internal.concurrency.services import (
    BatchedQueueService,
    QueueService,
    drain_on_exit,
    drain_on_exit_async,
)
from prefect._internal.concurrency.threads import wait_for_global_loop_exit
from prefect.settings import (
    PREFECT_LOGGING_INTERNAL_LEVEL,
    PREFECT_TEST_MODE,
    temporary_settings,
)


class MockService(QueueService[int]):
    mock = MagicMock()

    def __init__(self, index: Optional[int] = None) -> None:
        if index is not None:
            super().__init__(index)
        else:
            super().__init__()

    async def _handle(self, item: int):
        # Checkpoint to catch errors where async cancellation has occurred
        await asyncio.sleep(0)
        self.mock(self, item)
        print(f"Handled item {item} for {self}")


class MockBatchedService(BatchedQueueService[int]):
    _max_batch_size = 2
    mock = MagicMock()

    def __init__(self, index: Optional[int] = None) -> None:
        if index is not None:
            super().__init__(index)
        else:
            super().__init__()

    async def _handle_batch(self, items: List[int]):
        # Checkpoint to catch errors where async cancellation has occurred
        await asyncio.sleep(0)
        self.mock(self, items)
        print(f"Handled batch for {self}")


class _BacklogMixin:
    """
    Holds items in the queue until `release` is set, so a backlog builds up, then
    handles them without suspending.
    """

    release: threading.Event
    handled: List[int]
    # The queue size when other work on the event loop first got to run
    queue_sizes_seen_by_other_work: List[int]

    @contextlib.asynccontextmanager
    async def _lifespan(self):
        await asyncio.to_thread(self.release.wait)
        # Runs the first time the service lets the event loop do other work
        asyncio.get_running_loop().call_soon(
            lambda: self.queue_sizes_seen_by_other_work.append(self._queue.qsize())
        )
        yield


class BacklogService(_BacklogMixin, QueueService[int]):
    async def _handle(self, item: int):
        self.handled.append(item)


class BatchedBacklogService(_BacklogMixin, BatchedQueueService[int]):
    _max_batch_size = 10_000

    async def _handle_batch(self, items: List[int]):
        self.handled.extend(items)


@pytest.fixture(params=[BacklogService, BatchedBacklogService])
def backlog_service_type(request: pytest.FixtureRequest):
    service_type = request.param
    service_type.release = threading.Event()
    service_type.handled = []
    service_type.queue_sizes_seen_by_other_work = []
    yield service_type
    service_type.release.set()
    service_type.drain_all()


@pytest.fixture(autouse=True)
def reset_mock_services():
    yield

    # Reset mocks
    MockService.mock.reset_mock(side_effect=True)
    MockBatchedService.mock.reset_mock(side_effect=True)

    # Drain all items from the queue
    MockService.drain_all()
    MockBatchedService.drain_all()

    # Shutdown the global loop
    wait_for_global_loop_exit()


def test_instance_returns_instance():
    instance = MockService.instance()
    assert isinstance(instance, MockService)


def test_instance_returns_same_instance():
    instance = MockService.instance()
    assert MockService.instance() is instance


def test_instance_returns_new_instance_after_stopping():
    instance = MockService.instance()
    instance._stop()
    new_instance = MockService.instance()
    assert new_instance is not instance
    assert isinstance(new_instance, MockService)


def test_instance_returns_new_instance_with_unique_key():
    instance = MockService.instance(1)
    new_instance = MockService.instance(2)
    assert new_instance is not instance
    assert isinstance(new_instance, MockService)


def test_different_subclasses_have_unique_instances():
    instance = MockService.instance()
    assert isinstance(instance, MockService)
    new_instance = MockBatchedService.instance()
    assert new_instance is not instance
    assert isinstance(new_instance, MockBatchedService)


def test_instance_returns_same_instance_after_error():
    event = threading.Event()

    def on_handle(*_):
        event.set()
        raise ValueError("Oh no")

    instance = MockService.instance()
    instance.mock.side_effect = on_handle
    instance.send(1)

    # Wait for the service to actually handle the item
    event.wait()

    new_instance = MockService.instance()
    assert new_instance is instance
    assert isinstance(new_instance, MockService)

    instance.mock.side_effect = None

    # The instance can be used still
    new_instance.send(2)
    new_instance.drain()
    new_instance.mock.assert_has_calls([call(instance, 1), call(instance, 2)])


def test_instance_returns_new_instance_after_base_exception():
    event = threading.Event()

    def on_handle(*_):
        event.set()
        raise BaseException("Oh no")

    instance = MockService.instance()
    instance.mock.side_effect = on_handle
    instance.send(1)

    # Wait for the service to actually handle the item
    event.wait()
    instance.mock.reset_mock(side_effect=True)

    new_instance = MockService.instance()
    assert new_instance is not instance
    assert isinstance(new_instance, MockService)

    # The new instance can be used
    new_instance.send(2)
    new_instance.drain()
    new_instance.mock.assert_called_once_with(new_instance, 2)


def test_instance_returns_new_instance_when_cached_instance_is_stopped():
    failures = iter([True])

    class FailingLifespanService(MockService):
        @contextlib.asynccontextmanager
        async def _lifespan(self):
            if next(failures, False):
                raise ValueError("Oh no")
            yield

    # A lifespan that fails as soon as the service starts stops it while
    # `instance()` is still creating it; it must not remain cached
    instance = FailingLifespanService.instance()
    instance.drain()
    assert instance._stopped
    assert QueueService._instances.get(instance._key) is not instance

    # Even if a stopped instance is cached, it must not be returned
    QueueService._instances[instance._key] = instance
    new_instance = FailingLifespanService.instance()
    assert new_instance is not instance
    assert not new_instance._stopped

    new_instance.send(1)
    new_instance.drain()
    new_instance.mock.assert_called_once_with(new_instance, 1)


def test_stopped_instance_does_not_evict_newer_instance_with_same_key():
    instance = MockService.instance()
    instance._stop()
    new_instance = MockService.instance()
    assert new_instance is not instance

    instance._remove_instance()

    assert MockService.instance() is new_instance


def test_concurrent_cleanup_does_not_evict_replacement(monkeypatch: pytest.MonkeyPatch):
    instance = MockService.instance()
    checked = threading.Event()
    advanced = threading.Event()
    cleanup_thread_id: int | None = None
    lock = threading.Lock()

    class CacheLock:
        def __enter__(self) -> None:
            # Let the paused cleanup continue once its competitor either blocks
            # on this lock (fixed) or publishes a replacement (broken).
            if not lock.acquire(blocking=False):
                advanced.set()
                lock.acquire()

        def __exit__(self, *args: object) -> None:
            lock.release()

    class PausingInstances(dict[int, MockService]):
        def get(
            self, key: int, default: MockService | None = None
        ) -> MockService | None:
            cached = super().get(key, default)
            if threading.get_ident() == cleanup_thread_id and cached is instance:
                checked.set()
                assert advanced.wait(5)
            return cached

    # Pause cleanup after it reads the old instance, while another thread drains
    # that instance and requests its replacement.
    monkeypatch.setattr(
        MockService, "_instances", PausingInstances(MockService._instances)
    )
    monkeypatch.setattr(MockService, "_instance_cache_lock", CacheLock(), raising=False)

    def cleanup() -> None:
        nonlocal cleanup_thread_id
        cleanup_thread_id = threading.get_ident()
        instance._remove_instance()

    def replace() -> MockService:
        try:
            instance.drain()
            return MockService.instance()
        finally:
            advanced.set()

    with ThreadPoolExecutor(max_workers=2) as executor:
        cleanup_future = executor.submit(cleanup)
        try:
            assert checked.wait(5)
            replacement_future = executor.submit(replace)
            replacement = replacement_future.result(timeout=10)
            cleanup_future.result(timeout=10)
        finally:
            advanced.set()

    current = MockService.instance()
    try:
        assert current is replacement
        replacement.send(1)
        replacement.drain()
        replacement.mock.assert_called_once_with(replacement, 1)
    finally:
        replacement.drain()
        current.drain()


def test_instance_cache_lock_is_reset_after_fork(monkeypatch: pytest.MonkeyPatch):
    class ForkedService(MockService):
        _instance_cache_lock = threading.Lock()

    monkeypatch.setattr(ForkedService, "_instances", {})
    # A child process can inherit the cache lock while another thread holds it.
    with ForkedService._instance_cache_lock:
        ForkedService.reset_instances_for_fork()
        assert ForkedService._instance_cache_lock.acquire(blocking=False)
        ForkedService._instance_cache_lock.release()
        instance = ForkedService.instance()

    instance.send(1)
    instance.drain()
    instance.mock.assert_called_once_with(instance, 1)


def test_drain_after_reset_for_fork_does_not_error():
    instance = MockService.instance()
    instance.send(1)
    instance.drain()

    # Simulates the state of an inherited service in a forked child process
    instance.reset_for_fork()

    assert instance.drain(at_exit=True) is False


@pytest.mark.skipif(
    "fork" not in multiprocessing.get_all_start_methods(),
    reason="Requires the fork start method",
)
@pytest.mark.filterwarnings(
    # Python 3.15 warns when a multi-threaded process calls fork(); the running
    # service thread makes this process multi-threaded by design
    "ignore:This process .* is multi-threaded, use of fork:DeprecationWarning"
)
def test_forked_child_exits_cleanly_with_running_service():
    instance = MockService.instance()
    instance.send(1)

    try:
        process = multiprocessing.get_context("fork").Process(target=int)
        process.start()
        process.join(timeout=10)

        assert process.exitcode == 0
    finally:
        instance.drain()


def test_send_one():
    instance = MockService.instance()
    instance.send(1)
    MockService.drain_all()
    MockService.mock.assert_called_once_with(instance, 1)


def test_send_many():
    instance = MockService.instance()
    for i in range(10):
        instance.send(i)
    MockService.drain_all()
    MockService.mock.assert_has_calls([call(instance, i) for i in range(10)])


def test_send_many_instances():
    instances = []
    for i in range(10):
        instance = MockService.instance(i)
        instance.send(i)
        instances.append(instance)

    MockService.drain_all()
    MockService.mock.assert_has_calls(
        [call(instance, i) for instance, i in zip(instances, range(10))], any_order=True
    )


class TimedMockService(MockService):
    sleep_time = 0.01

    async def _handle(self, item: int):
        await asyncio.sleep(self.sleep_time)
        await super()._handle(item)


def test_wait_until_empty():
    instance = TimedMockService.instance()

    num_items = 5
    for i in range(num_items):
        instance.send(i)

    start_time = time.time()
    instance.wait_until_empty()
    end_time = time.time()

    expected_min_time = num_items * TimedMockService.sleep_time

    assert end_time - start_time >= expected_min_time

    TimedMockService.mock.assert_has_calls(
        [call(instance, i) for i in range(num_items)]
    )

    # Ensure the instance is properly drained
    assert instance._queue.empty()


def test_drain_safe_to_call_multiple_times():
    instances = []
    for i in range(10):
        instance = MockService.instance(i)
        instance.send(i)
        instances.append(instance)

    MockService.drain_all()
    MockService.drain_all()
    MockService.drain_all()

    MockService.mock.assert_has_calls(
        [call(instance, i) for instance, i in zip(instances, range(10))], any_order=True
    )


def test_drain_clears_asyncio_task():
    instance = MockService.instance()
    instance.send(1)

    assert instance._task is not None
    MockService.drain_all()
    assert instance._task is None


def test_send_many_threads():
    def on_thread(i):
        MockService.instance().send(i)

    with ThreadPoolExecutor() as executor:
        for i in range(10):
            executor.submit(on_thread, i)

    MockService.drain_all()
    MockService.mock.assert_has_calls([call(ANY, i) for i in range(10)], any_order=True)


def test_send_many_instances_many_threads():
    def on_thread(i):
        MockService.instance(i).send(i)

    with ThreadPoolExecutor() as executor:
        for i in range(10):
            executor.submit(on_thread, i)

    MockService.drain_all()
    MockService.mock.assert_has_calls(
        [call(ANY, i) for i in range(10)],
        any_order=True,
    )


def test_drain_many_instances_many_threads():
    def on_thread(i):
        MockService.instance(i).send(i)
        MockService.drain_all()

    with ThreadPoolExecutor() as executor:
        for i in range(10):
            executor.submit(on_thread, i)

    MockService.mock.assert_has_calls(
        [call(ANY, i) for i in range(10)],
        any_order=True,
    )


def test_drain_on_global_loop_shutdown():
    # Regression test https://github.com/PrefectHQ/prefect/issues/9275#issuecomment-1520468276
    for i in range(10):
        MockService.instance().send(i)

    wait_for_global_loop_exit()

    MockService.mock.assert_has_calls([call(ANY, i) for i in range(10)])


def test_drain_on_exit():
    with drain_on_exit(MockService):
        for i in range(10):
            MockService.instance().send(i)
    MockService.mock.assert_has_calls([call(ANY, i) for i in range(10)])


async def test_drain_on_exit_async():
    async with drain_on_exit_async(MockService):
        for i in range(10):
            MockService.instance().send(i)
    MockService.mock.assert_has_calls([call(ANY, i) for i in range(10)])


def test_drain_on_exit_async_from_same_loop():
    async def on_global_loop():
        async with drain_on_exit_async(MockService):
            for i in range(10):
                MockService.instance().send(i)

    from_sync.call_soon_in_loop_thread(create_call(on_global_loop)).result()

    MockService.mock.assert_has_calls([call(ANY, i) for i in range(10)])


def test_drain_all_timeout_sync():
    import os

    print(os.getpid())
    instance = MockService.instance()

    # Block forever on handling of this item
    event = threading.Event()
    MockService.mock.side_effect = lambda *_: event.wait()
    instance.send(1)

    t0 = time.monotonic()
    MockService.drain_all(timeout=0.01)
    t1 = time.monotonic()

    event.set()  # Unblock the handler and drain
    MockService.drain_all()

    assert t1 - t0 < 2


async def test_drain_all_timeout_async():
    # Creating an instance from an async context is not always safe when sending an
    # item that blocks the event loop like this
    instance = await from_async.call_soon_in_loop_thread(
        create_call(MockService.instance)
    ).aresult()

    event = threading.Event()
    MockService.mock.side_effect = lambda *_: event.wait()

    instance.send(1)
    t0 = time.monotonic()
    await MockService.drain_all(timeout=0.01)
    t1 = time.monotonic()

    event.set()  # Unblock the handler and drain
    await MockService.drain_all()

    assert t1 - t0 < 2


def test_lifespan():
    class LifespanService(QueueService[int]):
        events = []

        async def _handle(self, item):
            pass

        @contextlib.asynccontextmanager
        async def _lifespan(self):
            self.events.append("enter")
            try:
                yield
            finally:
                self.events.append("exit")

    LifespanService.instance().send(1)
    LifespanService.drain_all()
    assert LifespanService.events == ["enter", "exit"]


def test_lifespan_on_base_exception():
    class LifespanService(QueueService[int]):
        events = []

        async def _handle(self, item):
            raise BaseException("Oh no!")

        @contextlib.asynccontextmanager
        async def _lifespan(self):
            self.events.append("enter")
            try:
                yield
            finally:
                self.events.append("exit")

    LifespanService.instance().send(1)
    LifespanService.drain_all()
    assert LifespanService.events == ["enter", "exit"]


def test_batched_queue_service():
    instance = MockBatchedService.instance()
    instance.send(1)
    instance.send(2)
    instance.send(3)
    instance.send(4)
    instance.send(5)
    instance.drain()
    MockBatchedService.mock.assert_has_calls(
        [call(instance, [1, 2]), call(instance, [3, 4]), call(instance, [5])]
    )


def test_batched_queue_service_min_interval():
    event = threading.Event()

    class IntervalMockBatchedService(MockBatchedService):
        _min_interval = 0.01

    instance = IntervalMockBatchedService.instance()
    instance.mock.side_effect = lambda *_: event.set()
    instance.send(1)
    assert event.wait(10.0), "Item not handled within 10s"
    instance.send(2)
    IntervalMockBatchedService.drain_all()
    IntervalMockBatchedService.mock.assert_has_calls(
        [call(instance, [1]), call(instance, [2])]
    )


def test_queued_items_are_taken_without_waiting_on_queue_thread(
    backlog_service_type: type[BacklogService] | type[BatchedBacklogService],
    monkeypatch: pytest.MonkeyPatch,
):
    instance = backlog_service_type.instance()
    queue_thread_submit = MagicMock(wraps=instance._queue_get_thread.submit)
    monkeypatch.setattr(instance._queue_get_thread, "submit", queue_thread_submit)

    for i in range(1000):
        instance.send(i)
    backlog_service_type.release.set()
    instance.drain()

    assert backlog_service_type.handled == list(range(1000))
    # At most one wait for the stop signal, if it arrived after the backlog was
    # taken
    assert queue_thread_submit.call_count <= 1


def test_service_working_through_backlog_lets_other_work_run(
    backlog_service_type: type[BacklogService] | type[BatchedBacklogService],
):
    instance = backlog_service_type.instance()

    for i in range(5000):
        instance.send(i)
    backlog_service_type.release.set()
    instance.drain()

    assert backlog_service_type.handled == list(range(5000))
    # Other work on the global loop ran while most of the backlog was still queued
    assert backlog_service_type.queue_sizes_seen_by_other_work[0] > 4000


def test_on_item_dropped_called_when_queue_full():
    """When the queue is full, _on_item_dropped is called with the prepared item."""
    dropped_items: list[str] = []

    class DroppableService(QueueService[str]):
        _max_queue_size = 2

        async def _handle(self, item: str) -> None:
            pass

        def _prepare_item(self, item: str) -> str:
            return f"prepared-{item}"

        def _on_item_dropped(self, item: str) -> None:
            dropped_items.append(item)

    service = DroppableService.__new__(DroppableService)
    service.__init__()
    service._started = True
    service._stopped = False

    # Fill the queue
    service._queue.put_nowait("a")
    service._queue.put_nowait("b")
    assert service._queue.full()

    # This should trigger _on_item_dropped
    service.send("c")

    assert dropped_items == ["prepared-c"]
    assert service._queue.qsize() == 2  # Still full, item was dropped


def test_on_item_dropped_not_called_when_queue_has_space():
    """_on_item_dropped should not be called when enqueueing succeeds."""
    dropped_items: list[str] = []

    class DroppableService(QueueService[str]):
        _max_queue_size = 5

        async def _handle(self, item: str) -> None:
            pass

        def _on_item_dropped(self, item: str) -> None:
            dropped_items.append(item)

    service = DroppableService.__new__(DroppableService)
    service.__init__()
    service._started = True
    service._stopped = False

    service.send("a")
    service.send("b")

    assert dropped_items == []
    assert service._queue.qsize() == 2


def test_on_item_dropped_default_is_noop():
    """The default _on_item_dropped is a no-op and doesn't raise."""
    service = MockService.__new__(MockService)
    service.__init__()
    # Should not raise
    service._on_item_dropped(42)


@pytest.mark.parametrize(
    "level,expected", [("DEBUG", True), ("INFO", False), ("WARNING", False)]
)
def test_queue_service_item_failure_contains_traceback_only_at_debug(
    caplog: pytest.LogCaptureFixture, level: str, expected: bool
):
    class ExceptionOnHandleService(QueueService[int]):
        exception_msg = "Oh no!"

        async def _handle(self, _):
            raise Exception(self.exception_msg)

    with temporary_settings(
        {PREFECT_LOGGING_INTERNAL_LEVEL: level, PREFECT_TEST_MODE: False}
    ):
        instance = ExceptionOnHandleService.instance()
        instance.send(1)
        instance.drain()

    assert (ExceptionOnHandleService.exception_msg in caplog.text) == expected


@pytest.mark.parametrize(
    "level,expected", [("DEBUG", True), ("INFO", False), ("WARNING", False)]
)
def test_batched_queue_service_item_failure_contains_traceback_only_at_debug(
    caplog: pytest.LogCaptureFixture, level: str, expected: bool
):
    class ExceptionOnHandleBatchService(BatchedQueueService[int]):
        exception_msg = "Oh no!"
        _max_batch_size = 2

        async def _handle_batch(self, _):
            raise Exception(self.exception_msg)

    with temporary_settings(
        {PREFECT_LOGGING_INTERNAL_LEVEL: level, PREFECT_TEST_MODE: False}
    ):
        instance = ExceptionOnHandleBatchService.instance()
        instance.send(1)
        instance.drain()

    assert (ExceptionOnHandleBatchService.exception_msg in caplog.text) == expected


@pytest.mark.parametrize(
    "level,expected", [("DEBUG", True), ("INFO", False), ("WARNING", False)]
)
def test_queue_service_start_failure_contains_traceback_only_at_debug(
    caplog: pytest.LogCaptureFixture, level: str, expected: bool
):
    class ExceptionOnHandleService(QueueService[int]):
        exception_msg = "Oh no!"

        async def _handle(self): ...

        async def _main_loop(self):
            raise Exception(self.exception_msg)

    with temporary_settings(
        {PREFECT_LOGGING_INTERNAL_LEVEL: level, PREFECT_TEST_MODE: False}
    ):
        instance = ExceptionOnHandleService.instance()
        instance.drain()

    assert (ExceptionOnHandleService.exception_msg in caplog.text) == expected
