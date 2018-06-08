from typing import Any, Callable, Hashable, TypeVar

import wrapt

T = TypeVar("T")


def cache(validation_fn: Callable[[Any], Hashable]) -> Callable:
    @wrapt.decorator
    def inner(function: Callable[..., T], instance, args, kwargs) -> T:
        validation_key = validation_fn(instance)
        function_key = (function.__qualname__, args, frozenset(kwargs))

        if instance._cache.get("validation key", None) != validation_key:
            instance._cache.clear()
            instance._cache["validation key"] = validation_key

        if function_key in instance._cache:
            return instance._cache[function_key]

        else:
            result = function(*args, **kwargs)
            instance._cache[function_key] = result
            return result

    return inner
