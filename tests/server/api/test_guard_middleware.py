"""Tests for the optional fastapi-guard middleware wiring."""

import itertools

import pytest
from fastapi import FastAPI

from prefect.server.api.guard import attach_guard

pytest.importorskip("guard")

from httpx import ASGITransport, AsyncClient

from prefect.settings import (
    PREFECT_SERVER_API_GUARD_BLOCKED_IPS,
    PREFECT_SERVER_API_GUARD_ENABLED,
    PREFECT_SERVER_API_GUARD_PASSIVE_MODE,
    PREFECT_SERVER_API_GUARD_RATE_LIMIT,
    PREFECT_SERVER_API_GUARD_RATE_LIMIT_WINDOW,
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
