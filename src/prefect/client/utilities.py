"""
Utilities for working with clients.
"""
# This module must not import from `prefect.client` when it is imported to avoid
# circular imports for decorators such as `inject_client` which are widely used.

from functools import wraps

from prefect.utilities.asyncutils import asyncnullcontext
from prefect._internal.concurrency.event_loop import get_running_loop


def inject_client(fn):
    """
    Simple helper to provide a context managed client to a asynchronous function.

    The decorated function _must_ take a `client` kwarg and if a client is passed when
    called it will be used instead of creating a new one, but it will not be context
    managed as it is assumed that the caller is managing the context.
    """

    @wraps(fn)
    async def with_injected_client(*args, **kwargs):
        from prefect.client.orchestration import get_client
        from prefect.context import FlowRunContext, TaskRunContext

        flow_run_context = FlowRunContext.get()
        task_run_context = TaskRunContext.get()
        client = None
        client_context = asyncnullcontext()

        if "client" in kwargs and kwargs["client"] is not None:
            # Client provided in kwargs
            client = kwargs["client"]
        elif flow_run_context and flow_run_context.client._loop == get_running_loop():
            # Client available from flow run context
            client = flow_run_context.client
        elif task_run_context and task_run_context.client._loop == get_running_loop():
            # Client available from task run context
            client = task_run_context.client

        else:
            # A new client is needed
            client_context = get_client()

        # Removes existing client to allow it to be set by setdefault below
        kwargs.pop("client", None)

        async with client_context as new_client:
            kwargs.setdefault("client", new_client or client)
            return await fn(*args, **kwargs)

    return with_injected_client
