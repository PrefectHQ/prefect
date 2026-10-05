"""Select Prefect's HTTP libraries once, before defining clients and exceptions.

`PREFECT_CLIENT_HTTP_BACKEND` is a process-start environment variable, rather
than a runtime Prefect setting: changing it after import cannot change existing
class hierarchies. Both HTTP families can remain installed independently.
"""

import copy
import os
import threading
import warnings
from typing import TYPE_CHECKING, Any

import httpcore as _legacy_httpcore
import httpx as _legacy_httpx

__all__ = [
    "HTTP_BACKEND",
    "AsyncClient",
    "AsyncHTTPTransport",
    "Client",
    "HTTPStatusError",
    "Request",
    "RequestError",
    "Response",
    "httpcore",
    "httpx",
    "create_ssl_context",
    "PrefectHTTPXDeprecationWarning",
    "warn_on_legacy_httpx",
]

HTTP_BACKEND = os.environ.get("PREFECT_CLIENT_HTTP_BACKEND", "httpx").strip().lower()
if HTTP_BACKEND not in {"httpx", "httpx2"}:
    raise ValueError(
        "PREFECT_CLIENT_HTTP_BACKEND must be 'httpx' or 'httpx2', "
        f"got {HTTP_BACKEND!r}. Set it before starting Python."
    )

if TYPE_CHECKING or HTTP_BACKEND == "httpx":
    import httpcore as httpcore
    import httpx as httpx
    from httpx import (
        AsyncClient,
        AsyncHTTPTransport,
        Client,
        HTTPStatusError,
        Request,
        RequestError,
        Response,
    )
else:
    try:
        import httpcore2 as httpcore
        import httpx2 as httpx
        from httpx2 import (
            AsyncHTTPTransport,
            HTTPStatusError,
            Request,
            RequestError,
            Response,
        )
    except ModuleNotFoundError as exc:
        if exc.name not in {"httpx2", "httpcore2"}:
            raise
        raise ImportError(
            "PREFECT_CLIENT_HTTP_BACKEND=httpx2 requires HTTPX2. "
            "Install 'httpx2[http2]>=2.13.0,<3.0.0' "
            "in this environment before starting Python."
        ) from exc

    class Client(httpx.Client):
        def _init_proxy_transport(
            self, proxy: httpx.Proxy, *args: Any, **kwargs: Any
        ) -> httpx.BaseTransport:
            proxy = _with_legacy_proxy_ssl_context(proxy)
            assert proxy is not None
            return super()._init_proxy_transport(proxy, *args, **kwargs)

    class AsyncClient(httpx.AsyncClient):
        def _init_proxy_transport(
            self, proxy: httpx.Proxy, *args: Any, **kwargs: Any
        ) -> httpx.AsyncBaseTransport:
            proxy = _with_legacy_proxy_ssl_context(proxy)
            assert proxy is not None
            return super()._init_proxy_transport(proxy, *args, **kwargs)


def _with_legacy_proxy_ssl_context(
    proxy: httpx.Proxy | httpx.URL | str | None,
) -> httpx.Proxy | None:
    if isinstance(proxy, (str, httpx.URL)):
        proxy = httpx.Proxy(url=proxy)
    if (
        HTTP_BACKEND == "httpx2"
        and proxy is not None
        and proxy.url.scheme == "https"
        and proxy.ssl_context is None
    ):
        # Proxy TLS has a separate trust context from the destination server.
        # Keep the legacy HTTPcore defaults without mutating a caller's Proxy.
        proxy = copy.copy(proxy)
        proxy.ssl_context = _legacy_httpcore.default_ssl_context()
    return proxy


# Keep certificate trust and environment overrides identical in both backends.
# HTTPX is retained throughout the deprecation window, so its public helper
# remains the authority instead of duplicating its SSL configuration behavior.
create_ssl_context = _legacy_httpx.create_ssl_context


class PrefectHTTPXDeprecationWarning(FutureWarning):
    """Visible notice for the transition away from the legacy HTTPX backend."""


_warning_lock = threading.Lock()
_legacy_warning_emitted = False


def warn_on_legacy_httpx() -> None:
    """Warn once per process when the legacy HTTP backend is first used."""
    global _legacy_warning_emitted
    if HTTP_BACKEND != "httpx" or _legacy_warning_emitted:
        return
    with _warning_lock:
        if _legacy_warning_emitted:
            return
        warnings.warn(
            "Prefect's legacy HTTPX backend is deprecated. It will remain "
            "available for at least six months and three minor version increases "
            "after this deprecation is first released. Install "
            "'httpx2[http2]>=2.13.0,<3.0.0', set PREFECT_CLIENT_HTTP_BACKEND=httpx2 "
            "before starting Python, and use HTTPX2 types for custom HTTP "
            "objects and exception handlers.",
            PrefectHTTPXDeprecationWarning,
            stacklevel=3,
        )
        _legacy_warning_emitted = True
