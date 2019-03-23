import datetime
import multiprocessing
import signal
import threading
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Union

import dask
import dask.bag

import prefect
from prefect.core.edge import Edge

if TYPE_CHECKING:
    import prefect.engine.runner
    import prefect.engine.state
StateList = Union["prefect.engine.state.State", List["prefect.engine.state.State"]]


class Heartbeat(threading.Timer):
    def run(self) -> None:
        self.finished.wait(self.interval)  # type: ignore
        while not self.finished.is_set():  # type: ignore
            self.function(*self.args, **self.kwargs)  # type: ignore
            self.finished.wait(self.interval)  # type: ignore


def run_with_heartbeat(
    runner_method: Callable[..., "prefect.engine.state.State"]
) -> Callable[..., "prefect.engine.state.State"]:
    """
    Utility decorator for running class methods with a heartbeat.  The class should implement
    `self._heartbeat` with no arguments.
    """

    @wraps(runner_method)
    def inner(
        self: "prefect.engine.runner.Runner", *args: Any, **kwargs: Any
    ) -> "prefect.engine.state.State":
        try:
            timer = Heartbeat(prefect.config.cloud.heartbeat_interval, self._heartbeat)
            timer.daemon = True
            try:
                self._heartbeat()
            except:
                pass
            timer.start()
            return runner_method(self, *args, **kwargs)
        finally:
            timer.cancel()

    return inner


def multiprocessing_timeout(
    fn: Callable, *args: Any, timeout: int = None, **kwargs: Any
) -> Any:
    """
    Helper function for implementing timeouts on function executions.
    Implemented by spawning a new multiprocess.Process() and joining with timeout.

    Args:
        - fn (callable): the function to execute
        - *args (Any): arguments to pass to the function
        - timeout (int): the length of time to allow for
            execution before raising a `TimeoutError`, represented as an integer in seconds
        - **kwargs (Any): keyword arguments to pass to the function

    Returns:
        - the result of `f(*args, **kwargs)`

    Raises:
        - AssertionError: if run from a daemonic process
        - TimeoutError: if function execution exceeds the allowed timeout
    """

    if timeout is None:
        return fn(*args, **kwargs)

    def retrieve_value(
        *args: Any, _container: multiprocessing.Queue, **kwargs: Any
    ) -> None:
        """Puts the return value in a multiprocessing-safe container"""
        try:
            _container.put(fn(*args, **kwargs))
        except Exception as exc:
            _container.put(exc)

    q = multiprocessing.Queue()  # type: multiprocessing.Queue
    kwargs["_container"] = q
    p = multiprocessing.Process(target=retrieve_value, args=args, kwargs=kwargs)
    p.start()
    p.join(timeout)
    p.terminate()
    if not q.empty():
        res = q.get()
        if isinstance(res, Exception):
            raise res
        return res
    else:
        raise TimeoutError("Execution timed out.")


def main_thread_timeout(
    fn: Callable, *args: Any, timeout: int = None, **kwargs: Any
) -> Any:
    """
    Helper function for implementing timeouts on function executions.
    Implemented by setting a `signal` alarm on a timer. Must be run in the main thread.

    Args:
        - fn (callable): the function to execute
        - *args (Any): arguments to pass to the function
        - timeout (int): the length of time to allow for
            execution before raising a `TimeoutError`, represented as an integer in seconds
        - **kwargs (Any): keyword arguments to pass to the function

    Returns:
        - the result of `f(*args, **kwargs)`

    Raises:
        - TimeoutError: if function execution exceeds the allowed timeout
        - ValueError: if run from outside the main thread
    """

    if timeout is None:
        return fn(*args, **kwargs)

    def error_handler(signum, frame):  # type: ignore
        raise TimeoutError("Execution timed out.")

    try:
        signal.signal(signal.SIGALRM, error_handler)
        signal.alarm(timeout)
        return fn(*args, **kwargs)
    finally:
        signal.alarm(0)
