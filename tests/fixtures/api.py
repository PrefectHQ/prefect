from typing import Any, AsyncGenerator, Awaitable, Callable, Coroutine, Dict

import httpx
import pytest
from docket import Docket
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from prefect.client.base import app_lifespan_context
from prefect.server.api.server import create_app

Message = Dict[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Dict[str, Any]], Coroutine[None, None, None]]
ASGIApp = Callable[[Dict[str, Any], Receive, Send], Coroutine[None, None, None]]


@pytest.fixture()
def app() -> FastAPI:
    return create_app(ephemeral=True, ignore_cache=True)


@pytest.fixture
def test_client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, Any]:
    """
    Yield a test client for testing the api
    """
    # Manually enter the app's lifespan since ASGITransport doesn't trigger it
    # We need to enter both the parent app's lifespan and the mounted api_app's lifespan
    async with app_lifespan_context(app):
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="https://test/api"
        ) as async_client:
            yield async_client


@pytest.fixture
def sync_client(app: FastAPI) -> TestClient:
    return TestClient(app, base_url="https://test/api")


@pytest.fixture
async def hosted_api_client(use_hosted_api_server) -> AsyncGenerator[AsyncClient, Any]:
    async with httpx.AsyncClient(base_url=use_hosted_api_server) as async_client:
        yield async_client


@pytest.fixture
async def client_with_unprotected_block_api(
    app: ASGIApp,
) -> AsyncGenerator[AsyncClient, Any]:
    """
    Yield a test client for testing the api
    """
    api_version = "0.8.0"
    version_header = {"X-PREFECT-API-VERSION": api_version}
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport, base_url="https://test/api", headers=version_header
    ) as async_client:
        yield async_client


@pytest.fixture
async def client_without_exceptions(app: ASGIApp) -> AsyncGenerator[AsyncClient, Any]:
    """
    Yield a test client that does not raise app exceptions.

    This is useful if you need to test e.g. 500 error responses.
    """
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    async with httpx.AsyncClient(
        transport=transport, base_url="https://test/api"
    ) as async_client:
        yield async_client


@pytest.fixture(autouse=True)
async def clear_docket_fakeredis():
    """
    Clear the shared FakeServer state between tests to prevent state leakage.

    The Docket library uses a shared FakeServer instance for all memory:// URLs,
    which can cause key conflicts between tests if not cleared.
    """
    yield
    # Clear the FakeServer state after each test
    try:
        if hasattr(Docket, "_memory_server"):
            from fakeredis.aioredis import FakeConnection
            from redis.asyncio import ConnectionPool, Redis

            server = Docket._memory_server
            # Create a connection pool and Redis client for the FakeServer
            pool = ConnectionPool(connection_class=FakeConnection, server=server)
            async with Redis(connection_pool=pool) as redis_client:
                await redis_client.flushall()
            await pool.disconnect()
    except (ImportError, AttributeError):
        # docket or fakeredis not available, skip cleanup
        pass
