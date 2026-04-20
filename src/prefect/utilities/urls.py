import inspect
import ipaddress
import socket
import time
import urllib.parse
from collections.abc import Iterable
from logging import Logger
from string import Formatter
from typing import TYPE_CHECKING, Any, Literal, Optional, Union, cast
from urllib.parse import urlparse
from uuid import UUID

import anyio.to_thread
import httpcore
import httpx
from pydantic import BaseModel

from prefect import settings
from prefect.logging.loggers import get_logger

if TYPE_CHECKING:
    from prefect.blocks.core import Block
    from prefect.events.schemas.automations import Automation
    from prefect.events.schemas.events import ReceivedEvent, Resource
    from prefect.futures import PrefectFuture
    from prefect.variables import Variable

logger: Logger = get_logger("utilities.urls")

# The following objects are excluded from UI URL generation because we lack a
# directly-addressable URL:
#   artifact
#   variable
#   saved-search
UI_URL_FORMATS = {
    "flow": "flows/flow/{obj_id}",
    "flow-run": "runs/flow-run/{obj_id}",
    "flow-run-response": "runs/flow-run/{obj_id}",
    "task-run": "runs/task-run/{obj_id}",
    "block": "blocks/block/{obj_id}",
    "block-document": "blocks/block/{obj_id}",
    "work-pool": "work-pools/work-pool/{obj_id}",
    "work-queue": "work-queues/work-queue/{obj_id}",
    "concurrency-limit": "concurrency-limits/concurrency-limit/{obj_id}",
    "deployment": "deployments/deployment/{obj_id}",
    "automation": "automations/automation/{obj_id}",
    "received-event": "events/event/{occurred}/{obj_id}",
    "worker": "work-pools/work-pool/{work_pool_name}/worker/{obj_id}",
}

# The following objects are excluded from API URL generation because we lack a
# directly-addressable URL:
#   worker
#   artifact
#   saved-search
#   received-event
API_URL_FORMATS = {
    "flow": "flows/{obj_id}",
    "flow-run": "flow_runs/{obj_id}",
    "task-run": "task_runs/{obj_id}",
    "variable": "variables/name/{obj_id}",
    "block": "blocks/{obj_id}",
    "work-pool": "work_pools/{obj_id}",
    "work-queue": "work_queues/{obj_id}",
    "concurrency-limit": "concurrency_limits/{obj_id}",
    "deployment": "deployments/{obj_id}",
    "automation": "automations/{obj_id}",
}

URLType = Literal["ui", "api"]
RUN_TYPES = {"flow-run", "task-run"}


def validate_restricted_url(url: str) -> None:
    """
    Validate that the provided URL is safe for outbound requests.  This prevents
    attacks like SSRF (Server Side Request Forgery), where an attacker can make
    requests to internal services (like the GCP metadata service, localhost addresses,
    or in-cluster Kubernetes services).

    This is a pre-flight check that validates every address the hostname resolves
    to via `getaddrinfo`.  Because DNS can change between this check and the
    actual HTTP connection, callers that need hardened SSRF protection should
    also use `SSRFProtectedAsyncHTTPTransport` / `SSRFProtectedHTTPTransport`,
    which re-validate at connection time and connect to the pre-resolved IP to
    close the TOCTOU window exploited by DNS rebinding attacks.

    Args:
        url: The URL to validate.

    Raises:
        ValueError: If the URL is a restricted URL.
    """

    try:
        parsed_url = urlparse(url)
    except ValueError:
        raise ValueError(f"{url!r} is not a valid URL.")

    if parsed_url.scheme not in ("http", "https"):
        raise ValueError(
            f"{url!r} is not a valid URL.  Only HTTP and HTTPS URLs are allowed."
        )

    hostname = parsed_url.hostname or ""

    # Remove IPv6 brackets if present
    if hostname.startswith("[") and hostname.endswith("]"):
        hostname = hostname[1:-1]

    if not hostname:
        raise ValueError(f"{url!r} is not a valid URL.")

    try:
        _validate_resolved_hostname(hostname)
    except _RestrictedHostError as exc:
        raise ValueError(f"{url!r} is not a valid URL.  {exc}")


