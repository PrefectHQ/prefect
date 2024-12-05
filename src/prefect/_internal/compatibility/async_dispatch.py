import asyncio
import inspect
from functools import wraps
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Optional,
    TypeVar,
    Union,
)

from typing_extensions import ParamSpec

if TYPE_CHECKING:
    from prefect.flows import Flow
    from prefect.tasks import Task

R = TypeVar("R")
P = ParamSpec("P")


def is_in_async_context() -> bool:
    """
    Returns True if called from within an async context (coroutine or running event loop)
    """
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


def _is_acceptable_callable(
    obj: Union[Callable[..., Any], "Task[..., Any]", "Flow[..., Any]"],
) -> bool:
    if inspect.iscoroutinefunction(obj):
        return True
    fn = getattr(obj, "fn", None)
    if fn is not None and inspect.iscoroutinefunction(fn):
        return True
    if isinstance(obj, classmethod):
        if inspect.iscoroutinefunction(obj.__func__):  # type: ignore[arg-type]
            return True
    return False


def async_dispatch(
    async_impl: Callable[P, Coroutine[Any, Any, R]],
) -> Callable[[Callable[P, R]], Callable[P, Union[R, Coroutine[Any, Any, R]]]]:
    """
    Decorator that dispatches to either sync or async implementation based on context.

    Args:
        async_impl: The async implementation to dispatch to when in async context
    """

    def decorator(
        sync_fn: Callable[P, R],
    ) -> Callable[P, Union[R, Coroutine[Any, Any, R]]]:
        if not _is_acceptable_callable(async_impl):
            raise TypeError("async_impl must be an async function or method")

        @wraps(sync_fn)
        def wrapper(
            *args: P.args,
            _sync: Optional[bool] = None,  # type: ignore
            **kwargs: P.kwargs,
        ) -> Union[R, Coroutine[Any, Any, R]]:
            should_run_sync = _sync if _sync is not None else not is_in_async_context()

            if should_run_sync:
                return sync_fn(*args, **kwargs)
            return async_impl(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator
