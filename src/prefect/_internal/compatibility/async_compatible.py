import asyncio
import inspect
from functools import wraps
from typing import Any, Callable, Coroutine, Protocol, TypeVar, Union

from typing_extensions import ParamSpec

R = TypeVar("R")
P = ParamSpec("P")


class AsyncCompatible(Protocol[P, R]):
    """Protocol for functions decorated with async_compatible."""

    def __call__(
        self, *args: P.args, **kwargs: P.kwargs
    ) -> Union[R, Coroutine[Any, Any, R]]:
        ...

    aio: Callable[P, Coroutine[Any, Any, R]]


def is_in_async_context() -> bool:
    """Check if we're in an async context."""
    try:
        # First check if we're in a coroutine
        if asyncio.current_task() is not None:
            return True

        # Check if we have a loop and it's running
        loop = asyncio.get_event_loop()
        return loop.is_running()
    except RuntimeError:
        return False


def async_compatible(
    async_impl: Callable[P, Coroutine[Any, Any, R]],
) -> Callable[[Callable[P, R]], AsyncCompatible[P, R]]:
    """
    Decorator that adds async compatibility to a sync function.

    The decorated function will:
    - Return a coroutine when in an async context (detected via running event loop)
    - Run synchronously when in a sync context
    - Provide .aio for explicit async access

    Args:
        async_impl: The async implementation to dispatch to when async execution
                   is needed
    """
    if not inspect.iscoroutinefunction(async_impl):
        raise TypeError(
            "async_impl must be an async function to dispatch in async contexts"
        )

    def decorator(sync_fn: Callable[P, R]) -> AsyncCompatible[P, R]:
        @wraps(sync_fn)
        def wrapper(
            *args: P.args, **kwargs: P.kwargs
        ) -> Union[R, Coroutine[Any, Any, R]]:
            if is_in_async_context():
                return async_impl(*args, **kwargs)
            return sync_fn(*args, **kwargs)

        # Attach the async implementation directly
        wrapper.aio = async_impl
        return wrapper  # type: ignore

    return decorator
