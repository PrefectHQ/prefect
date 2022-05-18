import os
import sys

import anyio
import httpx
import pytest

from prefect.settings import PREFECT_API_URL, get_current_settings, temporary_settings


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

    # Will connect to the same database as normal test clients
    process = await anyio.open_process(
        command=[
            "uvicorn",
            "--factory",
            "prefect.orion.api.server:create_app",
            "--host",
            "127.0.0.1",
            "--port",
            "2222",
            "--log-level",
            "info",
        ],
        stdout=sys.stdout,
        stderr=sys.stderr,
        env={**get_current_settings().to_environment_variables(), **os.environ},
    )

    api_url = "http://localhost:2222/api"

    try:
        # Wait for the server to be ready
        async with httpx.AsyncClient() as client:
            response = None
            with anyio.move_on_after(10):
                while True:
                    try:
                        response = await client.get(api_url + "/health")
                    except httpx.ConnectError:
                        pass
                    else:
                        if response.status_code == 200:
                            break
                    await anyio.sleep(0.1)
            if response:
                response.raise_for_status()
            if not response:
                raise RuntimeError(
                    "Timed out while attempting to connect to hosted test Orion."
                )

        # Yield to the consuming tests
        yield api_url

    finally:
        # Cleanup the process
        try:
            process.terminate()
        except Exception:
            pass  # May already be terminated

        await process.aclose()


@pytest.fixture
def use_hosted_orion(hosted_orion_api):
    """
    Sets `PREFECT_API_URL` to the test session's hosted API endpoint.
    """
    with temporary_settings({PREFECT_API_URL: hosted_orion_api}):
        yield hosted_orion_api
