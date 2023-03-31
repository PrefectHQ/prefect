from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from unittest.mock import ANY, MagicMock, call

import pytest

from prefect._internal.concurrency.api import create_call, from_sync
from prefect._internal.concurrency.services import (
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


@pytest.fixture(autouse=True)
def reset_mock_service():
    MockService.mock.reset_mock()


def test_get_instance_returns_instance():
    instance = MockService.instance()
    assert isinstance(instance, MockService)


def test_get_instance_returns_same_instance():
    instance = MockService.instance()
    assert MockService.instance() is instance


def test_get_instance_returns_new_instance_after_stopping():
    instance = MockService.instance()
    instance._stop()
    new_instance = MockService.instance()
    assert new_instance is not instance
    assert isinstance(new_instance, MockService)


def test_get_instance_returns_new_instance_with_unique_key():
    instance = MockService.instance(1)
    new_instance = MockService.instance(2)
    assert new_instance is not instance
    assert isinstance(new_instance, MockService)


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
