import contextlib
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional
from unittest.mock import ANY, MagicMock, call

import pytest

from prefect._internal.concurrency.api import create_call, from_sync
from prefect._internal.concurrency.services import (
    BatchedQueueService,
    QueueService,
    drain_on_exit,
    drain_on_exit_async,
)


class MockService(QueueService[int]):
    mock = MagicMock()

    def __init__(self, index: Optional[int] = None) -> None:
        if index is not None:
            super().__init__(index)
        else:
            super().__init__()

    async def _handle(self, item: int):
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
        self.mock(self, items)
        print(f"Handled batch for {self}")


@pytest.fixture(autouse=True)
def reset_mock_services():
    yield
    MockService.mock.reset_mock(side_effect=True)
    MockBatchedService.mock.reset_mock(side_effect=True)
    MockService.drain_all()
    MockBatchedService.drain_all()


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
        [call(instance, i) for instance, i in zip(instances, range(10))]
    )


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
        [call(instance, i) for instance, i in zip(instances, range(10))]
    )


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
