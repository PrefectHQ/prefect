import os
import socket
import sys
from contextlib import contextmanager
from typing import Union

import anyio
import httpx
import pendulum
import pytest

from prefect.settings import PREFECT_API_URL, get_current_settings, temporary_settings
from prefect.testing.utilities import AsyncMock
from prefect.utilities.processutils import open_process


@pytest.fixture(autouse=True)
def add_prefect_loggers_to_caplog(caplog):
    import logging

    logger = logging.getLogger("prefect")
    logger.propagate = True

    try:
        yield
    finally:
        logger.propagate = False


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
        env={**os.environ, **get_current_settings().to_environment_variables()},
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
        try:
            process.terminate()
        except ProcessLookupError:
            pass


@pytest.fixture
def use_hosted_orion(hosted_orion_api):
    """
    Sets `PREFECT_API_URL` to the test session's hosted API endpoint.
    """
    with temporary_settings({PREFECT_API_URL: hosted_orion_api}):
        yield hosted_orion_api


@pytest.fixture
def mock_anyio_sleep(monkeypatch):
    """
    Mock sleep used to not actually sleep but to set the current time to now + sleep
    delay seconds while still yielding to other tasks in the event loop.

    Provides "assert_sleeps_for" context manager which asserts a sleep time occured
    within the context while using the actual runtime of the context as a tolerance.
    """
    original_now = pendulum.now
    original_sleep = anyio.sleep
    time_shift = 0.0

    async def callback(delay_in_seconds):
        nonlocal time_shift
        time_shift += float(delay_in_seconds)
        # Preserve yield effects of sleep
        await original_sleep(0)

    def latest_now(*args):
        # Fast-forwards the time by the total sleep time
        return original_now(*args).add(
            # Ensure we retain float precision
            seconds=int(time_shift),
            microseconds=(time_shift - int(time_shift)) * 1000000,
        )

    monkeypatch.setattr("pendulum.now", latest_now)

    sleep = AsyncMock(side_effect=callback)
    monkeypatch.setattr("anyio.sleep", sleep)

    @contextmanager
    def assert_sleeps_for(
        seconds: Union[int, float], extra_tolerance: Union[int, float] = 0
    ):
        """
        Assert that sleep was called for N seconds during the duration of the context.
        The runtime of the code during the context of the duration is used as an
        upper tolerance to account for sleeps that start based on a time. This is less
        brittle than attempting to freeze the current time.

        If an integer is provided, the upper tolerance will be rounded up to the nearest
        integer. If a float is provided, the upper tolerance will be a float.

        An optional extra tolerance may be provided to account for any other issues.
        This will be applied symmetrically.
        """
        run_t0 = original_now().timestamp()
        sleep_t0 = time_shift
        yield
        run_t1 = original_now().timestamp()
        sleep_t1 = time_shift
        runtime = run_t1 - run_t0
        if isinstance(seconds, int):
            # Round tolerance up to the nearest integer if input is an int
            runtime = int(runtime) + 1
        sleeptime = sleep_t1 - sleep_t0
        assert (
            sleeptime - float(extra_tolerance)
            <= seconds
            <= sleeptime + runtime + extra_tolerance
        ), f"Sleep was called for {sleeptime}; expected {seconds} with tolerance of +{runtime + extra_tolerance}, -{extra_tolerance}"

    sleep.assert_sleeps_for = assert_sleeps_for

    return sleep
