"""Optional fastapi-guard security middleware wiring for the Prefect server.

fastapi-guard (https://github.com/Guard-Core/fastapi-guard) provides IP
block/allow lists, rate limiting with auto-ban, user-agent blocking,
penetration-attempt detection, passive mode, optional security headers,
optional Redis-backed shared state, and optional IPInfo geo/cloud-provider
lookups.

Everything here is opt-in: with `PREFECT_SERVER_API_GUARD_ENABLED=False`
(the default), `attach_guard` is a no-op and the server behaves exactly as
before. Install the dependency with `uv add fastapi-guard` or
`pip install fastapi-guard` before enabling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import prefect.settings

if TYPE_CHECKING:
    from fastapi import FastAPI
    from guard import SecurityConfig, SecurityMiddleware
    from starlette.types import ASGIApp, Receive, Scope, Send

DEFAULT_EXCLUDED_PATHS = "/docs,/redoc,/openapi.json"


def probe_paths() -> frozenset[str]:
    """The API's health and readiness probes, under the path the API app is
    mounted at (PREFECT_SERVER_API_BASE_PATH, else /api)."""
    base_path = prefect.settings.get_current_settings().server.api.base_path
    base = (base_path or "/api").rstrip("/")
    return frozenset({f"{base}/health", f"{base}/ready"})


# fastapi-guard keeps rate limiting and ban checks active on excluded paths,
# so health and readiness probes would be rate limited (and the client IP
# auto-banned). They skip the guard entirely instead.
class _ProbeBypassGuard:
    """Routes health and readiness probes around the SecurityMiddleware."""

    def __init__(
        self,
        app: ASGIApp,
        guard_middleware: type[SecurityMiddleware],
        config: SecurityConfig,
        probe_paths: frozenset[str],
    ) -> None:
        self._app = app
        self._guarded = guard_middleware(app, config=config)
        self._probe_paths = probe_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"] in self._probe_paths:
            await self._app(scope, receive, send)
        else:
            await self._guarded(scope, receive, send)


def _csv(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def _setting(name: str) -> Any:
    """Read a guard_* field from the server API settings by its short name."""
    api_settings = prefect.settings.get_current_settings().server.api
    return getattr(api_settings, f"guard_{name}")


def _build_guard_config() -> SecurityConfig:
    """Build the SecurityConfig from the PREFECT_SERVER_API_GUARD_* settings."""
    from guard import SecurityConfig

    kwargs: dict[str, Any] = {
        "enable_rate_limiting": True,
        "rate_limit": _setting("rate_limit"),
        "rate_limit_window": _setting("rate_limit_window"),
        "enable_ip_banning": True,
        "auto_ban_threshold": _setting("auto_ban_threshold"),
        "auto_ban_duration": _setting("auto_ban_duration"),
        "enable_penetration_detection": True,
        # Rate-limit violations feed the ban engine rather than only
        # returning 429 (the advertised auto-ban behavior); the threshold
        # and duration come from the guard_auto_ban_* settings.
        "enable_rate_limit_auto_ban": True,
        # Bodies here are data (flow runs, deployment manifests, API
        # payloads), not commands the server executes: signature-scanning
        # them false-positives on ordinary content. URL, query, and header
        # screening stays on.
        "detection_scan_body": False,
        # In-memory state unless a Redis URL is configured: never implicitly
        # depend on a Redis server being reachable. With
        # `prefect server start --workers > 1` each worker is a separate
        # process, so set guard_redis_url to share counters and bans.
        "enable_redis": False,
        "passive_mode": _setting("passive_mode"),
        "blacklist": _csv(_setting("blocked_ips")),
        "blocked_user_agents": list(_csv(_setting("blocked_user_agents"))),
        # Zero-trust by default (guard_trusted_proxies defaults to empty):
        # Prefect servers are often reached from private-network peers, and
        # trusting private-range proxies would let any of them spoof
        # X-Forwarded-For past the blocklist and rate limits. Behind a
        # reverse proxy, set guard_trusted_proxies to the proxy addresses.
        "trusted_proxies": _csv(_setting("trusted_proxies")),
        "trusted_proxy_depth": _setting("trusted_proxy_depth"),
        "exclude_paths": list(
            _csv(_setting("excluded_paths"))
            or [*sorted(probe_paths()), *DEFAULT_EXCLUDED_PATHS.split(",")]
        ),
    }

    if allowed_ips := _csv(_setting("allowed_ips")):
        kwargs["whitelist"] = allowed_ips
    if blocked_countries := _csv(_setting("blocked_countries")):
        kwargs["blocked_countries"] = frozenset(blocked_countries)
    if allowed_countries := _csv(_setting("allowed_countries")):
        kwargs["whitelist_countries"] = frozenset(allowed_countries)
    if cloud_providers := _csv(_setting("block_cloud_providers")):
        kwargs["block_cloud_providers"] = frozenset(cloud_providers)

    if redis_url := _setting("redis_url"):
        kwargs["enable_redis"] = True
        kwargs["redis_url"] = redis_url.get_secret_value()
        kwargs["redis_prefix"] = "prefect_guard:"

    if ipinfo_token := _setting("ipinfo_token"):
        kwargs["ipinfo_token"] = ipinfo_token.get_secret_value()

    return SecurityConfig(**kwargs)


def attach_guard(app: FastAPI) -> None:
    """Attach the fastapi-guard middleware when guard_enabled is set.

    No-op unless the setting is on. Fails loudly when the setting is on but
    the package is missing: a misconfiguration must never silently disable
    security.
    """
    api_settings = prefect.settings.get_current_settings().server.api
    if not api_settings.guard_enabled:
        return
    try:
        from guard import SecurityMiddleware
    except ImportError as exc:
        raise ImportError(
            "PREFECT_SERVER_API_GUARD_ENABLED requires fastapi-guard. "
            "Install it with: uv add fastapi-guard"
        ) from exc

    app.add_middleware(
        _ProbeBypassGuard,
        guard_middleware=SecurityMiddleware,
        config=_build_guard_config(),
        probe_paths=probe_paths(),
    )
