"""
Utilities for working with clients.
"""

# This module must not import from `prefect.client` when it is imported to avoid
# circular imports for decorators such as `inject_client` which are widely used.

from functools import wraps
from typing import Any, Callable, Coroutine, Optional

from prefect._internal.concurrency.event_loop import get_running_loop
from prefect.client.orchestration import PrefectClient, get_client
from prefect.context import FlowRunContext, TaskRunContext
from prefect.utilities.asyncutils import asyncnullcontext


def get_or_infer_client(client: Optional[PrefectClient] = None) -> PrefectClient:
    """
    Infer a client from the provided client or the current context.
    """
    if client is not None:
        return client

    flow_run_context = FlowRunContext.get()
    task_run_context = TaskRunContext.get()
    if (
        flow_run_context
        and getattr(flow_run_context.client, "_loop") == get_running_loop()
    ):
        return flow_run_context.client
    elif (
        task_run_context
        and getattr(task_run_context.client, "_loop") == get_running_loop()
    ):
        return task_run_context.client
    else:

        return get_client()


def inject_client(fn: Callable[..., Any]) -> Callable[..., Coroutine[Any, Any, Any]]:
    """
    Simple helper to provide a context managed client to a asynchronous function.

    The decorated function _must_ take a `client` kwarg and if a client is passed when
    called it will be used instead of creating a new one, but it will not be context
    managed as it is assumed that the caller is managing the context.
    """

    @wraps(fn)
    async def with_injected_client(*args: Any, **kwargs: Any) -> Any:
        client = None
        client_context = asyncnullcontext()
        client = get_or_infer_client(kwargs.pop("client", None))
        async with client_context as new_client:
            kwargs.setdefault("client", new_client or client)
            return await fn(*args, **kwargs)

    return with_injected_client
