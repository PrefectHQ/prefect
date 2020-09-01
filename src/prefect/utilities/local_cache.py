import atexit
import functools
import inspect
import threading
import weakref
import uuid
from collections import defaultdict
from typing import Any, Callable

from toolz import curry

import prefect
from prefect.utilities.logging import get_logger


__all__ = ("shared_object",)


class _SerializableLock(object):
    _locks = weakref.WeakValueDictionary()  # type: weakref.WeakValueDictionary
    """A Serializable per-process Lock.

    This wraps a normal ``threading.Lock`` or ``threading.RLock`` object and
    satisfies the same interface.  However, this lock can also be serialized
    and sent to different processes. It will not block concurrent operations
    between processes but will consistently deserialize into the same lock.

    This is useful for consistently protecting resources on a per-process
    level.
    """

    def __init__(self, reentrant: bool = False, token: str = None):
        self.reentrant = reentrant
        self.token = token or str(uuid.uuid4())
        if self.token in _SerializableLock._locks:
            self.lock = _SerializableLock._locks[self.token]
        else:
            self.lock = threading.RLock() if reentrant else threading.Lock()
            _SerializableLock._locks[self.token] = self.lock

    def acquire(self, *args: Any, **kwargs: Any) -> bool:
        return self.lock.acquire(*args, **kwargs)

    def release(self, *args: Any, **kwargs: Any) -> None:
        self.lock.release(*args, **kwargs)

    def __enter__(self) -> None:
        self.lock.__enter__()

    def __exit__(self, *args: Any) -> None:
        self.lock.__exit__(*args)

    def __reduce__(self) -> tuple:
        return _SerializableLock, (self.reentrant, self.token)

    def __repr__(self) -> str:
        return "<%s: %s>" % (self.__class__.__name__, self.token)


@atexit.register
def clear_all_local_caches() -> None:
    """On process exit, ensure all local caches are cleared.

    For most executors, this should be a no-op (the cleanup should have already run).
    """
    for flow_run_id in list(_CACHES):
        clear_local_cache(flow_run_id)


def _init_cache() -> dict:
    out = defaultdict(dict)  # type: dict
    out["generators"] = []
    return out


_CACHES = defaultdict(_init_cache)  # type: dict


def get_local_cache() -> dict:
    # If not running inside a flow run, use a global cache This shouldn't
    # happen in normal flow usage, but allows shared_object functions to be
    # called from outside a flow run (for e.g. testing)
    key = prefect.context.get("flow_run_id", "GLOBAL")
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
            logger.warning(
                "Error while cleaning up `shared_object` function", exc_info=True
            )


def _default_key(*args: Any, **kwargs: Any) -> Any:
    return (args, frozenset(kwargs.items()) if kwargs else None)


@curry
def shared_object(func: Callable, *, key: Callable = None) -> Callable:
    """Marks the result of this helper function as a shared object to be reused
    by other tasks.

    Functions decorated with ``shared_object`` have their results stored in a
    temporary cache specific to a flow run & process. If the function is called
    with the same parameters during the same flow run in the same process, it
    will not be re-evaluated. Upon completion of the flow run, the cache will
    be cleared.

    Note that ``shared_object`` functions should never be tasks themselves, but
    should be called as helper-functions from inside tasks. They can be useful
    for creating and reusing resources per-worker-process while avoiding
    treating these clients as the results of tasks (which must be picklable
    when running with multiple processes).

    Args:
        - func (Callable): the function to cache. May either `return` a result,
            or `yield` one. If `yield` is used, the code block after the
            `yield` statement will be run as a cleanup step upon completion of
            the flow run (only one `yield` statement is permitted).
        - key (Callable, optional): a function to use to generate the cache
            key. Signature should be `key(*args, **kwargs) -> Any`. This can be
            useful if the arguments to `func` aren't unhashable.

    Example:

    Here we provide an example using `shared_object` to create a temporary
    database connection. If `task_1` and `task_2` run in the same process,
    they'll share the same database connection since both tasks call `db_conn`
    with the same arguments. At the end of the flow run, the database
    connection will be closed.

    ```python
    @shared_object
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
        func_id = "shared-object-function-{id(func)}"

    if key is None:
        key = _default_key

    sig = inspect.signature(func)

    lock = _SerializableLock()

    @functools.wraps(func)
    def inner(*args: Any, **kwargs: Any) -> Any:
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        assert key is not None  # appease mypy
        k = key(*bound.args, **bound.kwargs)
        cache = get_local_cache()
        with lock:
            try:
                return cache[func_id][k]
            except TypeError:
                raise TypeError(
                    "Arguments to a `shared_object` function must be hashable. "
                    "To support unhashable args, pass a `key` function to "
                    "`shared_object` when defining the function"
                )
            except KeyError:
                result = func(*args, **kwargs)
                if inspect.isgenerator(result):
                    generator = result
                    result = next(generator)
                    cache["generators"].append(generator)
                cache[func_id][k] = result
                return result

    return inner
