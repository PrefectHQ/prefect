import copy
import sys
import threading
from collections import defaultdict
from contextlib import asynccontextmanager
from functools import partial
from typing import Callable, ContextManager, Dict, Set, Tuple, Type

import anyio
import httpx
from asgi_lifespan import LifespanManager
from fastapi import FastAPI, status
from httpx import HTTPStatusError, Response
from typing_extensions import Self

from prefect.exceptions import PrefectHTTPStatusError
from prefect.logging import get_logger

# Datastores for lifespan management, keys should be a tuple of thread and app identities.
APP_LIFESPANS: Dict[Tuple[int, int], LifespanManager] = {}
APP_LIFESPANS_REF_COUNTS: Dict[Tuple[int, int], int] = {}
# Blocks concurrent access to the above dicts per thread. The index should be the thread identity.
APP_LIFESPANS_LOCKS: Dict[int, anyio.Lock] = defaultdict(anyio.Lock)


logger = get_logger("client")


@asynccontextmanager
async def app_lifespan_context(app: FastAPI) -> ContextManager[None]:
    """
    A context manager that calls startup/shutdown hooks for the given application.

    Lifespan contexts are cached per application to avoid calling the lifespan hooks
    more than once if the context is entered in nested code. A no-op context will be
    returned if the context for the given application is already being managed.

    This manager is robust to concurrent access within the event loop. For example,
    if you have concurrent contexts for the same application, it is guaranteed that
    startup hooks will be called before their context starts and shutdown hooks will
    only be called after their context exits.

    A reference count is used to support nested use of clients without running
    lifespan hooks excessively. The first client context entered will create and enter
    a lifespan context. Each subsequent client will increment a reference count but will
    not create a new lifespan context. When each client context exits, the reference
    count is decremented. When the last client context exits, the lifespan will be
    closed.

    In simple nested cases, the first client context will be the one to exit the
    lifespan. However, if client contexts are entered concurrently they may not exit
    in a consistent order. If the first client context was responsible for closing
    the lifespan, it would have to wait until all other client contexts to exit to
    avoid firing shutdown hooks while the application is in use. Waiting for the other
    clients to exit can introduce deadlocks, so, instead, the first client will exit
    without closing the lifespan context and reference counts will be used to ensure
    the lifespan is closed once all of the clients are done.
    """
    # TODO: A deadlock has been observed during multithreaded use of clients while this
    #       lifespan context is being used. This has only been reproduced on Python 3.7
    #       and while we hope to discourage using multiple event loops in threads, this
    #       bug may emerge again.
    #       See https://github.com/PrefectHQ/orion/pull/1696
    thread_id = threading.get_ident()

    # The id of the application is used instead of the hash so each application instance
    # is managed independently even if they share the same settings. We include the
    # thread id since applications are managed separately per thread.
    key = (thread_id, id(app))

    # On exception, this will be populated with exception details
    exc_info = (None, None, None)

    # Get a lock unique to this thread since anyio locks are not threadsafe
    lock = APP_LIFESPANS_LOCKS[thread_id]

    async with lock:
        if key in APP_LIFESPANS:
            # The lifespan is already being managed, just increment the reference count
            APP_LIFESPANS_REF_COUNTS[key] += 1
        else:
            # Create a new lifespan manager
            APP_LIFESPANS[key] = context = LifespanManager(
                app, startup_timeout=30, shutdown_timeout=30
            )
            APP_LIFESPANS_REF_COUNTS[key] = 1

            # Ensure we enter the context before releasing the lock so startup hooks
            # are complete before another client can be used
            await context.__aenter__()

    try:
        yield
    except BaseException:
        exc_info = sys.exc_info()
        raise
    finally:
        # If we do not shield against anyio cancellation, the lock will return
        # immediately and the code in its context will not run, leaving the lifespan
        # open
        with anyio.CancelScope(shield=True):
            async with lock:
                # After the consumer exits the context, decrement the reference count
                APP_LIFESPANS_REF_COUNTS[key] -= 1

                # If this the last context to exit, close the lifespan
                if APP_LIFESPANS_REF_COUNTS[key] <= 0:
                    APP_LIFESPANS_REF_COUNTS.pop(key)
                    context = APP_LIFESPANS.pop(key)
                    await context.__aexit__(*exc_info)


