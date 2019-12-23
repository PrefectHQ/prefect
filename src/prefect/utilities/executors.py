import datetime
import multiprocessing
import signal
import sys
import threading
import time
import warnings

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from functools import wraps
from logging import Logger
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


class Heartbeat:
    """
    Class for calling a function on an interval in a background thread.

    Args:
        - interval: the interval (in seconds) on which to call the function;
            sub-second intervals are supported
        - function (callable): the function to call; this function is assumed
            to not require arguments
    """

    def __init__(self, interval: int, function: Callable, logger: Logger) -> None:
        self.interval = interval
        self.rate = min(interval, 1)
        self.function = function
        self.logger = logger
        self._exit = False

    def start(self, name_prefix: str = "") -> None:
        """
        Calling this method initiates the function calls in the background.
        """

        def looper(ctx: dict) -> None:
            iters = 0

            ## we use the self._exit attribute as a way of communicating
            ## that the loop should cease; because we want to respond to this
            ## "exit signal" quickly, we loop every `rate` seconds and check
            ## whether we should exit.  Every `interval` number of calls, we
            ## actually call the function.  The rounding logic is here to
            ## support sub-second intervals.
            with prefect.context(ctx):
                while not self._exit:
                    if round(iters % self.interval) == 0:
                        self.function()
                    iters = (iters + 1) % self.interval
                    time.sleep(self.rate)

        def monitor(ctx: dict) -> None:
            with prefect.context(ctx):
                while not self._exit:
                    if not self.fut.running():
                        self.logger.warning(
                            "Heartbeat thread appears to have died.  This could result in a zombie run."
                        )
                        return
                    time.sleep(self.rate / 2)

        kwargs = dict(max_workers=2)  # type: Dict[str, Any]
        if sys.version_info.minor != 5:
            kwargs.update(dict(thread_name_prefix=name_prefix))
        self.executor = ThreadPoolExecutor(**kwargs)
        self.fut = self.executor.submit(looper, prefect.context.to_dict())
        self.executor.submit(monitor, prefect.context.to_dict())

    def cancel(self) -> bool:
        """
        Calling this method after `start()` has been called will cleanup
        the background thread and cease calling the function.

        Returns:
            - bool: indicating whether the background thread was still
                running at time of cancellation
        """
        running = True
        if hasattr(self, "executor"):
            # there is a possible race condition wherein a FlowRunner can
            # raise a KeyboardInterrupt from its heartbeat thread the exact
            # moment after the executor is created for a TaskRunner but before
            # the future is actually submitted to the executor
            if hasattr(self, "fut"):
                running = self.fut.running()
            self._exit = True
            self.executor.shutdown()
        return running


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
        timer = Heartbeat(
            prefect.config.cloud.heartbeat_interval, self._heartbeat, self.logger
        )
        obj = getattr(self, "task", None) or getattr(self, "flow", None)
        thread_name = "PrefectHeartbeat-{}".format(getattr(obj, "name", "unknown"))
        try:
            try:
                if self._heartbeat():
                    timer.start(name_prefix=thread_name)
            except Exception as exc:
                self.logger.exception(
                    "Heartbeat failed to start.  This could result in a zombie run."
                )
            return runner_method(self, *args, **kwargs)
        finally:
            was_running = timer.cancel()
            if not was_running:
                self.logger.warning(
                    "Heartbeat thread appears to have died.  This could result in a zombie run."
                )

    return inner


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
        *args: Any, _container: multiprocessing.Queue, _ctx_dict: dict, **kwargs: Any
    ) -> None:
        """Puts the return value in a multiprocessing-safe container"""
        try:
            with prefect.context(_ctx_dict):
                val = fn(*args, **kwargs)
            _container.put(val)
        except Exception as exc:
            _container.put(exc)

    q = multiprocessing.Queue()  # type: multiprocessing.Queue
    kwargs["_container"] = q
    kwargs["_ctx_dict"] = prefect.context.to_dict()
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


def timeout_handler(
    fn: Callable, *args: Any, timeout: int = None, **kwargs: Any
) -> Any:
    """
    Helper function for implementing timeouts on function executions.

    The exact implementation varies depending on whether this function is being run
    in the main thread or a non-daemonic subprocess.  If this is run from a daemonic subprocess or on Windows,
    the task is run in a `ThreadPoolExecutor` and only a soft timeout is enforced, meaning
    a `TimeoutError` is raised at the appropriate time but the task continues running in the background.

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
    # if no timeout, just run the function
    if timeout is None:
        return fn(*args, **kwargs)

    # if we are running the main thread, use a signal to stop execution at the appropriate time;
    # else if we are running in a non-daemonic process, spawn a subprocess to kill at the appropriate time
    if not sys.platform.startswith("win"):
        if threading.current_thread() is threading.main_thread():
            return main_thread_timeout(fn, *args, timeout=timeout, **kwargs)
        elif multiprocessing.current_process().daemon is False:
            return multiprocessing_timeout(fn, *args, timeout=timeout, **kwargs)

        msg = (
            "This task is running in a daemonic subprocess; "
            "consequently Prefect can only enforce a soft timeout limit, i.e., "
            "if your Task reaches its timeout limit it will enter a TimedOut state "
            "but continue running in the background."
        )
    else:
        msg = (
            "This task is running on Windows; "
            "consequently Prefect can only enforce a soft timeout limit, i.e., "
            "if your Task reaches its timeout limit it will enter a TimedOut state "
            "but continue running in the background."
        )

    warnings.warn(msg)
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


class RecursiveCall(Exception):
    def __init__(self, func: Callable, *args: Any, **kwargs: Any):
        self.func = func
        self.args = args
        self.kwargs = kwargs


def tail_recursive(func: Callable) -> Callable:
    """
    Helper function to facilitate tail recursion of the wrapped function.

    This allows for recursion with unlimited depth since a stack is not allocated for
    each "nested" call. Note: instead of calling the target function in question, a 
    `RecursiveCall` exception must be raised instead. 

    Args:
        - fn (callable): the function to execute

    Returns:
        - the result of `f(*args, **kwargs)`

    Raises:
        - RecursionError: if a recursive "call" (raised exception) is made with a function that is 
            not decorated with `tail_recursive` decorator.
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        while True:
            try:
                return func(*args, **kwargs)
            except RecursiveCall as exc:
                try:
                    call_func = getattr(exc.func, "__wrapped_func__")
                except AttributeError:
                    raise RecursionError(
                        "function has not been wrapped to provide tail recursion (func={})".format(
                            exc.func
                        )
                    )

                # there may be multiple nested recursive calls, we should only respond to calls for the
                # wrapped function explicitly, otherwise allow the call to continue to propagate
                if call_func != func:
                    raise exc
                args = exc.args
                kwargs = exc.kwargs
                continue

    setattr(wrapper, "__wrapped_func__", func)
    return wrapper
