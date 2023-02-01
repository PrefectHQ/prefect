import os
import signal
import sys
import tempfile

import anyio
import httpx
import pytest

from prefect.settings import get_current_settings
from prefect.testing.fixtures import is_port_in_use
from prefect.utilities.processutils import open_process

STARTUP_TIMEOUT = 20
SHUTDOWN_TIMEOUT = 20


@pytest.fixture(scope="function")
async def orion_process():
    """
    Runs an instance of the Orion server. Requires a port from 2222-2227 to be available.
    Uses the same database as the rest of the tests.
    Yields:
        The anyio.Process.
    """

    ports = [2222 + i for i in range(5)]

    while True:
        try:
            port = ports.pop()
        except IndexError as exc:
            raise RuntimeError("No ports available to run test API.") from exc

        if not is_port_in_use(port):
            break

    out = tempfile.TemporaryFile()  # capture output for test assertions

    # Will connect to the same database as normal test clients
    async with open_process(
        command=[
            "prefect",
            "orion",
            "start",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "INFO",
        ],
        stdout=out,
        stderr=out,
        env={**os.environ, **get_current_settings().to_environment_variables()},
    ) as process:
        process.out = out
        api_url = f"http://localhost:{port}/api"

        # Wait for the server to be ready
        async with httpx.AsyncClient() as client:
            response = None
            with anyio.move_on_after(STARTUP_TIMEOUT):
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
        yield process

        # Then shutdown the process
        try:
            process.terminate()
        except ProcessLookupError:
            pass
        out.close()


class TestUvicornSignalForwarding:
    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="SIGTERM is only used in non-Windows environments",
    )
    async def test_sigint_sends_sigterm_then_sigkill(self, orion_process):
        orion_process.send_signal(signal.SIGINT)
        await anyio.sleep(0.001)
        orion_process.send_signal(signal.SIGINT)
        with anyio.fail_after(SHUTDOWN_TIMEOUT):
            await orion_process.wait()
        orion_process.out.seek(0)
        out = orion_process.out.read().decode()

        if "KeyboardInterrupt" in out:
            pass  # SIGKILL came too late, main PID already closing
        else:
            first = out.index("Sending SIGTERM")
            second = out.index("Sending SIGKILL")
            assert (
                first < second
            ), f"When sending two SIGINT shortly after each other, the main process should first send a SIGTERM and then a SIGKILL to the uvicorn subprocess. Output:{out}"

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="SIGTERM is only used in non-Windows environments",
    )
    async def test_sigterm_sends_sigterm_then_sigkill(self, orion_process):
        orion_process.send_signal(signal.SIGTERM)
        await anyio.sleep(0.001)
        orion_process.send_signal(signal.SIGTERM)
        with anyio.fail_after(SHUTDOWN_TIMEOUT):
            await orion_process.wait()
        orion_process.out.seek(0)
        out = orion_process.out.read().decode()

        if "KeyboardInterrupt" in out:
            pass  # SIGKILL came too late, main PID already closing
        else:
            first = out.index("Sending SIGTERM")
            second = out.index("Sending SIGKILL")
            assert (
                first < second
            ), f"When sending two SIGTERM shortly after each other, the main process should first send a SIGTERM and then a SIGKILL to the uvicorn subprocess. Output:{out}"

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="SIGTERM is only used in non-Windows environments",
    )
    async def test_sigterm_sends_sigterm_directly(self, orion_process):
        orion_process.send_signal(signal.SIGTERM)
        with anyio.fail_after(SHUTDOWN_TIMEOUT):
            await orion_process.wait()
        orion_process.out.seek(0)
        out = orion_process.out.read().decode()

        assert (
            "Sending SIGTERM" in out
        ), f"When sending a SIGTERM, the main process should send a SIGTERM to the uvicorn subprocess. Output:{out}"

    @pytest.mark.skipif(
        sys.platform != "win32",
        reason="CTRL_BREAK_EVENT is only defined in Windows",
    )
    async def test_sends_ctrl_break_win32(self, orion_process):
        orion_process.send_signal(signal.SIGINT)
        with anyio.fail_after(SHUTDOWN_TIMEOUT):
            await orion_process.wait()
        orion_process.out.seek(0)
        out = orion_process.out.read().decode()

        assert (
            "Sending CTRL_BREAK_EVENT" in out
        ), f"When sending a SIGINT, the main process should send a CTRL_BREAK_EVENT to the uvicorn subprocess. Output:{out}"
