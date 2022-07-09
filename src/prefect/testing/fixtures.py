import os
import socket
import sys

import anyio
import httpx
import pytest

from prefect.settings import PREFECT_API_URL, get_current_settings, temporary_settings
from prefect.utilities.processutils import open_process


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


@pytest.fixture(scope="session")
async def hosted_orion_api():
    """
    Runs an instance of the Orion API at a dedicated URL instead of the ephemeral
    application. Requires a port from 2222-2227 to be available.

    Uses the same database as the rest of the tests.

    Yields:
        The connection string
    """

    ports = [2222 + i for i in range(5)]

    while True:
        try:
            port = ports.pop()
        except IndexError as exc:
            raise RuntimeError("No ports available to run test API.") from exc

        if not is_port_in_use(port):
            break

    # Will connect to the same database as normal test clients
    async with open_process(
        command=[
            "uvicorn",
            "--factory",
            "prefect.orion.api.server:create_app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "info",
        ],
        stdout=sys.stdout,
        stderr=sys.stderr,
        env={**get_current_settings().to_environment_variables(), **os.environ},
    ) as process:

        api_url = f"http://localhost:{port}/api"

        # Wait for the server to be ready
        async with httpx.AsyncClient() as client:
            response = None
            with anyio.move_on_after(20):
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

        # Then shutdown the process
        process.terminate()


@pytest.fixture
def use_hosted_orion(hosted_orion_api):
    """
    Sets `PREFECT_API_URL` to the test session's hosted API endpoint.
    """
    with temporary_settings({PREFECT_API_URL: hosted_orion_api}):
        yield hosted_orion_api
