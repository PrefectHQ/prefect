"""Shared server version checking logic for Prefect clients.

This module contains the version compatibility check cache and a standalone
async helper so that both HTTP-based clients (PrefectClient / SyncPrefectClient)
and WebSocket-based clients (PrefectEventsClient, PrefectEventSubscriber,
PrefectLogsSubscriber) can share the same once-per-process guard.
"""

import logging
import threading
from urllib.parse import urlparse, urlunparse

import httpx
from packaging import version

import prefect
from prefect.settings import get_current_settings

# ---------------------------------------------------------------------------
# Cache – keyed by (api_url, client_version) so each unique pair is checked
# at most once per process.
# ---------------------------------------------------------------------------
_API_VERSION_CHECK_CACHE: set[tuple[str, str]] = set()
_API_VERSION_CHECK_CACHE_LOCK = threading.Lock()


def _api_version_check_key(api_url: str, client_version: str) -> tuple[str, str]:
    return (api_url, client_version)


def _is_api_version_check_cached(key: tuple[str, str]) -> bool:
    with _API_VERSION_CHECK_CACHE_LOCK:
        return key in _API_VERSION_CHECK_CACHE


def _cache_api_version_check(key: tuple[str, str]) -> None:
    with _API_VERSION_CHECK_CACHE_LOCK:
        _API_VERSION_CHECK_CACHE.add(key)


def _clear_api_version_check_cache() -> None:
    """Clear cached API version compatibility checks (for tests)."""
    with _API_VERSION_CHECK_CACHE_LOCK:
        _API_VERSION_CHECK_CACHE.clear()


def _sanitize_url(url: str) -> str:
    """Return *url* with any embedded userinfo (user:password@) removed."""
    parsed = urlparse(url)
    if parsed.username or parsed.password:
        # Rebuild netloc without credentials
        host = parsed.hostname or ""
        port_part = f":{parsed.port}" if parsed.port else ""
        sanitized = parsed._replace(netloc=f"{host}{port_part}")
        return urlunparse(sanitized)
    return url


# ---------------------------------------------------------------------------
# Standalone async check – usable by any client that knows its *api_url*.
# ---------------------------------------------------------------------------


async def check_server_version(
    api_url: str,
    logger: logging.Logger,
    *,
    raise_on_error: bool = True,
) -> None:
    """Perform a one-shot server version compatibility check.

    The check is skipped when:
    * The ``server_version_check_enabled`` setting is ``False``.
    * The *api_url* points at Prefect Cloud (Cloud is always compatible).
    * A check for this *(api_url, client_version)* pair has already passed.

    On a major-version mismatch a ``RuntimeError`` is raised (regardless of
    *raise_on_error*).  When the server is simply older than the client a
    warning is logged.

    Args:
        api_url: The base Prefect API URL (e.g. ``http://localhost:4200/api``).
        logger: Logger used for warnings and debug messages.
        raise_on_error: When ``True`` (the default, used by HTTP clients),
            raise ``RuntimeError`` if the version endpoint cannot be reached.
            When ``False`` (used by WebSocket clients), log a debug message
            and return silently so that the caller can still attempt its
            connection.
    """
    settings = get_current_settings()

    if not settings.client.server_version_check_enabled:
        return

    # Cloud is always compatible as a server
    cloud_api_url = str(settings.cloud.api_url)
    if api_url.startswith(cloud_api_url):
        return

    client_version = prefect.__version__
    key = _api_version_check_key(api_url, client_version)
    if _is_api_version_check_cached(key):
        return

    try:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(f"{api_url}/admin/version")
            api_version_str: str = response.json()
    except Exception as e:
        if "Unauthorized" in str(e):
            raise
        if raise_on_error:
            raise RuntimeError(
                f"Failed to reach API at {_sanitize_url(api_url)}"
            ) from e
        logger.debug(
            "Unable to check server version at %s: %s",
            _sanitize_url(api_url),
            e,
        )
        return

    api_ver = version.parse(api_version_str)
    client_ver = version.parse(client_version)

    if api_ver.major != client_ver.major:
        raise RuntimeError(
            f"Found incompatible versions: client: {client_ver}, server: {api_ver}. "
            "Major versions must match."
        )

    if api_ver < client_ver:
        logger.warning(
            "Your Prefect server is running an older version of Prefect "
            "than your client which may result in unexpected behavior. "
            "Please upgrade your Prefect server from version %s to "
            "version %s or higher.",
            api_ver,
            client_ver,
        )

    _cache_api_version_check(key)