class PrefectResponse(httpx.Response):
    """
    A Prefect wrapper for the `httpx.Response` class.

    Provides more informative error messages.
    """

    def raise_for_status(self) -> None:
        """
        Raise an exception if the response contains an HTTPStatusError.

        The `PrefectHTTPStatusError` contains useful additional information that
        is not contained in the `HTTPStatusError`.
        """
        try:
            return super().raise_for_status()
        except HTTPStatusError as exc:
            raise PrefectHTTPStatusError.from_httpx_error(exc) from exc.__cause__

    @classmethod
    def from_httpx_response(cls: Type[Self], response: httpx.Response) -> Self:
        """
        Create a `PrefectReponse` from an `httpx.Response`.

        By changing the `__class__` attribute of the Response, we change the method
        resolution order to look for methods defined in PrefectResponse, while leaving
        everything else about the original Response instance intact.
        """
        new_response = copy.copy(response)
        new_response.__class__ = cls
        return new_response


class PrefectHttpxClient(httpx.AsyncClient):
    """
    A Prefect wrapper for the async httpx client with support for retry-after headers
    for:

    - 429 CloudFlare-style rate limiting
    - 503 Service unavailable

    Additionally, this client will always call `raise_for_status` on responses.

    For more details on rate limit headers, see:
    [Configuring Cloudflare Rate Limiting](https://support.cloudflare.com/hc/en-us/articles/115001635128-Configuring-Rate-Limiting-from-UI)
    """

    RETRY_MAX = 5

    async def _send_with_retry(
        self,
        request: Callable,
        retry_codes: Set[int] = set(),
        retry_exceptions: Tuple[Exception, ...] = tuple(),
    ):
        """
        Send a request and retry it if it fails.

        Sends the provided request and retries it up to self.RETRY_MAX times if
        the request either raises an exception listed in `retry_exceptions` or receives
        a response with a status code listed in `retry_codes`.

        Retries will be delayed based on either the retry header (preferred) or
        exponential backoff if a retry header is not provided.
        """
        try_count = 0
        response = None

        while try_count <= self.RETRY_MAX:
            try_count += 1
            retry_seconds = None
            exc_info = None

            try:
                response = await request()
            except retry_exceptions:
                if try_count > self.RETRY_MAX:
                    raise
                # Otherwise, we will ignore this error but capture the info for logging
                exc_info = sys.exc_info()
            else:
                # We got a response; return immediately if it is not retryable
                if response.status_code not in retry_codes:
                    return response

                if "Retry-After" in response.headers:
                    retry_seconds = float(response.headers["Retry-After"])

            # Use an exponential back-off if not set in a header
            if retry_seconds is None:
                retry_seconds = 2**try_count

            logger.debug(
                (
                    "Encountered retryable exception during request. "
                    if exc_info
                    else "Received response with retryable status code. "
                )
                + (
                    f"Another attempt will be made in {retry_seconds}s. "
                    f"This is attempt {try_count}/{self.RETRY_MAX + 1}."
                ),
                exc_info=exc_info,
            )
            await anyio.sleep(retry_seconds)

        assert (
            response is not None
        ), "Retry handling ended without response or exception"

        # We ran out of retries, return the failed response
        return response

    async def send(self, *args, **kwargs) -> Response:
        api_request = partial(super().send, *args, **kwargs)

        response = await self._send_with_retry(
            request=api_request,
            retry_codes={
                status.HTTP_429_TOO_MANY_REQUESTS,
                status.HTTP_503_SERVICE_UNAVAILABLE,
            },
            retry_exceptions=(
                httpx.ReadTimeout,
                httpx.PoolTimeout,
                # `ConnectionResetError` when reading socket raises as a `ReadError`
                httpx.ReadError,
                # Uvicorn bug, see https://github.com/PrefectHQ/prefect/issues/7512
                httpx.RemoteProtocolError,
                # HTTP2 bug, see https://github.com/PrefectHQ/prefect/issues/7442
                httpx.LocalProtocolError,
            ),
        )

        # Always raise bad responses
        # NOTE: We may want to remove this and handle responses per route in the
        #       `OrionClient`

        response.raise_for_status()

        return response
