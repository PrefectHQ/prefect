import asyncio
import contextlib
import os
import signal
import socket
import sys
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Callable

import anyio
import httpx
import pytest
import readchar
from anyio.abc import Process

from prefect.cli._server_utils import SERVER_PID_FILE_NAME, _format_host_for_url
from prefect.context import get_settings_context
from prefect.settings import (
    PREFECT_API_DATABASE_CONNECTION_URL,
    PREFECT_API_URL,
    PREFECT_HOME,
    PREFECT_MESSAGING_BROKER,
    PREFECT_MESSAGING_CACHE,
    PREFECT_PROFILES_PATH,
    PREFECT_SERVER_CONCURRENCY_LEASE_STORAGE,
    PREFECT_SERVER_EVENTS_CAUSAL_ORDERING,
    Profile,
    ProfilesCollection,
    get_current_settings,
    load_profiles,
    save_profiles,
    temporary_settings,
)
from prefect.testing.cli import invoke_and_assert
from prefect.testing.fixtures import is_port_in_use
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.utilities.processutils import open_process

POLL_INTERVAL = 0.5
STARTUP_TIMEOUT = 30
SHUTDOWN_TIMEOUT = 20


async def wait_for_server(api_url: str, timeout: float | None = None) -> None:
    timeout = timeout or STARTUP_TIMEOUT
    async with httpx.AsyncClient() as client:
        with anyio.move_on_after(timeout):
            response = None
            while True:
                try:
                    response = await client.get(api_url + "/health")
                except httpx.ConnectError:
                    pass
                else:
                    if response.status_code == 200:
                        await anyio.sleep(1)  # extra sleep for less flakiness
                        break
                await anyio.sleep(POLL_INTERVAL)
        if response:
            response.raise_for_status()
        if not response:
            raise RuntimeError(
                f"Timed out after {timeout}s while attempting to connect to hosted test server at {api_url}."
            )


