import multiprocessing
import pytest
import time
from datetime import timedelta

from prefect.utilities.executors import multiprocessing_timeout, main_thread_timeout


@pytest.mark.parametrize("handler", [multiprocessing_timeout, main_thread_timeout])
def test_timeout_handler_times_out(handler):
    slow_fn = lambda: time.sleep(2)
    with pytest.raises(TimeoutError):
        handler(slow_fn, timeout=timedelta(seconds=1))


@pytest.mark.parametrize("handler", [multiprocessing_timeout, main_thread_timeout])
def test_timeout_handler_passes_args_and_kwargs_and_returns(handler):
    def do_nothing(x, y=None):
        return x, y

    assert handler(do_nothing, 5, timeout=timedelta(seconds=1), y="yellow") == (
        5,
        "yellow",
    )


@pytest.mark.parametrize("handler", [multiprocessing_timeout, main_thread_timeout])
def test_timeout_handler_doesnt_swallow_bad_args(handler):
    def do_nothing(x, y=None):
        return x, y

    with pytest.raises(TypeError):
        handler(do_nothing, timeout=timedelta(seconds=1))

    with pytest.raises(TypeError):
        handler(do_nothing, 5, timeout=timedelta(seconds=1), z=10)

    with pytest.raises(TypeError):
        handler(do_nothing, 5, timeout=timedelta(seconds=1), y="s", z=10)


@pytest.mark.parametrize("handler", [multiprocessing_timeout, main_thread_timeout])
def test_timeout_handler_reraises(handler):
    def do_something():
        raise ValueError("test")

    with pytest.raises(ValueError) as exc:
        handler(do_something, timeout=timedelta(seconds=1))
        assert "test" in exc


@pytest.mark.parametrize("handler", [multiprocessing_timeout, main_thread_timeout])
def test_timeout_handler_allows_function_to_spawn_new_process(handler):
    def my_process():
        p = multiprocessing.Process(target=lambda: 5)
        p.start()
        p.join()
        p.terminate()

    assert handler(my_process, timeout=timedelta(seconds=1)) is None
