# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import dask
import dask.bag
import datetime
import multiprocessing
import signal
from typing import Any, Callable, Dict, List, Union

import prefect
from prefect.core.edge import Edge


StateList = Union["prefect.engine.state.State", List["prefect.engine.state.State"]]


def multiprocessing_timeout(
    fn: Callable, *args: Any, timeout: datetime.timedelta = None, **kwargs: Any
):
    """
    Decorator for implementing timeouts on function executions.
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
        - TimeoutError: if function execution exceeds the allowed timeout
    """

    if timeout is None:
        return fn(*args, **kwargs)
    else:
        timeout = timeout.total_seconds()

    def retrieve_value(*args, _container, **kwargs):
        """Puts the return value in a multiprocessing-safe container"""
        try:
            _container.put(fn(*args, **kwargs))
        except Exception as exc:
            _container.put(exc)

    q = multiprocessing.Queue()
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
    fn: Callable, *args: Any, timeout: datetime.timedelta = None, **kwargs: Any
):
    """
    Decorator for implementing timeouts on function executions.
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
    """

    if timeout is None:
        return fn(*args, **kwargs)
    else:
        timeout = round(timeout.total_seconds())

    def error_handler(signum, frame):
        raise TimeoutError("Execution timed out.")

    try:
        signal.signal(signal.SIGALRM, error_handler)
        signal.alarm(timeout)
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
    return [type(s)(result=elem) for elem in s.result]


def unpack_dict_to_bag(*values: Any, keys: List[str]) -> dict:
    "Convenience function for packaging up all keywords into a dictionary"
    return {k: v for k, v in zip(keys, values)}