@contextlib.asynccontextmanager
async def start_server_process(
    host: str = "127.0.0.1",
) -> AsyncIterator[Process]:
    """
    Runs an instance of the server. Requires a port from 2222-2229 to be available.
    Uses the same database as the rest of the tests.

    Args:
        host: The host address to bind the server to. Defaults to 127.0.0.1.

    Yields:
        The anyio Process.
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
            host,
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
        # format IPv6 addresses with brackets for URL
        url_host = f"[{host}]" if ":" in host else host
        api_url = f"http://{url_host}:{port}/api"
        await wait_for_server(api_url)
        yield process

    out.close()


async def fetch_pid(client, api_url):
    r = await client.get(api_url + "/pid")
    return r.json()["pid"]


class TestMultipleWorkerServer:
    def test_number_of_workers(self) -> None:
        """Test that workers parameter is properly validated"""
        invoke_and_assert(
            command=["server", "start", "--workers", "0"],
            expected_output_contains="Number of workers must be >= 1",
            expected_code=1,
        )

    @pytest.mark.parametrize(
        ["connection_url", "expected_output_contains"],
        [
            (
                "sqlite+aiosqlite:///test.db",
                "Multi-worker mode (--workers > 1) is not supported with SQLite database.",
            ),
            (
                "invalid://connection/string",
                "Unable to validate database configuration",
            ),
        ],
    )
    def test_database_validation(
        self, connection_url: str, expected_output_contains: str
    ) -> None:
        """Test database validation"""
        with temporary_settings({PREFECT_API_DATABASE_CONNECTION_URL: connection_url}):
            invoke_and_assert(
                command=["server", "start", "--workers", "2"],
                expected_output_contains=expected_output_contains,
                expected_code=1,
            )

    def test_memory_messaging_cache_not_supported(self):
        """Test that in-memory messaging cache is not supported with multiple workers"""
        with temporary_settings(
            {
                PREFECT_API_DATABASE_CONNECTION_URL: "postgresql+asyncpg://user:pass@localhost:5432/prefect",
                PREFECT_MESSAGING_CACHE: "prefect.server.utilities.messaging.memory",
                PREFECT_MESSAGING_BROKER: "prefect.server.utilities.messaging.memory",
                PREFECT_SERVER_EVENTS_CAUSAL_ORDERING: "prefect.server.events.ordering.memory",
                PREFECT_SERVER_CONCURRENCY_LEASE_STORAGE: "prefect.server.concurrency.lease_storage.memory",
            }
        ):
            invoke_and_assert(
                command=[
                    "server",
                    "start",
                    "--workers",
                    "2",
                    "--no-services",
                ],
                expected_output_contains="Multi-worker mode (--workers > 1) requires Redis for messaging and lease storage.",
                expected_code=1,
            )

    async def test_multi_worker_in_background(
        self,
        unused_tcp_port: int,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Test starting the server with multiple workers in the background."""
        # Patch at the canonical location (for cyclopts, which imports inside
        # the function body) and at the typer module namespace (which captured
        # the reference at import time).
        from unittest.mock import MagicMock

        mock_validate = MagicMock()
        monkeypatch.setattr(
            "prefect.cli._server_utils._validate_multi_worker", mock_validate
        )

        # Disable migrations and block registration to avoid race conditions
        # when multiple workers start concurrently. Each worker would try to
        # run migrations/block registration at the same time, causing database
        # deadlocks and race conditions.
        monkeypatch.setenv("PREFECT_API_DATABASE_MIGRATE_ON_START", "false")
        monkeypatch.setenv("PREFECT_API_BLOCKS_REGISTER_ON_START", "false")

        try:
            await run_sync_in_worker_thread(
                invoke_and_assert,
                command=[
                    "server",
                    "start",
                    "--port",
                    str(unused_tcp_port),
                    "--workers",
                    "2",
                    "--no-services",
                    "--background",
                ],
                expected_output_contains="Starting server with 2 worker processes.",
                expected_code=0,
            )

            api_url = f"http://127.0.0.1:{unused_tcp_port}/api"
            # Multi-worker servers take longer to start, use 60s timeout
            # to reduce flakiness in CI environments
            try:
                await wait_for_server(api_url, timeout=60)
            except RuntimeError as e:
                # If server fails to start, try to get the logs for debugging
                pid_file = PREFECT_HOME.value() / SERVER_PID_FILE_NAME
                if pid_file.exists():
                    raise RuntimeError(
                        f"{e}\nServer PID file exists at {pid_file}, but server is not responding."
                    ) from e
                else:
                    raise RuntimeError(
                        f"{e}\nServer PID file does not exist at {pid_file}. Server may have failed to start."
                    ) from e

            if os.getenv("GITHUB_ACTIONS"):
                await anyio.sleep(
                    5
                )  # Give workers extra time to start up in CI environments

            pids = set()
            for _ in range(10):
                async with httpx.AsyncClient() as client:
                    tasks = [fetch_pid(client, api_url) for _ in range(100)]
                    results = await asyncio.gather(*tasks)

                pids.update(results)
                if len(pids) == 2:
                    break

                await anyio.sleep(1)  # Wait a bit more before retrying

            assert len(pids) == 2, f"Expected 2 worker PIDs but got {len(pids)}: {pids}"
            assert mock_validate.called

        finally:
            await run_sync_in_worker_thread(
                invoke_and_assert,
                command=["server", "stop"],
                expected_output_contains="Server stopped!",
                expected_code=0,
            )


class TestBackgroundServer:
    def test_start_and_stop_background_server(self, unused_tcp_port: int):
        invoke_and_assert(
            command=[
                "server",
                "start",
                "--port",
                str(unused_tcp_port),
                "--background",
            ],
            expected_output_contains="The Prefect server is running in the background.",
            expected_code=0,
        )

        pid_file = PREFECT_HOME.value() / "server.pid"
        assert pid_file.exists(), "Server PID file does not exist"

        invoke_and_assert(
            command=[
                "server",
                "stop",
            ],
            expected_output_contains="Server stopped!",
            expected_code=0,
        )

        assert not (PREFECT_HOME.value() / "server.pid").exists(), (
            "Server PID file exists"
        )

    def test_start_duplicate_background_server(
        self, unused_tcp_port_factory: Callable[[], int]
    ):
        port_1 = unused_tcp_port_factory()
        invoke_and_assert(
            command=[
                "server",
                "start",
                "--port",
                str(port_1),
                "--background",
            ],
            expected_output_contains="The Prefect server is running in the background.",
            expected_code=0,
        )

        port_2 = unused_tcp_port_factory()
        invoke_and_assert(
            command=[
                "server",
                "start",
                "--port",
                str(port_2),
                "--background",
            ],
            expected_output_contains="A server is already running in the background.",
            expected_code=1,
        )

        invoke_and_assert(
            command=[
                "server",
                "stop",
            ],
            expected_output_contains="Server stopped!",
            expected_code=0,
        )

    def test_start_port_in_use(self, unused_tcp_port: int):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", unused_tcp_port))
            invoke_and_assert(
                command=[
                    "server",
                    "start",
                    "--port",
                    str(unused_tcp_port),
                    "--background",
                ],
                expected_output_contains=f"Port {unused_tcp_port} is already in use.",
                expected_code=1,
            )

    def test_start_port_in_use_by_background_server(self, unused_tcp_port: int):
        pid_file = PREFECT_HOME.value() / SERVER_PID_FILE_NAME
        pid_file.write_text("99999")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", unused_tcp_port))

            invoke_and_assert(
                command=[
                    "server",
                    "start",
                    "--port",
                    str(unused_tcp_port),
                    "--background",
                ],
                expected_output_contains=f"A background server process is already running on port {unused_tcp_port}.",
                expected_code=1,
            )

    def test_stop_stale_pid_file(self, unused_tcp_port: int):
        pid_file = PREFECT_HOME.value() / SERVER_PID_FILE_NAME
        pid_file.write_text("99999")

        invoke_and_assert(
            command=[
                "server",
                "stop",
            ],
            expected_output_contains="Cleaning up stale PID file.",
            expected_output_does_not_contain="Server stopped!",
            expected_code=0,
        )

        assert not (PREFECT_HOME.value() / "server.pid").exists(), (
            "Server PID file exists"
        )


