import datetime
import signal
import threading
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Union

import dask
import dask.bag

import prefect
from prefect.core.edge import Edge

if TYPE_CHECKING:
    import prefect.engine.runner
    import prefect.engine.state
    from prefect.engine.state import State
StateList = Union["State", List["State"]]


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
            timer.join()

    return inner


def timeout_handler(
    fn: Callable, *args: Any, timeout: int = None, **kwargs: Any
) -> Any:
    """
    Helper function for implementing timeouts on function executions.
    Implemented via `concurrent.futures.ThreadPoolExecutor`.

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
    """
    if timeout is None:
        return fn(*args, **kwargs)

    executor = ThreadPoolExecutor()

    def run_with_ctx(*args: Any, _ctx_dict: dict, **kwargs: Any) -> Any:
        with prefect.context(_ctx_dict):
            return fn(*args, **kwargs)

    fut = executor.submit(
        run_with_ctx, *args, _ctx_dict=prefect.context.to_dict(), **kwargs
    )

    try:
        return fut.result(timeout=timeout)
    except FutureTimeout:
        raise TimeoutError("Execution timed out.")