class _RestrictedHostError(Exception):
    """Internal exception raised when a hostname resolves to a restricted address."""


def _validate_resolved_hostname(hostname: str) -> list[str]:
    """Resolve `hostname` and validate every returned address.

    Returns the list of resolved IPs (as strings) in resolution order.  Raises
    `_RestrictedHostError` if any resolved address is private, or if the
    hostname cannot be resolved.

    Using `getaddrinfo` (rather than `gethostbyname`, which returns only the
    first A record) closes an SSRF bypass where a hostname publishes both a
    public and a private A/AAAA record: every resolved address is checked.
    """
    # IP literal: validate directly.
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        if ip.is_private:
            raise _RestrictedHostError(f"It resolves to the private address {ip}.")
        return [str(ip)]

    try:
        addrinfos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise _RestrictedHostError("It could not be resolved.")

    resolved: list[str] = []
    for addrinfo in addrinfos:
        sockaddr = addrinfo[4]
        ip_str = sockaddr[0]
        # Strip IPv6 zone identifier if present (e.g. "fe80::1%eth0")
        ip_str = ip_str.split("%", 1)[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if ip.is_private:
            raise _RestrictedHostError(f"It resolves to the private address {ip}.")
        if ip_str not in resolved:
            resolved.append(ip_str)

    if not resolved:
        raise _RestrictedHostError("It could not be resolved.")

    return resolved


class _SSRFProtectedAsyncBackend(httpcore.AsyncNetworkBackend):
    """An `httpcore.AsyncNetworkBackend` that validates resolved addresses.

    Wraps an existing backend and, on each `connect_tcp` call, resolves the
    hostname itself, rejects any resolved address that is private, and then
    connects to the validated IP directly (rather than the hostname) so that
    the underlying backend cannot re-resolve to a different address.

    TLS SNI / certificate validation is unaffected because httpcore passes the
    original hostname to `start_tls` via `server_hostname`, independently of
    the host used for the TCP connection.
    """

    def __init__(self, wrapped: httpcore.AsyncNetworkBackend) -> None:
        self._wrapped = wrapped

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: Optional[float] = None,
        local_address: Optional[str] = None,
        socket_options: Optional[Iterable[Any]] = None,
    ) -> httpcore.AsyncNetworkStream:
        # Resolve in a worker thread so the event loop is not blocked during
        # DNS lookups (which can be slow or intermittently failing).
        validated_ips = await anyio.to_thread.run_sync(
            _resolve_and_validate_for_connect, host
        )
        last_exc: Optional[BaseException] = None
        deadline = time.monotonic() + timeout if timeout is not None else None
        for ip in validated_ips:
            remaining = _remaining_timeout(deadline)
            if remaining == 0.0:
                break
            try:
                return await self._wrapped.connect_tcp(
                    ip,
                    port,
                    timeout=remaining,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout, OSError) as exc:
                last_exc = exc
        assert last_exc is not None
        raise last_exc

    async def connect_unix_socket(
        self,
        path: str,
        timeout: Optional[float] = None,
        socket_options: Optional[Iterable[Any]] = None,
    ) -> httpcore.AsyncNetworkStream:
        return await self._wrapped.connect_unix_socket(
            path, timeout=timeout, socket_options=socket_options
        )

    async def sleep(self, seconds: float) -> None:
        await self._wrapped.sleep(seconds)


class _SSRFProtectedSyncBackend(httpcore.NetworkBackend):
    """Synchronous counterpart of `_SSRFProtectedAsyncBackend`."""

    def __init__(self, wrapped: httpcore.NetworkBackend) -> None:
        self._wrapped = wrapped

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: Optional[float] = None,
        local_address: Optional[str] = None,
        socket_options: Optional[Iterable[Any]] = None,
    ) -> httpcore.NetworkStream:
        validated_ips = _resolve_and_validate_for_connect(host)
        last_exc: Optional[BaseException] = None
        deadline = time.monotonic() + timeout if timeout is not None else None
        for ip in validated_ips:
            remaining = _remaining_timeout(deadline)
            if remaining == 0.0:
                break
            try:
                return self._wrapped.connect_tcp(
                    ip,
                    port,
                    timeout=remaining,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout, OSError) as exc:
                last_exc = exc
        assert last_exc is not None
        raise last_exc

    def connect_unix_socket(
        self,
        path: str,
        timeout: Optional[float] = None,
        socket_options: Optional[Iterable[Any]] = None,
    ) -> httpcore.NetworkStream:
        return self._wrapped.connect_unix_socket(
            path, timeout=timeout, socket_options=socket_options
        )

    def sleep(self, seconds: float) -> None:
        self._wrapped.sleep(seconds)


