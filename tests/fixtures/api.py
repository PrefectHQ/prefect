from typing import Any, AsyncGenerator, Awaitable, Callable, Coroutine, Dict

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from prefect.server.api.server import create_app

Message = Dict[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Dict[str, Any]], Coroutine[None, None, None]]
ASGIApp = Callable[[Dict[str, Any], Receive, Send], Coroutine[None, None, None]]


@pytest.fixture()
def app() -> FastAPI:
    return create_app(ephemeral=True)


@pytest.fixture
async def client(app: ASGIApp) -> AsyncGenerator[AsyncClient, Any]:
    """
    Yield a test client for testing the api
    """
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="https://test/api"
    ) as async_client:
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
