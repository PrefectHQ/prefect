"""Tests for the optional fastapi-guard middleware wiring."""

import itertools

import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from prefect.server.api.guard import attach_guard

pytest.importorskip("guard")

from httpx import ASGITransport, AsyncClient

from prefect.settings import (
    PREFECT_SERVER_API_BASE_PATH,
    PREFECT_SERVER_API_GUARD_BLOCKED_IPS,
    PREFECT_SERVER_API_GUARD_ENABLED,
    PREFECT_SERVER_API_GUARD_IPINFO_TOKEN,
    PREFECT_SERVER_API_GUARD_PASSIVE_MODE,
    PREFECT_SERVER_API_GUARD_RATE_LIMIT,
    PREFECT_SERVER_API_GUARD_RATE_LIMIT_WINDOW,
    PREFECT_SERVER_API_GUARD_REDIS_URL,
    Settings,
    get_current_settings,
    temporary_settings,
)

# Rate limiting and ban state in fastapi-guard are process-wide, so every
# test drives its own TEST-NET client IP to stay hermetic.
_IP = itertools.count(1)


def _unique_ip() -> str:
    n = next(_IP)
    return f"198.51.{n // 250}.{(n % 250) + 1}"


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    attach_guard(app)
    return app


async def _get(client_ip):
    transport = ASGITransport(app=_build_app(), client=(client_ip, 50000))
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return (await client.get("/ping")).status_code


async def test_disabled_by_default():
    app = FastAPI()
    attach_guard(app)
    assert len(app.user_middleware) == 0
    client_ip = _unique_ip()
    assert await _get(client_ip) == 200


async def test_blocked_ip_is_rejected(monkeypatch):
    blocked = _unique_ip()
    with temporary_settings(
        {
            PREFECT_SERVER_API_GUARD_ENABLED: True,
            PREFECT_SERVER_API_GUARD_BLOCKED_IPS: blocked,
        }
    ):
        assert await _get(blocked) == 403


async def test_rate_limit_returns_429(monkeypatch):
    client_ip = _unique_ip()
    with temporary_settings(
        {
            PREFECT_SERVER_API_GUARD_ENABLED: True,
            PREFECT_SERVER_API_GUARD_RATE_LIMIT: 2,
            PREFECT_SERVER_API_GUARD_RATE_LIMIT_WINDOW: 60,
        }
    ):
        assert await _get(client_ip) == 200
        assert await _get(client_ip) == 200
        assert await _get(client_ip) == 429


async def test_passive_mode_never_blocks(monkeypatch):
    blocked = _unique_ip()
    with temporary_settings(
        {
            PREFECT_SERVER_API_GUARD_ENABLED: True,
            PREFECT_SERVER_API_GUARD_PASSIVE_MODE: True,
            PREFECT_SERVER_API_GUARD_BLOCKED_IPS: blocked,
        }
    ):
        assert await _get(blocked) == 200


async def test_redis_stays_off_without_config():
    with temporary_settings({PREFECT_SERVER_API_GUARD_ENABLED: True}):
        from prefect.server.api.guard import _build_guard_config

        config = _build_guard_config()
        assert config.enable_redis is False


async def test_zero_trust_proxy_default():
    """No proxy is trusted unless explicitly configured.

    Prefect servers are often reached from private-network peers, and
    trusting private-range proxies would let any of them spoof
    X-Forwarded-For past the blocklist and rate limits.
    """
    from prefect.settings import PREFECT_SERVER_API_GUARD_TRUSTED_PROXIES

    with temporary_settings({PREFECT_SERVER_API_GUARD_ENABLED: True}):
        from prefect.server.api.guard import _build_guard_config

        config = _build_guard_config()
        assert config.trusted_proxies == ()
        # Bodies here are data (flow runs, deployment manifests):
        # signature-scanning them would false-positive on ordinary
        # content, so it stays off; URL/query/header screening is on.
        assert config.detection_scan_body is False
        # Rate-limit violations feed the ban engine (the advertised
        # auto-ban behavior).
        assert config.enable_rate_limit_auto_ban is True

    with temporary_settings(
        {
            PREFECT_SERVER_API_GUARD_ENABLED: True,
            PREFECT_SERVER_API_GUARD_TRUSTED_PROXIES: "10.0.0.1,10.0.0.2",
        }
    ):
        from prefect.server.api.guard import _build_guard_config

        config = _build_guard_config()
        assert config.trusted_proxies == ("10.0.0.1", "10.0.0.2")


def test_settings_fields_exist():
    api_settings = get_current_settings().server.api
    for name in (
        "guard_enabled",
        "guard_rate_limit",
        "guard_rate_limit_window",
        "guard_auto_ban_threshold",
        "guard_auto_ban_duration",
        "guard_passive_mode",
    ):
        assert hasattr(api_settings, name)


@pytest.mark.parametrize(
    ("base_path", "probe_path"),
    [
        (None, "/api/health"),
        (None, "/api/ready"),
        ("/v2/api", "/v2/api/health"),
        ("/v2/api/", "/v2/api/ready"),
    ],
)
async def test_health_probes_are_never_rate_limited_or_banned(base_path, probe_path):
    client_ip = _unique_ip()
    app = FastAPI()

    @app.get(probe_path)
    async def probe():
        return {"ok": True}

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    with temporary_settings(
        {
            PREFECT_SERVER_API_BASE_PATH: base_path,
            PREFECT_SERVER_API_GUARD_ENABLED: True,
            PREFECT_SERVER_API_GUARD_RATE_LIMIT: 2,
            PREFECT_SERVER_API_GUARD_RATE_LIMIT_WINDOW: 60,
        }
    ):
        attach_guard(app)
        transport = ASGITransport(app=app, client=(client_ip, 50000))
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            statuses = [(await client.get(probe_path)).status_code for _ in range(30)]
            assert statuses == [200] * 30
            # Probe traffic must not have consumed or banned the client either.
            assert (await client.get("/ping")).status_code == 200


def test_guard_env_vars_load_without_validation_aliases(monkeypatch):
    monkeypatch.setenv("PREFECT_SERVER_API_GUARD_RATE_LIMIT", "7")
    monkeypatch.setenv("PREFECT_SERVER_API_GUARD_ENABLED", "true")
    api_settings = Settings().server.api
    assert api_settings.guard_rate_limit == 7
    assert api_settings.guard_enabled is True


def test_redis_url_and_ipinfo_token_are_secret_and_reach_the_guard():
    redis_url = "redis://:hunter2@127.0.0.1:6538/9"
    with temporary_settings(
        {
            PREFECT_SERVER_API_GUARD_ENABLED: True,
            PREFECT_SERVER_API_GUARD_REDIS_URL: redis_url,
            PREFECT_SERVER_API_GUARD_IPINFO_TOKEN: "tok-123",
        }
    ):
        api_settings = get_current_settings().server.api
        assert isinstance(api_settings.guard_redis_url, SecretStr)
        assert isinstance(api_settings.guard_ipinfo_token, SecretStr)
        dumped = str(get_current_settings().model_dump())
        assert "hunter2" not in dumped
        assert "tok-123" not in dumped

        from prefect.server.api.guard import _build_guard_config

        config = _build_guard_config()
        assert config.redis_url == redis_url
        assert config.ipinfo_token == "tok-123"