@pytest.mark.service("process")
class TestUvicornSignalForwarding:
    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="SIGTERM is only used in non-Windows environments",
    )
    async def test_sigint_shutsdown_cleanly(self):
        async with start_server_process() as server_process:
            server_process.send_signal(signal.SIGINT)
            with anyio.fail_after(SHUTDOWN_TIMEOUT):
                exit_code = await server_process.wait()

            assert exit_code == 0, (
                "After one sigint, the process should exit successfully"
            )

            server_process.out.seek(0)
            out = server_process.out.read().decode()

            assert "Application shutdown complete." in out, (
                "When sending a SIGINT, the application should shutdown cleanly. "
                f"Output:\n{out}"
            )

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="SIGTERM is only used in non-Windows environments",
    )
    async def test_sigterm_shutsdown_cleanly(self):
        async with start_server_process() as server_process:
            server_process.send_signal(signal.SIGTERM)
            with anyio.fail_after(SHUTDOWN_TIMEOUT):
                exit_code = await server_process.wait()

            assert exit_code == -signal.SIGTERM, (
                "After a sigterm, the server process should indicate it was terminated"
            )

            server_process.out.seek(0)
            out = server_process.out.read().decode()

            assert "Application shutdown complete." in out, (
                "When sending a SIGTERM, the application should shutdown cleanly. "
                f"Output:\n{out}"
            )

    @pytest.mark.skipif(
        sys.platform != "win32",
        reason="CTRL_BREAK_EVENT is only defined in Windows",
    )
    async def test_ctrl_break_shutsdown_cleanly(self):
        async with start_server_process() as server_process:
            server_process.send_signal(signal.SIGINT)
            with anyio.fail_after(SHUTDOWN_TIMEOUT):
                exit_code = await server_process.wait()

            assert exit_code == 0, (
                "After a ctrl-break, the process should exit successfully"
            )

            server_process.out.seek(0)
            out = server_process.out.read().decode()

            assert "Sending CTRL_BREAK_EVENT" in out, (
                "When sending a SIGINT, the main process should send a"
                f" CTRL_BREAK_EVENT to the uvicorn subprocess. Output:\n{out}"
            )


@pytest.mark.service("process")
class TestIPv6Support:
    """Tests for IPv6 address support in server start."""

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="SIGTERM is only used in non-Windows environments",
    )
    async def test_server_starts_with_ipv6_host(self):
        """Test that the server can start and respond on an IPv6 address.

        Regression test for https://github.com/PrefectHQ/prefect/issues/20343
        """
        async with start_server_process(host="::1") as server_process:
            server_process.send_signal(signal.SIGTERM)
            with anyio.fail_after(SHUTDOWN_TIMEOUT):
                await server_process.wait()

            server_process.out.seek(0)
            out = server_process.out.read().decode()

            assert "Uvicorn running on" in out, (
                f"Server should have started successfully. Output:\n{out}"
            )
            assert "Invalid host" not in out, (
                f"Server should not reject IPv6 address. Output:\n{out}"
            )


