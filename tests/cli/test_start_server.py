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
async def server_process():
    """
    Runs an instance of the server. Requires a port from 2222-2229 to be available.
    Uses the same database as the rest of the tests.
    Yields:
        The anyio.Process.
    """

    ports = list(range(2222, 2230))

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
            "server",
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
                            await anyio.sleep(0.5)  # extra sleep for less flakiness
                            break
                    await anyio.sleep(0.1)
            if response:
                response.raise_for_status()
            if not response:
                raise RuntimeError(
                    "Timed out while attempting to connect to hosted test server."
                )

        # Yield to the consuming tests
        yield process

        # Then shutdown the process
        try:
            process.terminate()
        except ProcessLookupError:
            pass
        out.close()


@pytest.mark.service("process")
class TestUvicornSignalForwarding:
    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="SIGTERM is only used in non-Windows environments",
    )
    async def test_sigint_sends_sigterm(self, server_process):
        server_process.send_signal(signal.SIGINT)
        with anyio.fail_after(SHUTDOWN_TIMEOUT):
            await server_process.wait()
        server_process.out.seek(0)
        out = server_process.out.read().decode()

        assert "Sending SIGTERM" in out, (
            "When sending a SIGINT, the main process should send a SIGTERM to the"
            f" uvicorn subprocess. Output:\n{out}"
        )

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="SIGTERM is only used in non-Windows environments",
    )
    async def test_sigterm_sends_sigterm_directly(self, server_process):
        server_process.send_signal(signal.SIGTERM)
        with anyio.fail_after(SHUTDOWN_TIMEOUT):
            await server_process.wait()
        server_process.out.seek(0)
        out = server_process.out.read().decode()

        assert "Sending SIGTERM" in out, (
            "When sending a SIGTERM, the main process should send a SIGTERM to the"
            f" uvicorn subprocess. Output:\n{out}"
        )

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="SIGTERM is only used in non-Windows environments",
    )
    async def test_sigint_sends_sigterm_then_sigkill(self, server_process):
        server_process.send_signal(signal.SIGINT)
        await anyio.sleep(0.001)  # some time needed for the recursive signal handler
        server_process.send_signal(signal.SIGINT)
        with anyio.fail_after(SHUTDOWN_TIMEOUT):
            await server_process.wait()
        server_process.out.seek(0)
        out = server_process.out.read().decode()

        assert (
            # either the main PID is still waiting for shutdown, so forwards the SIGKILL
            "Sending SIGKILL" in out
            # or SIGKILL came too late, and the main PID is already closing
            or "KeyboardInterrupt" in out
            or "Server stopped!" in out
        ), (
            "When sending two SIGINT shortly after each other, the main process should"
            " first send a SIGTERM and then a SIGKILL to the uvicorn subprocess."
            f" Output:\n{out}"
        )

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="SIGTERM is only used in non-Windows environments",
    )
    async def test_sigterm_sends_sigterm_then_sigkill(self, server_process):
        server_process.send_signal(signal.SIGTERM)
        await anyio.sleep(0.001)  # some time needed for the recursive signal handler
        server_process.send_signal(signal.SIGTERM)
        with anyio.fail_after(SHUTDOWN_TIMEOUT):
            await server_process.wait()
        server_process.out.seek(0)
        out = server_process.out.read().decode()

        assert (
            # either the main PID is still waiting for shutdown, so forwards the SIGKILL
            "Sending SIGKILL" in out
            # or SIGKILL came too late, and the main PID is already closing
            or "KeyboardInterrupt" in out
            or "Server stopped!" in out
        ), (
            "When sending two SIGTERM shortly after each other, the main process should"
            " first send a SIGTERM and then a SIGKILL to the uvicorn subprocess."
            f" Output:\n{out}"
        )

    @pytest.mark.skipif(
        sys.platform != "win32",
        reason="CTRL_BREAK_EVENT is only defined in Windows",
    )
    async def test_sends_ctrl_break_win32(self, server_process):
        server_process.send_signal(signal.SIGINT)
        with anyio.fail_after(SHUTDOWN_TIMEOUT):
            await server_process.wait()
        server_process.out.seek(0)
        out = server_process.out.read().decode()

        assert "Sending CTRL_BREAK_EVENT" in out, (
            "When sending a SIGINT, the main process should send a CTRL_BREAK_EVENT to"
            f" the uvicorn subprocess. Output:\n{out}"
        )
