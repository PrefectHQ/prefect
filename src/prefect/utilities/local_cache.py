import functools
from collections import defaultdict

from toolz import curry

import prefect


_CACHES = defaultdict(lambda: defaultdict(dict))


def get_local_cache():
    key = prefect.context.get("flow_run_id")
    if key is None:
        raise ValueError("No local cache in context")
    return _CACHES[key]


def clear_local_cache():
    key = prefect.context.get("flow_run_id")
    _CACHES.pop(key, None)


def _default_key(*args, **kwargs):
    return (args, frozenset(kwargs.items()) if kwargs else None)


@curry
def cached(func, *, key=None):
    try:
        func_id = f"{func.__module__}.{func.__qualname__}-{id(func)}"
    except Exception:
        func_id = "cached-function-{id(func)}"

    if key is None:
        key = _default_key

    @functools.wraps(func)
    def inner(*args, **kwargs):
        k = key(*args, **kwargs)
        cache = get_local_cache()
        try:
            return cache[func_id][k]
        except TypeError:
            raise TypeError("Argumentws to a cached function must be hashable")
        except KeyError:
            cache[func_id][k] = result = func(*args, **kwargs)
            return result

    return inner