def _remaining_timeout(deadline: Optional[float]) -> Optional[float]:
    """Return the time left until `deadline`, or `None` if no deadline is set.

    Clamps to `0.0` when the deadline has already passed.  Callers use this to
    share a single connect-timeout budget across multiple per-IP retries so
    that connect time stays bounded (roughly) by the caller's timeout rather
    than scaling with the number of resolved addresses.
    """
    if deadline is None:
        return None
    return max(0.0, deadline - time.monotonic())


def _resolve_and_validate_for_connect(host: str) -> list[str]:
    """Resolve `host` and return all safe IPs to connect to.

    Every returned IP has been validated against the private-address blocklist;
    callers iterate them in order and retry on connect failures so that dual-
    stack hostnames still work in single-stack environments.

    Raises `httpcore.ConnectError` if any resolved address is private or if the
    hostname cannot be resolved.  The returned IPs are passed to the underlying
    network backend as IP literals, so it will not perform further DNS
    resolution — eliminating the DNS rebinding TOCTOU window.
    """
    try:
        return _validate_resolved_hostname(host)
    except _RestrictedHostError as exc:
        raise httpcore.ConnectError(f"Refusing to connect to {host!r}: {exc}") from None


class SSRFProtectedAsyncHTTPTransport(httpx.AsyncHTTPTransport):
    """An `httpx.AsyncHTTPTransport` that guards against DNS rebinding SSRF.

    Behaves identically to `httpx.AsyncHTTPTransport` except that, for every
    request, the hostname is resolved, every resolved address is checked
    against the private-address blocklist, and the connection is made to the
    specific validated IP.  This closes the TOCTOU window between a pre-flight
    `validate_restricted_url` check and the actual HTTP connection.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._pool._network_backend = _SSRFProtectedAsyncBackend(
            self._pool._network_backend
        )


class SSRFProtectedHTTPTransport(httpx.HTTPTransport):
    """Synchronous counterpart of `SSRFProtectedAsyncHTTPTransport`."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._pool._network_backend = _SSRFProtectedSyncBackend(
            self._pool._network_backend
        )


def convert_class_to_name(obj: Any) -> str:
    """
    Convert CamelCase class name to dash-separated lowercase name
    """
    cls = obj if inspect.isclass(obj) else obj.__class__
    name = cls.__name__
    return "".join(["-" + i.lower() if i.isupper() else i for i in name]).lstrip("-")


