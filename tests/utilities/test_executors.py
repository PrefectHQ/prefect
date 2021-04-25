import os
import multiprocessing
import sys
import threading
import time
from unittest.mock import MagicMock

import cloudpickle
import pytest

import prefect
from prefect.utilities.exceptions import TaskTimeoutError
from prefect.utilities.executors import (
    run_with_thread_timeout,
    run_with_multiprocess_timeout,
    multiprocessing_safe_run_and_retrieve,
    tail_recursive,
    RecursiveCall,
)


# We will test the low-level timeout handlers here and `run_task_with_timeout`
# is covered in `tests.core.test_flow.test_timeout_actually_stops_execution`
# and `tests.engine.test_task_runner.test_timeout_actually_stops_execution`
TIMEOUT_HANDLERS = [run_with_thread_timeout, run_with_multiprocess_timeout]


@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows doesn't support any timeout logic"
)
@pytest.mark.parametrize("timeout_handler", TIMEOUT_HANDLERS)
def test_timeout_handler_times_out(timeout_handler):
    slow_fn = lambda: time.sleep(2)
    with pytest.raises(TaskTimeoutError):
        timeout_handler(slow_fn, timeout=1)


@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows doesn't support any timeout logic"
)
@pytest.mark.parametrize("timeout_handler", TIMEOUT_HANDLERS)
def test_timeout_handler_actually_stops_execution(timeout_handler, tmpdir):
    start_path = str(tmpdir.join("started.txt"))
    finish_path = str(tmpdir.join("finished.txt"))

    if timeout_handler == run_with_thread_timeout:
        timeout = 1
        wait_time = 1.5
        max_overhead = 0.1
    else:
        timeout = 2.5
        wait_time = 3
        max_overhead = 2

    def slow_fn(start_path, finish_path, wait_time):
        with open(start_path, "wb"):
            pass
        time.sleep(wait_time)
        with open(start_path, "wb"):
            pass

    start_time = time.time()
    stop_time = start_time + wait_time + max_overhead
    with pytest.raises(TaskTimeoutError):
        timeout_handler(
            slow_fn, args=(start_path, finish_path, wait_time), timeout=timeout
        )

    # Wait untl after we're sure the task would have finished naturally
    time.sleep(stop_time - time.time())

    assert os.path.exists(start_path)
    assert not os.path.exists(finish_path)


@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows doesn't support any timeout logic"
)
@pytest.mark.parametrize("timeout_handler", TIMEOUT_HANDLERS)
def test_timeout_handler_passes_args_and_kwargs_and_returns(timeout_handler):
    def just_return(x, y=None):
        return x, y

    assert timeout_handler(
        just_return, args=[5], kwargs=dict(y="yellow"), timeout=10
    ) == (
        5,
        "yellow",
    )


@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows doesn't support any timeout logic"
)
@pytest.mark.parametrize("timeout_handler", TIMEOUT_HANDLERS)
def test_timeout_handler_doesnt_swallow_bad_args(timeout_handler):
    def do_nothing(x, y=None):
        return x, y

    with pytest.raises(TypeError):
        timeout_handler(do_nothing, timeout=10)

    with pytest.raises(TypeError):
        timeout_handler(do_nothing, args=[5], kwargs=dict(z=10), timeout=10)

    with pytest.raises(TypeError):
        timeout_handler(do_nothing, args=[5], kwargs=dict(y="s", z=10), timeout=10)


@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows doesn't support any timeout logic"
)
@pytest.mark.parametrize("timeout_handler", TIMEOUT_HANDLERS)
def test_timeout_handler_reraises(timeout_handler):
    def do_something():
        raise ValueError("test")

    with pytest.raises(ValueError, match="test"):
        timeout_handler(do_something, timeout=10)


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
        return "hello"

    assert timeout_handler(my_process, timeout=10) == "hello"


@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows doesn't support any timeout logic"
)
@pytest.mark.parametrize("timeout_handler", TIMEOUT_HANDLERS)
def test_timeout_handler_allows_function_to_spawn_new_thread(timeout_handler):
    def my_thread():
        t = threading.Thread(target=lambda: 5)
        t.start()
        t.join()
        return "hello"

    assert timeout_handler(my_thread, timeout=10) == "hello"


@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows doesn't support any timeout logic"
)
@pytest.mark.parametrize("timeout_handler", TIMEOUT_HANDLERS)
def test_timeout_handler_doesnt_do_anything_if_no_timeout(timeout_handler):
    assert timeout_handler(lambda: 4) == 4


@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows doesn't support any timeout logic"
)
@pytest.mark.parametrize("timeout_handler", TIMEOUT_HANDLERS)
def test_timeout_handler_preserves_context(timeout_handler):
    def my_fun(x, **kwargs):
        return prefect.context.get("test_key")

    with prefect.context(test_key=42):
        res = timeout_handler(my_fun, args=[2], timeout=10)

    assert res == 42


@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows doesn't support any timeout logic"
)
def test_run_with_thread_timeout_preserves_logging(caplog):
    run_with_thread_timeout(prefect.Flow("logs").run, timeout=10)
    assert len(caplog.messages) >= 2  # 1 INFO to start, 1 INFO to end


@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows doesn't support any timeout logic"
)
def test_run_with_multiprocess_timeout_preserves_logging(capfd):
    """
    Requires fd capturing because the subprocess output won't be captured by caplog
    """
    run_with_multiprocess_timeout(prefect.Flow("logs").run, timeout=10)
    stdout = capfd.readouterr().out
    assert "Beginning Flow run" in stdout
    assert "Flow run SUCCESS" in stdout


@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows doesn't support any timeout logic"
)
def test_run_with_multiprocess_timeout_handles_none_return_values():
    def fn():
        return None

    result = run_with_multiprocess_timeout(fn, timeout=10)

    assert result is None


@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows doesn't support any timeout logic"
)
def test_run_with_multiprocess_timeout_handles_unpicklable_return_values():
    def fn():
        import threading

        # An unpickleable type
        return threading.Lock()

    with pytest.raises(
        RuntimeError,
        match="Failed to pickle result of type 'lock'",
    ) as exc_info:
        run_with_multiprocess_timeout(fn, timeout=12)

    # We include the original exception
    assert "TypeError: cannot pickle '_thread.lock' object" in str(
        exc_info.value
        # Python 3.6/7 have a different error message
    ) or "TypeError: can't pickle _thread.lock objects" in str(exc_info.value)


@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows doesn't support any timeout logic"
)
def test_multiprocessing_safe_run_and_retrieve_logs_queue_errors(caplog):
    # We cannot mock queue.put
    def fn():
        pass

    mock_queue = MagicMock(put=MagicMock(side_effect=Exception("Test")))

    request = cloudpickle.dumps({"fn": fn})

    with pytest.raises(
        Exception,
        match="Test",
    ):
        multiprocessing_safe_run_and_retrieve(mock_queue, request)

    assert "Failed to put result in queue to main process!" in caplog.text
    assert "Exception: Test" in caplog.text


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
