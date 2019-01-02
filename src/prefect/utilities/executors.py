# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import dask
import dask.bag
import datetime
import multiprocessing
import signal
import threading
from functools import wraps
from typing import Any, Callable, Dict, List, Union

import prefect
from prefect.core.edge import Edge


StateList = Union["prefect.engine.state.State", List["prefect.engine.state.State"]]


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
            timer = threading.Timer(
                prefect.config.cloud.heartbeat_interval, self._heartbeat
            )
            try:
                self._heartbeat()
            except:
                pass
            timer.start()
            return runner_method(self, *args, **kwargs)
        except Exception as exc:
            raise exc
        finally:
            timer.cancel()

    return inner


def multiprocessing_timeout(
    fn: Callable, *args: Any, timeout: datetime.timedelta = None, **kwargs: Any
) -> Any:
    """
    Helper function for implementing timeouts on function executions.
    Implemented by spawning a new multiprocess.Process() and joining with timeout.

    Args:
        - fn (callable): the function to execute
        - *args (Any): arguments to pass to the function
        - timeout (datetime.timedelta): the length of time to allow for
            execution before raising a `TimeoutError`
        - **kwargs (Any): keyword arguments to pass to the function

    Returns:
        - the result of `f(*args, **kwargs)`

    Raises:
        - AssertionError: if run from a daemonic process
        - TimeoutError: if function execution exceeds the allowed timeout
    """

    if timeout is None:
        return fn(*args, **kwargs)
    else:
        timeout_length = timeout.total_seconds()

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
    p.join(timeout_length)
    p.terminate()
    if not q.empty():
        res = q.get()
        if isinstance(res, Exception):
            raise res
        return res
    else:
        raise TimeoutError("Execution timed out.")


def main_thread_timeout(
    fn: Callable, *args: Any, timeout: datetime.timedelta = None, **kwargs: Any
) -> Any:
    """
    Helper function for implementing timeouts on function executions.
    Implemented by setting a `signal` alarm on a timer. Must be run in the main thread.

    Args:
        - fn (callable): the function to execute
        - *args (Any): arguments to pass to the function
        - timeout (datetime.timedelta): the length of time to allow for
            execution before raising a `TimeoutError`
        - **kwargs (Any): keyword arguments to pass to the function

    Returns:
        - the result of `f(*args, **kwargs)`

    Raises:
        - TimeoutError: if function execution exceeds the allowed timeout
        - ValueError: if run from outside the main thread
    """

    if timeout is None:
        return fn(*args, **kwargs)
    else:
        timeout_length = round(timeout.total_seconds())

    def error_handler(signum, frame):  # type: ignore
        raise TimeoutError("Execution timed out.")

    try:
        signal.signal(signal.SIGALRM, error_handler)
        signal.alarm(timeout_length)
        return fn(*args, **kwargs)
    finally:
        signal.alarm(0)


def dict_to_list(dd: Dict[Edge, StateList]) -> List[dict]:
    """
    Given a dictionary of {Edge: States (or lists of States)} which need to be
    iterated over, effectively converts any states which return a list to a list of individual states and
    zips the values together to return a list of dictionaries, with each key now associated to a single element.
    """
    mapped = {e: state_to_list(s) for e, s in dd.items() if e.mapped}
    unmapped = {e: s for e, s in dd.items() if not e.mapped}
    m_list = [dict(zip(mapped, vals)) for vals in zip(*mapped.values())]
    for d in m_list:
        d.update(unmapped)
    return m_list


def state_to_list(s: StateList) -> List["prefect.engine.state.State"]:
    """
    Converts a State `s` with an iterator as its result to a list of states of the same type.

    Example:
        ```python
        s = State(result=[1, 2, 3])
        state_to_list(s) # [State(result=1), State(result=2), State(result=3)]
    """
    if isinstance(s, list):
        return s
    assert s.result is not None, "State's result must be iterable"
    return [type(s)(result=elem) for elem in s.result]
