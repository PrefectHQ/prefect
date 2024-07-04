from contextlib import contextmanager
from contextvars import ContextVar
from typing import (
    Any,
    Generator,
    Optional,
)

from pydantic import PrivateAttr

from prefect.client.orchestration import PrefectClient, SyncPrefectClient, get_client
from prefect.utilities.asyncutils import run_coro_as_sync

from .base import ContextModel


class ClientContext(ContextModel):
    """
    A context for managing the Prefect client instances.

    Clients were formerly tracked on the TaskRunContext and FlowRunContext, but
    having two separate places and the addition of both sync and async clients
    made it difficult to manage. This context is intended to be the single
    source for clients.

    The client creates both sync and async clients, which can either be read
    directly from the context object OR loaded with get_client, inject_client,
    or other Prefect utilities.

    with ClientContext.get_or_create() as ctx:
        c1 = get_client(sync_client=True)
        c2 = get_client(sync_client=True)
        assert c1 is c2
        assert c1 is ctx.sync_client
    """

    __var__ = ContextVar("clients")
    sync_client: SyncPrefectClient
    async_client: PrefectClient
    _httpx_settings: Optional[dict[str, Any]] = PrivateAttr(None)
    _context_stack: int = PrivateAttr(0)

    def __init__(self, httpx_settings: Optional[dict[str, Any]] = None):
        super().__init__(
            sync_client=get_client(sync_client=True, httpx_settings=httpx_settings),
            async_client=get_client(sync_client=False, httpx_settings=httpx_settings),
        )
        self._httpx_settings = httpx_settings
        self._context_stack = 0

    def __enter__(self):
        self._context_stack += 1
        if self._context_stack == 1:
            self.sync_client.__enter__()
            run_coro_as_sync(self.async_client.__aenter__())
            return super().__enter__()
        else:
            return self

    def __exit__(self, *exc_info):
        self._context_stack -= 1
        if self._context_stack == 0:
            self.sync_client.__exit__(*exc_info)
            run_coro_as_sync(self.async_client.__aexit__(*exc_info))
            return super().__exit__(*exc_info)

    @classmethod
    @contextmanager
    def get_or_create(cls) -> Generator["ClientContext", None, None]:
        ctx = ClientContext.get()
        if ctx:
            yield ctx
        else:
            with ClientContext() as ctx:
                yield ctx
