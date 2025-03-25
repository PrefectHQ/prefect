"""
Utilities for working with clients.
"""

# This module must not import from `prefect.client` when it is imported to avoid
# circular imports for decorators such as `inject_client` which are widely used.

from collections.abc import Coroutine
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Optional, Union

from typing_extensions import Concatenate, ParamSpec, TypeGuard, TypeVar

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient, SyncPrefectClient

P = ParamSpec("P")
R = TypeVar("R", infer_variance=True)


def _current_async_client(
    client: Union["PrefectClient", "SyncPrefectClient"],
) -> TypeGuard["PrefectClient"]:
    """Determine if the client is a PrefectClient instance attached to the current loop"""
    from prefect._internal.concurrency.event_loop import get_running_loop

    # Only a PrefectClient will have a _loop attribute that is the current loop
    return getattr(client, "_loop", None) == get_running_loop()


def get_or_create_client(
    client: Optional["PrefectClient"] = None,
) -> tuple["PrefectClient", bool]:
    """
    Returns provided client, infers a client from context if available, or creates a new client.

    Args:
        - client (PrefectClient, optional): an optional client to use

    Returns:
        - tuple: a tuple of the client and a boolean indicating if the client was inferred from context
    """
    if client is not None:
        return client, True

    from prefect.context import AsyncClientContext, FlowRunContext, TaskRunContext

    async_client_context = AsyncClientContext.get()
    flow_run_context = FlowRunContext.get()
    task_run_context = TaskRunContext.get()

    for context in (async_client_context, flow_run_context, task_run_context):
        if context is None:
            continue
        if _current_async_client(context_client := context.client):
            return context_client, True

    from prefect.client.orchestration import get_client as get_httpx_client

    return get_httpx_client(), False


def client_injector(
    func: Callable[Concatenate["PrefectClient", P], Coroutine[Any, Any, R]],
) -> Callable[P, Coroutine[Any, Any, R]]:
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
        given = kwargs.pop("client", None)
        if TYPE_CHECKING:
            assert given is None or isinstance(given, PrefectClient)
        client, inferred = get_or_create_client(given)
        if not inferred:
            context = client
        else:
            from prefect.utilities.asyncutils import asyncnullcontext

            context = asyncnullcontext(client)
        async with context as new_client:
            kwargs |= {"client": new_client}
            return await fn(*args, **kwargs)

    return with_injected_client
