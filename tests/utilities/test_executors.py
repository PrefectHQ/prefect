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
    run_with_thread_timeout,
    run_with_multiprocess_timeout,
    tail_recursive,
    RecursiveCall,
)


# We will test the low-level timeout handlers here and `run_task_with_timeout_handler`
# is covered in `tests.core.test_flow.test_timeout_actually_stops_execution`
TIMEOUT_HANDLERS = [run_with_thread_timeout, run_with_multiprocess_timeout]


@pytest.mark.parametrize("timeout_handler", TIMEOUT_HANDLERS)
def test_timeout_handler_times_out(timeout_handler):
    slow_fn = lambda: time.sleep(2)
    with pytest.raises(TimeoutError):
        timeout_handler(slow_fn, timeout=2)


@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows doesn't support any timeout logic"
)
@pytest.mark.parametrize("timeout_handler", TIMEOUT_HANDLERS)
def test_timeout_handler_actually_stops_execution(timeout_handler):
    with tempfile.TemporaryDirectory() as call_dir:
        FILE = os.path.join(call_dir, "test.txt")
        # Increase timeout for multiprocess because its startup time is slower and
        # the file was not always created
        TIMEOUT = 1 if timeout_handler is run_with_thread_timeout else 3
        WRITES = 6

        def slow_fn():
            "Runs for TIMEOUT * 2 seconds, writes to file WRITES times"
            for _ in range(WRITES):
                with open(FILE, "a") as f:
                    f.write("called\n")
                time.sleep((TIMEOUT * 2) / WRITES)

        with pytest.raises(TimeoutError):
            # We should get less than WRITES lines -- roughly half expected
            timeout_handler(slow_fn, timeout=TIMEOUT)

        time.sleep(0.5)
        with open(FILE, "r") as g:
            contents = g.read()

    assert len(contents.split("\n")) < WRITES


@pytest.mark.parametrize("timeout_handler", TIMEOUT_HANDLERS)
def test_timeout_handler_passes_args_and_kwargs_and_returns(timeout_handler):
    def just_return(x, y=None):
        return x, y

    assert timeout_handler(
        just_return, args=[5], kwargs=dict(y="yellow"), timeout=2
    ) == (
        5,
        "yellow",
    )


@pytest.mark.parametrize("timeout_handler", TIMEOUT_HANDLERS)
def test_timeout_handler_doesnt_swallow_bad_args(timeout_handler):
    def do_nothing(x, y=None):
        return x, y

    with pytest.raises(TypeError):
        timeout_handler(do_nothing, timeout=2)

    with pytest.raises(TypeError):
        timeout_handler(do_nothing, args=[5], kwargs=dict(z=10), timeout=2)

    with pytest.raises(TypeError):
        timeout_handler(do_nothing, args=[5], kwargs=dict(y="s", z=10), timeout=2)


@pytest.mark.parametrize("timeout_handler", TIMEOUT_HANDLERS)
def test_timeout_handler_reraises(timeout_handler):
    def do_something():
        raise ValueError("test")

    with pytest.raises(ValueError, match="test"):
        timeout_handler(do_something, timeout=2)


# Define a top-level helper function for a null-op process target, must be defined
# as a non-local for the python native pickler used within `my_process`
def do_nothing():
    return None


@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows doesn't support any timeout logic"
)
@pytest.mark.parametrize("timeout_handler", TIMEOUT_HANDLERS)
def test_timeout_handler_allows_function_to_spawn_new_process(timeout_handler):
    def my_process():
        p = multiprocessing.Process(target=do_nothing())
        p.start()
        p.join()
        p.terminate()

    assert timeout_handler(my_process, timeout=2) is None


@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows doesn't support any timeout logic"
)
@pytest.mark.parametrize("timeout_handler", TIMEOUT_HANDLERS)
def test_timeout_handler_allows_function_to_spawn_new_thread(timeout_handler):
    def my_thread():
        t = threading.Thread(target=lambda: 5)
        t.start()
        t.join()

    assert timeout_handler(my_thread, timeout=2) is None


@pytest.mark.parametrize("timeout_handler", TIMEOUT_HANDLERS)
def test_timeout_handler_doesnt_do_anything_if_no_timeout(timeout_handler):
    assert timeout_handler(lambda: 4, timeout=2) == 4
    assert timeout_handler(lambda: 4) == 4


@pytest.mark.parametrize("timeout_handler", TIMEOUT_HANDLERS)
def test_timeout_handler_preserves_context(timeout_handler):
    def my_fun(x, **kwargs):
        return prefect.context.get("test_key")

    with prefect.context(test_key=42):
        res = timeout_handler(my_fun, args=[2], timeout=2)

    assert res == 42


def test_run_with_thread_timeout_preserves_logging(caplog):
    run_with_thread_timeout(prefect.Flow("logs").run, timeout=2)
    assert len(caplog.messages) >= 2  # 1 INFO to start, 1 INFO to end


def test_run_with_multiprocess_timeout_preserves_logging(capfd):
    """
    Requires fd capturing because the subprocess output won't be captured by caplog
    """
    run_with_multiprocess_timeout(prefect.Flow("logs").run, timeout=2)
    stdout = capfd.readouterr().out
    assert "Beginning Flow run" in stdout
    assert "Flow run SUCCESS" in stdout


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
