import multiprocessing
import threading
import time
from datetime import timedelta
from unittest.mock import MagicMock

import pytest

import prefect
from prefect.utilities.executors import Heartbeat, timeout_handler


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
    timer.join()
    assert a.called == 2


def test_timeout_handler_times_out():
    slow_fn = lambda: time.sleep(2)
    with pytest.raises(TimeoutError):
        timeout_handler(slow_fn, timeout=1)


def test_timeout_handler_passes_args_and_kwargs_and_returns():
    def do_nothing(x, y=None):
        return x, y

    assert timeout_handler(do_nothing, 5, timeout=1, y="yellow") == (5, "yellow")


def test_timeout_handler_doesnt_swallow_bad_args():
    def do_nothing(x, y=None):
        return x, y

    with pytest.raises(TypeError):
        timeout_handler(do_nothing, timeout=1)

    with pytest.raises(TypeError):
        timeout_handler(do_nothing, 5, timeout=1, z=10)

    with pytest.raises(TypeError):
        timeout_handler(do_nothing, 5, timeout=1, y="s", z=10)


def test_timeout_handler_reraises():
    def do_something():
        raise ValueError("test")

    with pytest.raises(ValueError, match="test"):
        timeout_handler(do_something, timeout=1)


def test_timeout_handler_allows_function_to_spawn_new_process():
    def my_process():
        p = multiprocessing.Process(target=lambda: 5)
        p.start()
        p.join()
        p.terminate()

    assert timeout_handler(my_process, timeout=1) is None


def test_timeout_handler_allows_function_to_spawn_new_thread():
    def my_thread():
        t = threading.Thread(target=lambda: 5)
        t.start()
        t.join()

    assert timeout_handler(my_thread, timeout=1) is None


def test_timeout_handler_doesnt_do_anything_if_no_timeout(monkeypatch):
    monkeypatch.delattr(prefect.utilities.executors, "ThreadPoolExecutor")
    with pytest.raises(NameError):  # to test the test's usefulness...
        timeout_handler(lambda: 4, timeout=1)
    assert timeout_handler(lambda: 4) == 4


def test_timeout_handler_preserves_context():
    def my_fun(x, **kwargs):
        return prefect.context.get("test_key")

    with prefect.context(test_key=42):
        res = timeout_handler(my_fun, 2, timeout=1)

    assert res == 42


def test_timeout_handler_preserves_logging(caplog):
    timeout_handler(prefect.Flow("logs").run, timeout=2)
    assert len(caplog.records) >= 2  # 1 INFO to start, 1 INFO to end
