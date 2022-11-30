import os
import signal
import socket
import sys
from unittest.mock import MagicMock, call

import anyio
import anyio.abc
import pytest

from prefect.exceptions import InfrastructureNotAvailable, InfrastructureNotFound
from prefect.infrastructure.process import Process
from prefect.testing.utilities import AsyncMock


@pytest.fixture
def mock_open_process(monkeypatch):
    monkeypatch.setattr("anyio.open_process", AsyncMock())
    anyio.open_process.return_value.terminate = MagicMock()  #  Not an async attribute
    yield anyio.open_process


@pytest.mark.parametrize("stream_output", [True, False])
def test_process_stream_output(capsys, stream_output):
    assert Process(stream_output=stream_output, command=["echo", "hello world"]).run()

    out, err = capsys.readouterr()

    if not stream_output:
        assert err == ""
        assert "hello world" not in out.splitlines()
    else:
        assert "hello world" in out


@pytest.mark.skipif(
    sys.platform == "win32", reason="stderr redirect does not work on Windows"
)
def test_process_streams_stderr(capsys):
    assert Process(
        command=["bash", "-c", ">&2 echo hello world"], stream_output=True
    ).run()

    _, err = capsys.readouterr()
    assert err.strip() == "hello world"


@pytest.mark.skipif(
    sys.platform == "win32", reason="bash calls are not working on Windows"
)
@pytest.mark.parametrize("exit_code", [0, 1, 2])
def test_process_returns_exit_code(exit_code):
    result = Process(command=["bash", "-c", f"exit {exit_code}"]).run()
    assert result.status_code == exit_code
    assert bool(result) is (exit_code == 0)


def test_process_runs_command(tmp_path):
    # Perform a side-effect to demonstrate the command is run
    assert Process(command=["touch", str(tmp_path / "canary")]).run()
    assert (tmp_path / "canary").exists()


def test_process_runs_command_in_working_dir_str(tmpdir, capsys):
    assert Process(
        command=["bash", "-c", "pwd"], stream_output=True, working_dir=str(tmpdir)
    ).run()
    out, _ = capsys.readouterr()
    assert str(tmpdir) in out


def test_process_runs_command_in_working_dir_path(tmp_path, capsys):
    assert Process(
        command=["bash", "-c", "pwd"], stream_output=True, working_dir=tmp_path
    ).run()
    out, _ = capsys.readouterr()
    assert str(tmp_path) in out


def test_process_environment_variables(monkeypatch, mock_open_process):
    monkeypatch.setenv("MYVAR", "VALUE")
    Process(command=["echo", "hello"], stream_output=False).run()
    mock_open_process.assert_awaited_once()
    env = mock_open_process.call_args[1].get("env")
    assert env == {**os.environ, **Process._base_environment(), "MYVAR": "VALUE"}


@pytest.mark.skipif(
    sys.platform == "win32", reason="bash calls are not working on Windows"
)
def test_process_includes_current_env_vars(monkeypatch, capsys):
    monkeypatch.setenv("MYVAR", "VALUE-A")
    assert Process(command=["bash", "-c", "echo $MYVAR"]).run()
    out, _ = capsys.readouterr()
    assert "VALUE-A" in out


@pytest.mark.skipif(
    sys.platform == "win32", reason="bash calls are not working on Windows"
)
def test_process_env_override_current_env_vars(monkeypatch, capsys):
    monkeypatch.setenv("MYVAR", "VALUE-A")
    assert Process(
        command=["bash", "-c", "echo $MYVAR"], env={"MYVAR": "VALUE-B"}
    ).run()
    out, _ = capsys.readouterr()
    assert "VALUE-B" in out


@pytest.mark.skipif(
    sys.platform == "win32", reason="bash calls are not working on Windows"
)
def test_process_env_unset_current_env_vars(monkeypatch, capsys):
    monkeypatch.setenv("MYVAR", "VALUE-A")
    assert Process(command=["bash", "-c", "echo $MYVAR"], env={"MYVAR": None}).run()
    out, _ = capsys.readouterr()
    assert "VALUE-A" not in out


