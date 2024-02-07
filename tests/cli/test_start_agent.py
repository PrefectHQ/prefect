import os
import signal
import sys
import tempfile

import anyio
import pytest

import prefect.server.models as models
import prefect.server.schemas as schemas
from prefect.settings import get_current_settings
from prefect.utilities.processutils import open_process

POLL_INTERVAL = 0.5
STARTUP_TIMEOUT = 20
SHUTDOWN_TIMEOUT = 5


async def safe_shutdown(process):
    try:
        with anyio.fail_after(SHUTDOWN_TIMEOUT):
            await process.wait()
    except TimeoutError:
        # try twice in case process.wait() hangs
        with anyio.fail_after(SHUTDOWN_TIMEOUT):
            await process.wait()


@pytest.fixture(autouse=True)
async def ensure_default_agent_pool_exists(session):
    # The default agent work pool is created by a migration, but is cleared on
    # consecutive test runs. This fixture ensures that the default agent work
    # pool exists before each test.
    default_work_pool = await models.workers.read_work_pool_by_name(
        session=session, work_pool_name=models.workers.DEFAULT_AGENT_WORK_POOL_NAME
    )
    if default_work_pool is None:
        await models.workers.create_work_pool(
            session=session,
            work_pool=schemas.actions.WorkPoolCreate(
                name=models.workers.DEFAULT_AGENT_WORK_POOL_NAME, type="prefect-agent"
            ),
        )
        await session.commit()


@pytest.fixture(scope="function")
async def agent_process(use_hosted_api_server):
    """
    Runs an agent listening to all queues.
    Yields:
        The anyio.Process.
    """
    out = tempfile.TemporaryFile()  # capture output for test assertions

    # Will connect to the same database as normal test clients
    async with open_process(
        command=[
            "prefect",
            "agent",
            "start",
            "--match=nonexist",
        ],
        stdout=out,
        stderr=out,
        env={**os.environ, **get_current_settings().to_environment_variables()},
    ) as process:
        process.out = out

        for _ in range(int(STARTUP_TIMEOUT / POLL_INTERVAL)):
            await anyio.sleep(POLL_INTERVAL)
            if out.tell() > 400:
                # Sleep to allow startup to complete
                # TODO: Replace with a healthcheck endpoint
                await anyio.sleep(4)
                break

        assert out.tell() > 400, "The agent did not start up in time"
        assert process.returncode is None, "The agent failed to start up"

        # Yield to the consuming tests
        yield process

        # Then shutdown the process
        try:
            process.terminate()
        except ProcessLookupError:
            pass
        out.close()


class TestAgentSignalForwarding:
    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="SIGTERM is only used in non-Windows environments",
    )
    async def test_sigint_sends_sigterm(self, agent_process):
        agent_process.send_signal(signal.SIGINT)
        await safe_shutdown(agent_process)
        agent_process.out.seek(0)
        out = agent_process.out.read().decode()

        assert "Sending SIGINT" in out, (
            "When sending a SIGINT, the main process should receive a SIGINT."
            f" Output:\n{out}"
        )
        assert "Agent stopped!" in out, (
            "When sending a SIGINT, the main process should shutdown gracefully."
            f" Output:\n{out}"
        )

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="SIGTERM is only used in non-Windows environments",
    )
    async def test_sigterm_sends_sigterm_directly(self, agent_process):
        agent_process.send_signal(signal.SIGTERM)
        await safe_shutdown(agent_process)
        agent_process.out.seek(0)
        out = agent_process.out.read().decode()

        assert "Sending SIGINT" in out, (
            "When sending a SIGTERM, the main process should receive a SIGINT."
            f" Output:\n{out}"
        )
        assert "Agent stopped!" in out, (
            "When sending a SIGTERM, the main process should shutdown gracefully."
            f" Output:\n{out}"
        )

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="SIGTERM is only used in non-Windows environments",
    )
    async def test_sigint_sends_sigterm_then_sigkill(self, agent_process):
        agent_process.send_signal(signal.SIGINT)
        await anyio.sleep(0.01)  # some time needed for the recursive signal handler
        agent_process.send_signal(signal.SIGINT)
        await safe_shutdown(agent_process)
        agent_process.out.seek(0)
        out = agent_process.out.read().decode()

        assert (
            # either the main PID is still waiting for shutdown, so forwards the SIGKILL
            "Sending SIGKILL" in out
            # or SIGKILL came too late, and the main PID is already closing
            or "KeyboardInterrupt" in out
            or "Agent stopped!" in out
            or "Aborted." in out
        ), (
            "When sending two SIGINT shortly after each other, the main process should"
            f" first receive a SIGINT and then a SIGKILL. Output:\n{out}"
        )

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="SIGTERM is only used in non-Windows environments",
    )
    async def test_sigterm_sends_sigterm_then_sigkill(self, agent_process):
        agent_process.send_signal(signal.SIGTERM)
        await anyio.sleep(0.01)  # some time needed for the recursive signal handler
        agent_process.send_signal(signal.SIGTERM)
        await safe_shutdown(agent_process)
        agent_process.out.seek(0)
        out = agent_process.out.read().decode()

        assert (
            # either the main PID is still waiting for shutdown, so forwards the SIGKILL
            "Sending SIGKILL" in out
            # or SIGKILL came too late, and the main PID is already closing
            or "KeyboardInterrupt" in out
            or "Agent stopped!" in out
            or "Aborted." in out
        ), (
            "When sending two SIGTERM shortly after each other, the main process should"
            f" first receive a SIGINT and then a SIGKILL. Output:\n{out}"
        )

    @pytest.mark.skipif(
        sys.platform != "win32",
        reason="CTRL_BREAK_EVENT is only defined in Windows",
    )
    async def test_sends_ctrl_break_win32(self, agent_process):
        agent_process.send_signal(signal.SIGINT)
        await safe_shutdown(agent_process)
        agent_process.out.seek(0)
        out = agent_process.out.read().decode()

        assert "Sending CTRL_BREAK_EVENT" in out, (
            "When sending a SIGINT, the main process should send a CTRL_BREAK_EVENT to"
            f" the uvicorn subprocess. Output:\n{out}"
        )
