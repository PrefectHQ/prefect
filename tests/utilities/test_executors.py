import multiprocessing
import time
from datetime import timedelta
from unittest.mock import MagicMock

import pytest

import prefect
from prefect.utilities.executors import (
    Heartbeat,
    main_thread_timeout,
    multiprocessing_timeout,
)


def test_heartbeat_calls_function_on_interval():
    class A:
        def __init__(self):
            self.called = 0

        def __call__(self):
            self.called += 1

    a = A()
    timer = Heartbeat(0.09, a)
    timer.start()
    time.sleep(0.2)
    timer.cancel()
    assert a.called == 2


@pytest.mark.parametrize("handler", [multiprocessing_timeout, main_thread_timeout])
def test_timeout_handler_times_out(handler):
    slow_fn = lambda: time.sleep(2)
    with pytest.raises(TimeoutError):
        handler(slow_fn, timeout=1)


@pytest.mark.parametrize("handler", [multiprocessing_timeout, main_thread_timeout])
def test_timeout_handler_passes_args_and_kwargs_and_returns(handler):
    def do_nothing(x, y=None):
        return x, y

    assert handler(do_nothing, 5, timeout=1, y="yellow") == (5, "yellow")


@pytest.mark.parametrize("handler", [multiprocessing_timeout, main_thread_timeout])
def test_timeout_handler_doesnt_swallow_bad_args(handler):
    def do_nothing(x, y=None):
        return x, y

    with pytest.raises(TypeError):
        handler(do_nothing, timeout=1)

    with pytest.raises(TypeError):
        handler(do_nothing, 5, timeout=1, z=10)

    with pytest.raises(TypeError):
        handler(do_nothing, 5, timeout=1, y="s", z=10)


@pytest.mark.parametrize("handler", [multiprocessing_timeout, main_thread_timeout])
def test_timeout_handler_reraises(handler):
    def do_something():
        raise ValueError("test")

    with pytest.raises(ValueError) as exc:
        handler(do_something, timeout=1)
        assert "test" in exc


@pytest.mark.parametrize("handler", [multiprocessing_timeout, main_thread_timeout])
def test_timeout_handler_allows_function_to_spawn_new_process(handler):
    def my_process():
        p = multiprocessing.Process(target=lambda: 5)
        p.start()
        p.join()
        p.terminate()

    assert handler(my_process, timeout=1) is None


def test_main_thread_timeout_doesnt_do_anything_if_no_timeout(monkeypatch):
    monkeypatch.delattr(prefect.utilities.executors.signal, "signal")
    with pytest.raises(AttributeError):  # to test the test's usefulness...
        main_thread_timeout(lambda: 4, timeout=1)
    assert main_thread_timeout(lambda: 4) == 4


def test_multiprocessing_timeout_doesnt_do_anything_if_no_timeout(monkeypatch):
    monkeypatch.delattr(prefect.utilities.executors.multiprocessing, "Process")
    with pytest.raises(AttributeError):  # to test the test's usefulness...
        multiprocessing_timeout(lambda: 4, timeout=1)
    assert multiprocessing_timeout(lambda: 4) == 4
