import asyncio
import inspect
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Coroutine, Optional, TypeVar, Union

from typing_extensions import ParamSpec

if TYPE_CHECKING:
    from prefect.tasks import Task

R = TypeVar("R")
P = ParamSpec("P")


def is_in_async_context() -> bool:
    """
    Returns True if called from within an async context.

    An async context is one of:
        - a coroutine
        - a running event loop
        - a task or flow that is async
    """
    from prefect.context import get_run_context
    from prefect.exceptions import MissingContextError

    try:
        run_ctx = get_run_context()
        parent_obj = getattr(run_ctx, "task", None)
        if not parent_obj:
            parent_obj = getattr(run_ctx, "flow", None)
        return getattr(parent_obj, "isasync", True)
    except MissingContextError:
        # not in an execution context, make best effort to
        # decide whether to syncify
        try:
            asyncio.get_running_loop()
            return True
        except RuntimeError:
            return False


def _is_acceptable_callable(
    obj: Union[Callable[P, R], "Task[P, R]", classmethod],
) -> bool:
    if inspect.iscoroutinefunction(obj):
        return True

    # Check if a task or flow. Need to avoid importing `Task` or `Flow` here
    # due to circular imports.
    if (fn := getattr(obj, "fn", None)) and inspect.iscoroutinefunction(fn):
        return True

    if isinstance(obj, classmethod) and inspect.iscoroutinefunction(obj.__func__):
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
            raise TypeError("async_impl must be an async function")

        @wraps(sync_fn)
        def wrapper(
            *args: P.args,
            _sync: Optional[bool] = None,  # type: ignore
            **kwargs: P.kwargs,
        ) -> Union[R, Coroutine[Any, Any, R]]:
            should_run_sync = _sync if _sync is not None else not is_in_async_context()

            if should_run_sync:
                return sync_fn(*args, **kwargs)
            if isinstance(async_impl, classmethod):
                return async_impl.__func__(*args, **kwargs)
            return async_impl(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator
