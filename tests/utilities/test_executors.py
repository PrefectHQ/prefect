import os
import multiprocessing
import sys
import threading
import tempfile
import time

import pytest

import prefect
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.executors import (
    timeout_handler,
    tail_recursive,
    RecursiveCall,
)


def test_timeout_handler_times_out():
    slow_fn = lambda: time.sleep(2)
    with pytest.raises(TimeoutError):
        timeout_handler(slow_fn, timeout=1)


@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows doesn't support any timeout logic"
)
def test_timeout_handler_actually_stops_execution():
    with tempfile.TemporaryDirectory() as call_dir:
        FILE = os.path.join(call_dir, "test.txt")

        def slow_fn():
            "Runs for 1.5 seconds, writes to file 6 times"
            iters = 0
            while iters < 6:
                time.sleep(0.26)
                with open(FILE, "a") as f:
                    f.write("called\n")
                iters += 1

        with pytest.raises(TimeoutError):
            # allow for at most 3 writes
            timeout_handler(slow_fn, timeout=1)

        time.sleep(0.5)
        with open(FILE, "r") as g:
            contents = g.read()

    assert len(contents.split("\n")) <= 4


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


@pytest.mark.skipif(sys.platform == "win32", reason="Test fails on Windows")
def test_timeout_handler_allows_function_to_spawn_new_process():
    def my_process():
        p = multiprocessing.Process(target=lambda: 5)
        p.start()
        p.join()
        p.terminate()

    assert timeout_handler(my_process, timeout=1) is None


@pytest.mark.skipif(sys.platform == "win32", reason="Test fails on Windows")
def test_timeout_handler_allows_function_to_spawn_new_thread():
    def my_thread():
        t = threading.Thread(target=lambda: 5)
        t.start()
        t.join()

    assert timeout_handler(my_thread, timeout=1) is None


def test_timeout_handler_doesnt_do_anything_if_no_timeout(monkeypatch):
    assert timeout_handler(lambda: 4, timeout=1) == 4
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


def test_recursion_go_case():
    @tail_recursive
    def my_func(a=0):
        if a > 5:
            return a
        raise RecursiveCall(my_func, a + 2)

    assert 6 == my_func()


def test_recursion_beyond_python_limits():
    RECURSION_LIMIT = sys.getrecursionlimit()

    @tail_recursive
    def my_func(calls=0):
        if calls > RECURSION_LIMIT + 10:
            return calls
        raise RecursiveCall(my_func, calls + 1)

    assert my_func() == RECURSION_LIMIT + 11


def test_recursion_nested():
    def utility_func(a):
        if a > 5:
            return a
        raise RecursiveCall(my_func, a + 2)

    @tail_recursive
    def my_func(a=0):
        return utility_func(a)

    assert 6 == my_func()


def test_recursion_multiple():
    call_checkpoints = []

    @tail_recursive
    def a_func(a=0):
        call_checkpoints.append(("a", a))
        if a > 5:
            return a
        a = b_func(a + 1)
        raise RecursiveCall(a_func, (a + 1) * 2)

    @tail_recursive
    def b_func(b=0):
        call_checkpoints.append(("b", b))
        if b > 5:
            return b
        b = a_func(b + 2)
        raise RecursiveCall(b_func, b + 2)

    assert a_func() == 42  # :)
    assert call_checkpoints == [
        ("a", 0),
        ("b", 1),
        ("a", 3),
        ("b", 4),
        ("a", 6),
        ("b", 8),
        ("a", 18),
        ("b", 20),
        ("a", 42),
    ]


def test_recursion_raises_when_not_decorated():
    call_checkpoints = []

    @tail_recursive
    def a_func(a=0):
        call_checkpoints.append(("a", a))
        if a > 5:
            return a
        a = b_func(a + 1)
        raise RecursiveCall(a_func, (a + 1) * 2)

    def b_func(b=0):
        call_checkpoints.append(("b", b))
        if b > 5:
            return b
        b = a_func(b + 2)
        raise RecursiveCall(b_func, b + 2)

    with pytest.raises(RecursionError):
        assert a_func()

    assert call_checkpoints == [("a", 0), ("b", 1), ("a", 3), ("b", 4), ("a", 6)]