def url_for(
    obj: Union[
        "PrefectFuture[Any]",
        "Block",
        "Variable",
        "Automation",
        "Resource",
        "ReceivedEvent",
        BaseModel,
        str,
    ],
    obj_id: Optional[Union[str, UUID]] = None,
    url_type: URLType = "ui",
    default_base_url: Optional[str] = None,
    **additional_format_kwargs: Any,
) -> Optional[str]:
    """
    Returns the URL for a Prefect object.

    Pass in a supported object directly or provide an object name and ID.

    Args:
        obj (Union[PrefectFuture, Block, Variable, Automation, Resource, ReceivedEvent, BaseModel, str]):
            A Prefect object to get the URL for, or its URL name and ID.
        obj_id (Union[str, UUID], optional):
            The UUID of the object.
        url_type (Literal["ui", "api"], optional):
            Whether to return the URL for the UI (default) or API.
        default_base_url (str, optional):
            The default base URL to use if no URL is configured.
        additional_format_kwargs (Dict[str, Any], optional):
            Additional keyword arguments to pass to the URL format.

    Returns:
        Optional[str]: The URL for the given object or None if the object is not supported.

    Examples:
        url_for(my_flow_run)
        url_for(obj=my_flow_run)
        url_for("flow-run", obj_id="123e4567-e89b-12d3-a456-426614174000")
    """
    from prefect.blocks.core import Block
    from prefect.client.schemas.objects import WorkPool
    from prefect.events.schemas.automations import Automation
    from prefect.events.schemas.events import ReceivedEvent, Resource
    from prefect.futures import PrefectFuture

    if isinstance(obj, PrefectFuture):
        name = "task-run"
    elif isinstance(obj, Block):
        name = "block"
    elif isinstance(obj, Automation):
        name = "automation"
    elif isinstance(obj, ReceivedEvent):
        name = "received-event"
    elif isinstance(obj, Resource):
        if obj.id.startswith("prefect."):
            name = obj.id.split(".")[1]
        else:
            logger.debug(f"No URL known for resource with ID: {obj.id}")
            return None
    elif isinstance(obj, str):
        name = obj
    else:
        name = convert_class_to_name(obj)

    # Can't do an isinstance check here because the client build
    # doesn't have access to that server schema.
    if name == "work-queue-with-status":
        name = "work-queue"

    if url_type != "ui" and url_type != "api":
        raise ValueError(f"Invalid URL type: {url_type}. Use 'ui' or 'api'.")

    if url_type == "ui" and name not in UI_URL_FORMATS:
        logger.debug("No UI URL known for this object: %s", name)
        return None
    elif url_type == "api" and name not in API_URL_FORMATS:
        logger.debug("No API URL known for this object: %s", name)
        return None

    if isinstance(obj, str) and not obj_id:
        raise ValueError(
            "If passing an object name, you must also provide an object ID."
        )

    base_url = (
        settings.PREFECT_UI_URL.value()
        if url_type == "ui"
        else settings.PREFECT_API_URL.value()
    )
    base_url = base_url or default_base_url

    if not base_url:
        logger.debug(
            f"No URL found for the Prefect {'UI' if url_type == 'ui' else 'API'}, "
            f"and no default base path provided."
        )
        return None

    if not obj_id:
        # We treat PrefectFuture as if it was the underlying task run,
        # so we need to check the object type here instead of name.
        if isinstance(obj, PrefectFuture):
            obj_id = getattr(obj, "task_run_id", None)
        elif name == "block":
            # Blocks are client-side objects whose API representation is a
            # BlockDocument.
            obj_id = getattr(obj, "_block_document_id")
        elif name in ("variable", "work-pool"):
            if TYPE_CHECKING:
                assert isinstance(obj, (Variable, WorkPool))
            obj_id = obj.name
        elif isinstance(obj, Resource):
            obj_id = obj.id.rpartition(".")[2]
        else:
            obj_id = getattr(obj, "id", None)
        if not obj_id:
            logger.debug(
                "An ID is required to build a URL, but object did not have one: %s", obj
            )
            return ""

    url_format = (
        UI_URL_FORMATS.get(name) if url_type == "ui" else API_URL_FORMATS.get(name)
    )
    assert url_format is not None

    # Use duck-typing to handle both client-side and server-side ReceivedEvent
    if name == "received-event" and hasattr(obj, "occurred"):
        # Cast to ReceivedEvent for type checking - we've verified it has the
        # required attributes via hasattr and name check above
        event = cast(ReceivedEvent, obj)
        url = url_format.format(
            occurred=event.occurred.strftime("%Y-%m-%d"), obj_id=obj_id
        )
    else:
        obj_keys = [
            fname
            for _, fname, _, _ in Formatter().parse(url_format)
            if fname is not None and fname != "obj_id"
        ]

        if not all(key in additional_format_kwargs for key in obj_keys):
            raise ValueError(
                f"Unable to generate URL for {name} because the following keys are missing: {', '.join(obj_keys)}"
            )

        url = url_format.format(obj_id=obj_id, **additional_format_kwargs)

    if not base_url.endswith("/"):
        base_url += "/"
    return urllib.parse.urljoin(base_url, url)