def test_process_created_then_marked_as_started(mock_open_process):
    fake_status = MagicMock(spec=anyio.abc.TaskStatus)
    # By raising an exception when started is called we can assert the process
    # is opened before this time
    fake_status.started.side_effect = RuntimeError("Started called!")

    with pytest.raises(RuntimeError, match="Started called!"):
        Process(command=["echo", "hello"], stream_output=False).run(
            task_status=fake_status
        )

    fake_status.started.assert_called_once()
    mock_open_process.assert_awaited_once()


async def test_process_can_be_run_async():
    result = await Process(command=["echo", "hello"], stream_output=False).run()
    assert result


def test_task_status_receives_infrastructure_pid():
    fake_status = MagicMock(spec=anyio.abc.TaskStatus)
    result = Process(command=["echo", "hello"], stream_output=False).run(
        task_status=fake_status
    )

    hostname = socket.gethostname()
    fake_status.started.assert_called_once_with(f"{hostname}:{result.identifier}")


def test_run_requires_command():
    process = Process(command=[])
    with pytest.raises(ValueError, match="cannot be run with empty command"):
        process.run()


async def test_prepare_for_flow_run_uses_sys_executable(
    deployment,
    orion_client,
):
    flow_run = await orion_client.create_flow_run_from_deployment(deployment.id)
    infrastructure = Process().prepare_for_flow_run(flow_run)
    assert infrastructure.command == [sys.executable, "-m", "prefect.engine"]


@pytest.mark.parametrize(
    "exit_code,help_message",
    [
        (-9, "This indicates that the process exited due to a SIGKILL signal"),
        (
            247,
            "This indicates that the process was terminated due to high memory usage.",
        ),
    ],
)
def test_process_logs_exit_code_help_message(
    exit_code, help_message, caplog, monkeypatch
):

    # We need to use a monkeypatch because `bash -c "exit -9"`` returns a 247
    class fake_process:
        returncode = exit_code
        pid = 0

    mock = AsyncMock(return_value=fake_process)
    monkeypatch.setattr("prefect.infrastructure.process.run_process", mock)

    result = Process(command=["noop"]).run()
    assert result.status_code == exit_code

    record = caplog.records[-1]
    assert record.levelname == "ERROR"
    assert help_message in record.message


async def test_process_kill_mismatching_hostname(monkeypatch):
    os_kill = MagicMock()
    monkeypatch.setattr("os.kill", os_kill)

    infrastructure_pid = f"not-{socket.gethostname()}:12345"

    process = Process(command=["noop"])

    with pytest.raises(InfrastructureNotAvailable):
        await process.kill(infrastructure_pid=infrastructure_pid, grace_seconds=15)

    os_kill.assert_not_called()


async def test_process_kill_no_matching_pid(monkeypatch):
    os_kill = MagicMock(side_effect=ProcessLookupError())
    monkeypatch.setattr("os.kill", os_kill)

    infrastructure_pid = f"{socket.gethostname()}:12345"

    process = Process(command=["noop"])

    with pytest.raises(InfrastructureNotFound):
        await process.kill(infrastructure_pid=infrastructure_pid, grace_seconds=15)


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="SIGTERM/SIGKILL are only used in non-Windows environments",
)
async def test_process_kill_sends_sigterm_then_sigkill(monkeypatch):
    os_kill = MagicMock()
    anyio_sleep = AsyncMock()
    monkeypatch.setattr("os.kill", os_kill)
    monkeypatch.setattr("prefect.infrastructure.process.anyio.sleep", anyio_sleep)

    infrastructure_pid = f"{socket.gethostname()}:12345"
    grace_seconds = 15

    process = Process(command=["noop"])
    await process.kill(
        infrastructure_pid=infrastructure_pid, grace_seconds=grace_seconds
    )

    os_kill.assert_has_calls(
        [
            call(12345, signal.SIGTERM),
            call(12345, signal.SIGKILL),
        ]
    )

    anyio_sleep.assert_called_once_with(grace_seconds)


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="CTRL_BREAK_EVENT is only defined in Windows",
)
async def test_process_kill_windows_sends_ctrl_break(monkeypatch):
    os_kill = MagicMock()
    monkeypatch.setattr("os.kill", os_kill)

    infrastructure_pid = f"{socket.gethostname()}:12345"
    grace_seconds = 15

    process = Process(command=["noop"])
    await process.kill(
        infrastructure_pid=infrastructure_pid, grace_seconds=grace_seconds
    )

    os_kill.assert_called_once_with(12345, signal.CTRL_BREAK_EVENT)
