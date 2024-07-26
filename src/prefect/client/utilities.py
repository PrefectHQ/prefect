"""
Utilities for working with clients.
"""

# This module must not import from `prefect.client` when it is imported to avoid
# circular imports for decorators such as `inject_client` which are widely used.

from functools import wraps
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Optional,
    Tuple,
    TypeVar,
    cast,
)

from typing_extensions import Concatenate, ParamSpec

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient

P = ParamSpec("P")
R = TypeVar("R")


def get_or_create_client(
    client: Optional["PrefectClient"] = None,
) -> Tuple["PrefectClient", bool]:
    """
    Returns provided client, infers a client from context if available, or creates a new client.

    Args:
        - client (PrefectClient, optional): an optional client to use

    Returns:
        - tuple: a tuple of the client and a boolean indicating if the client was inferred from context
    """
    if client is not None:
        return client, True
    from prefect._internal.concurrency.event_loop import get_running_loop
    from prefect.context import AsyncClientContext, FlowRunContext, TaskRunContext

    async_client_context = AsyncClientContext.get()
    flow_run_context = FlowRunContext.get()
    task_run_context = TaskRunContext.get()

    if async_client_context and async_client_context.client._loop == get_running_loop():
        return async_client_context.client, True
    elif (
        flow_run_context
        and getattr(flow_run_context.client, "_loop", None) == get_running_loop()
    ):
        return flow_run_context.client, True
    elif (
        task_run_context
        and getattr(task_run_context.client, "_loop", None) == get_running_loop()
    ):
        return task_run_context.client, True
    else:
        from prefect.client.orchestration import get_client as get_httpx_client

        return get_httpx_client(), False


def client_injector(
    func: Callable[Concatenate["PrefectClient", P], Awaitable[R]],
) -> Callable[P, Awaitable[R]]:
    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        client, _ = get_or_create_client()
        return await func(client, *args, **kwargs)

    return wrapper


def inject_client(
    fn: Callable[P, Coroutine[Any, Any, R]],
) -> Callable[P, Coroutine[Any, Any, R]]:
    """
    Simple helper to provide a context managed client to an asynchronous function.

    The decorated function _must_ take a `client` kwarg and if a client is passed when
    called it will be used instead of creating a new one, but it will not be context
    managed as it is assumed that the caller is managing the context.
    """

    @wraps(fn)
    async def with_injected_client(*args: P.args, **kwargs: P.kwargs) -> R:
        client = cast(Optional["PrefectClient"], kwargs.pop("client", None))
        client, inferred = get_or_create_client(client)
        if not inferred:
            context = client
        else:
            from prefect.utilities.asyncutils import asyncnullcontext

            context = asyncnullcontext()
        async with context as new_client:
            kwargs.setdefault("client", new_client or client)
            return await fn(*args, **kwargs)

    return with_injected_client