class TestPrestartCheck:
    @pytest.fixture(autouse=True)
    def interactive_console(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr("prefect.cli._app.is_interactive", lambda: True)

        # `readchar` does not like the fake stdin provided by typer isolation so we provide
        # a version that does not require a fd to be attached
        def readchar():
            sys.stdin.flush()
            position = sys.stdin.tell()
            if not sys.stdin.read():
                print("TEST ERROR: CLI is attempting to read input but stdin is empty.")
                raise SystemExit(-2)
            else:
                sys.stdin.seek(position)
            return sys.stdin.read(1)

        monkeypatch.setattr("readchar._posix_read.readchar", readchar)

    @pytest.fixture(autouse=True)
    def temporary_profiles_path(self, tmp_path: Path):
        path = tmp_path / "profiles.toml"
        with temporary_settings({PREFECT_PROFILES_PATH: path}):
            save_profiles(
                profiles=ProfilesCollection(profiles=[get_settings_context().profile])
            )
            yield path

    @pytest.fixture
    def stop_server(self):
        yield
        invoke_and_assert(
            command=[
                "server",
                "stop",
            ],
            expected_output_contains="Server stopped!",
            expected_code=0,
        )

    @pytest.mark.usefixtures("stop_server")
    def test_switch_to_local_profile_by_default(self):
        invoke_and_assert(
            command=[
                "server",
                "start",
                "--background",
            ],
            expected_output_contains="Switched to profile 'local'",
            expected_code=0,
        )

        profiles = load_profiles()
        assert profiles.active_name == "local"

    @pytest.mark.usefixtures("stop_server")
    def test_choose_when_multiple_profiles_have_same_api_url(self):
        save_profiles(
            profiles=ProfilesCollection(
                profiles=[
                    Profile(
                        name="local-server",
                        settings={PREFECT_API_URL: "http://127.0.0.1:4200/api"},
                    ),
                    Profile(
                        name="local",
                        settings={PREFECT_API_URL: "http://127.0.0.1:4200/api"},
                    ),
                    get_settings_context().profile,
                ]
            )
        )

        invoke_and_assert(
            command=[
                "server",
                "start",
                "--background",
            ],
            expected_output_contains="Switched to profile 'local'",
            expected_code=0,
            user_input=readchar.key.ENTER,
        )

        profiles = load_profiles()
        assert profiles.active_name == "local"


class TestHostValidation:
    def test_start_invalid_host(self):
        """Test that providing an invalid host returns a clear error message.

        this is a regression test for https://github.com/PrefectHQ/prefect/issues/16950
        """
        invoke_and_assert(
            command=[
                "server",
                "start",
                "--host",
                "foo",
            ],
            expected_output_contains="Invalid host 'foo'. Please specify a valid hostname or IP address.",
            expected_code=1,
        )

    @pytest.mark.parametrize(
        "host",
        [
            "127.0.0.1",
            "0.0.0.0",
            "::",
            "::1",
        ],
    )
    def test_host_validation_accepts_valid_addresses(
        self, host: str, unused_tcp_port: int
    ):
        """Test that both IPv4 and IPv6 addresses are accepted as valid hosts.

        Regression test for https://github.com/PrefectHQ/prefect/issues/20343
        which reported that IPv6 addresses like '::' were rejected.

        This test verifies the socket binding check works for both address families
        without starting the full server (to avoid unrelated startup issues).
        """
        # this mimics the socket check in src/prefect/cli/server.py
        info = socket.getaddrinfo(
            host, unused_tcp_port, socket.AF_UNSPEC, socket.SOCK_STREAM
        )
        family, socktype, proto, canonname, sockaddr = info[0]
        with socket.socket(family, socktype, proto) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(sockaddr)
        # if we get here without socket.gaierror, the host was accepted


class TestFormatHostForUrl:
    """Tests for _format_host_for_url helper function."""

    @pytest.mark.parametrize(
        "host,expected",
        [
            ("127.0.0.1", "127.0.0.1"),
            ("0.0.0.0", "0.0.0.0"),
            ("::", "[::]"),
            ("::1", "[::1]"),
            ("2001:db8::1", "[2001:db8::1]"),
            ("localhost", "localhost"),
            ("example.com", "example.com"),
        ],
    )
    def test_format_host_for_url(self, host: str, expected: str):
        """Test that IPv6 addresses are wrapped in brackets for URL use.

        Regression test for https://github.com/PrefectHQ/prefect/issues/20343
        """
        assert _format_host_for_url(host) == expected
