import os
import subprocess

import anyio
import httpx
import pytest
from httpx import ASGITransport

from prefect.orion.api.server import app
from prefect.utilities.testing import temporary_settings


@pytest.fixture
async def client():
    """
    Yield a test client for testing the orion api
    """

    async with httpx.AsyncClient(app=app, base_url="https://test/api") as async_client:
        yield async_client


@pytest.fixture
async def client_without_exceptions():
    """
    Yield a test client that does not raise app exceptions.

    This is useful if you need to test e.g. 500 error responses.
    """
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    async with httpx.AsyncClient(
        transport=transport, base_url="https://test/api"
    ) as async_client:
        yield async_client


@pytest.fixture(scope="session")
async def hosted_orion_api():
    """
    Runs an instance of the Orion API at a dedicated URL instead of the ephemeral
    application. Requires port 2222 to be available.

    Uses the same database as the rest of the tests.

    If built, the UI will be accessible during tests at http://localhost:2222/.

    Yields:
        The connection string
    """

    env = os.environ.copy()
    # Disable services so tests are not affected
    env["PREFECT_ORION_SERVICES_RUN_IN_APP"] = "False"

    # Will connect to the same database as normal test clients
    async with await anyio.open_process(
        command=[
            "uvicorn",
            "prefect.orion.api.server:app",
            "--host",
            "0.0.0.0",  # required for access across networked docker containers in CI
            "--port",
            "2222",
            "--log-level",
            "error",
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ) as process:

        api_url = "http://localhost:2222/api"

        # Wait for the server to be ready
        async with httpx.AsyncClient() as client:
            attempts = 0
            response = None
            while attempts < 20:  # Wait for 2 seconds maximum
                attempts += 1
                try:
                    response = await client.get(api_url + "/admin/hello")
                except httpx.ConnectError:
                    pass
                else:
                    if response.status_code == 200:
                        break
                await anyio.sleep(0.1)
            if response:
                response.raise_for_status()

        try:
            yield api_url
        finally:
            if not process.returncode:
                process.terminate()


@pytest.fixture
def use_hosted_orion(hosted_orion_api):
    """
    Sets `PREFECT_API_URL` and `prefect.settings.from_env().api_url` to the test session's
    hosted API endpoint.
    """
    with temporary_settings(PREFECT_API_URL=hosted_orion_api):
        yield hosted_orion_api
