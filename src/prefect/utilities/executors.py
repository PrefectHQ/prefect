import multiprocessing
import os
import signal
import subprocess
import sys
import threading
import warnings
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, List, Union

import prefect

if TYPE_CHECKING:
    import prefect.engine.runner
    import prefect.engine.state
    from prefect.engine.state import State  # pylint: disable=W0611

StateList = Union["State", List["State"]]


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
            p = None
            try:
                if self._heartbeat():
                    # we use Popen + a prefect CLI for a few reasons:
                    # - using threads would interfere with the task; for example, a task
                    #   which does not release the GIL would prevent the heartbeat thread from
                    #   firing
                    # - using multiprocessing.Process would release the GIL but a subprocess
                    #   cannot be spawned from a deamonic subprocess, and Dask sometimes will
                    #   submit tasks to run within daemonic subprocesses
                    current_env = dict(os.environ).copy()
                    auth_token = prefect.context.config.cloud.get("auth_token")
                    api_url = prefect.context.config.cloud.get("api")
                    current_env.setdefault("PREFECT__CLOUD__AUTH_TOKEN", auth_token)
                    current_env.setdefault("PREFECT__CLOUD__API", api_url)
                    p = subprocess.Popen(
                        self.heartbeat_cmd,
                        env=current_env,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
            except Exception as exc:
                self.logger.exception(
                    "Heartbeat failed to start.  This could result in a zombie run."
                )
            return runner_method(self, *args, **kwargs)
        finally:
            if p is not None:
                exit_code = p.poll()
                if exit_code is not None:
                    out, err = p.communicate()
                    msg = "Heartbeat process died with exit code {}".format(exit_code)
                    msg += "\nSTDOUT: {}".format(out.decode() if out else None)
                    msg += "\nSTDERR: {}".format(err.decode() if err else None)
                    self.logger.error(msg)
                p.kill()

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
