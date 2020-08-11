import functools
import inspect
from collections import defaultdict
from typing import Any, Callable

from toolz import curry

import prefect
from prefect.utilities.logging import get_logger


__all__ = ("memoize",)


def _init_cache() -> dict:
    out = defaultdict(dict)  # type: dict
    out["generators"] = []
    return out


_CACHES = defaultdict(_init_cache)  # type: dict


def get_local_cache() -> dict:
    key = prefect.context.get("flow_run_id")
    if key is None:
        raise ValueError("No local cache in context")
    return _CACHES[key]


def clear_local_cache(flow_run_id: str) -> None:
    cache = _CACHES.pop(flow_run_id, None)
    if cache is None:
        return
    logger = get_logger()
    for generator in cache["generators"]:
        try:
            next(generator)
        except StopIteration:
            pass
        except Exception:
            logger.warn("Error while cleaning up cached function", exc_info=True)


def _default_key(*args: Any, **kwargs: Any) -> Any:
    return (args, frozenset(kwargs.items()) if kwargs else None)


@curry
def memoize(func: Callable, *, key: Callable = None) -> Callable:
    """Decorator for caching the result of a function during a flow run.

    Caches the results of a function in a temporary cache specific to a flow
    run & process. If the function is called with the same parameters during
    the same flow run in the same process, it will not be re-evaluated. Upon
    completion of the flow run, the cache will be cleared.

    Note that memoized functions should never be tasks themselves, but should
    be called as helper-functions from inside tasks. They can be useful for
    creating and reusing resources per-worker-process while avoiding treating
    these clients as the results of tasks (which must be picklable when running
    with multiple processes).

    Args:
        - func (Callable): the function to cache. May either `return` a result,
            or `yield` one. If `yield` is used, the code block after the
            `yield` statement will be run as a cleanup step upon completion of
            the flow run.  (only one `yield` statement is permitted).
        - key (Callable, optional): a function to use to generate the cache
            key. Signature should be `key(args, kwargs) -> Any`. This can be
            useful if the arguments to `func` are unhashable.

    Example:

    Here we provide an example using `memoize` to create a temporary database
    connection. If `task_1` and `task_2` run in the same process, they'll share
    the same database connection since both tasks call `db_conn` with the same
    arguments. At the end of the flow run, the database connection will be
    closed.

    ```python
    @memoize
    def db_conn(some_arg):
        with create_db_connection(some_arg) as conn:
            yield conn

    @task
    def task_1(some_arg):
        conn = db_conn(some_arg)
        conn.do_something(...)

    @task
    def task_2(some_arg)
        conn = db_conn(some_arg)
        conn.do_something_else(...)
    ```
    """
    try:
        func_id = f"{func.__qualname__}-{id(func)}"
    except Exception:
        func_id = "cached-function-{id(func)}"

    if key is None:
        key = _default_key

    @functools.wraps(func)
    def inner(*args: Any, **kwargs: Any) -> Any:
        assert key is not None  # appease mypy
        k = key(*args, **kwargs)
        cache = get_local_cache()
        try:
            return cache[func_id][k]
        except TypeError:
            raise TypeError("Argumentws to a cached function must be hashable")
        except KeyError:
            result = func(*args, **kwargs)
            if inspect.isgenerator(result):
                generator = result
                result = next(generator)
                cache["generators"].append(generator)
            cache[func_id][k] = result
            return result

    return inner
