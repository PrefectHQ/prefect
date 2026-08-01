import asyncio
import os
import sys
import tempfile
import threading
from pathlib import Path

import prefect_sandbox.sbx as sbx_module
import pytest
from prefect_sandbox import (
    SandboxCreationError,
    SandboxError,
    SandboxExecutionError,
    SandboxFileWriter,
    SandboxHandle,
    SandboxHandleError,
    SandboxUnavailableError,
    SbxSandbox,
)
from prefect_sandbox.sbx import _CommandResult


@pytest.fixture
def backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SbxSandbox:
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    monkeypatch.setattr(SbxSandbox, "_check_binary", lambda self: None)
    return SbxSandbox()


def activate(
    backend: SbxSandbox, sandbox_id: str = "prefect-sandbox-test"
) -> SandboxHandle:
    workspace = Path(tempfile.gettempdir()) / f"prefect-sandbox-{sandbox_id}"
    workspace.mkdir()
    backend._sandboxes[sandbox_id] = workspace
    return SandboxHandle(sandbox_id)


def command_result(
    exit_code: int = 0,
    stdout: bytes = b"",
    stderr: bytes = b"",
    truncated: bool = False,
) -> _CommandResult:
    return _CommandResult(exit_code, stdout, stderr, truncated)


def test_sbx_exposes_file_writer_capability() -> None:
    assert isinstance(SbxSandbox(), SandboxFileWriter)


async def test_missing_binary_fails_before_creating_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    monkeypatch.setattr("prefect_sandbox.sbx.shutil.which", lambda _: None)

    with pytest.raises(SandboxUnavailableError, match="not found"):
        await SbxSandbox().create()

    assert list(tmp_path.iterdir()) == []


async def test_cancelling_workspace_creation_removes_the_completed_directory(
    backend: SbxSandbox,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "prefect-sandbox-slow"
    started = threading.Event()
    release = threading.Event()
    cli_calls: list[list[str]] = []

    def slow_mkdtemp(*, prefix: str) -> str:
        assert prefix == sbx_module._WORKSPACE_PREFIX
        workspace.mkdir()
        started.set()
        if not release.wait(5):
            raise RuntimeError("test did not release workspace creation")
        return str(workspace)

    async def run_cli(self, args, *, timeout, max_output_bytes):
        cli_calls.append(list(args))
        return command_result()

    monkeypatch.setattr(sbx_module.tempfile, "mkdtemp", slow_mkdtemp)
    monkeypatch.setattr(SbxSandbox, "_run_cli", run_cli)
    creating = asyncio.create_task(backend.create())
    try:
        assert await asyncio.to_thread(started.wait, 2)
        creating.cancel()
        await asyncio.sleep(0)
        assert not creating.done()
    finally:
        release.set()

    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(creating, 5)
    assert not workspace.exists()
    assert cli_calls == []


async def test_create_uses_an_empty_workspace_and_provider_options(
    backend: SbxSandbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []

    async def run_cli(self, args, *, timeout, max_output_bytes):
        calls.append(list(args))
        return command_result()

    monkeypatch.setattr(SbxSandbox, "_run_cli", run_cli)
    backend.image = "python:3.13-slim"
    backend.memory = "4g"
    backend.cpus = 2

    handle = await backend.create()
    workspace = backend._sandboxes[handle.id]

    assert workspace is not None
    assert workspace.is_dir()
    assert list(workspace.iterdir()) == []
    assert calls == [
        [
            "create",
            "--quiet",
            "--name",
            handle.id,
            "--memory",
            "4g",
            "--cpus",
            "2",
            "--template",
            "python:3.13-slim",
            "shell",
            str(workspace),
        ]
    ]


async def test_failed_create_removes_provider_and_workspace(
    backend: SbxSandbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    workspace: Path | None = None

    async def run_cli(self, args, *, timeout, max_output_bytes):
        nonlocal workspace
        calls.append(list(args))
        if args[0] == "create":
            workspace = Path(args[-1])
            return command_result(1, stderr=b"provisioning failed")
        return command_result()

    monkeypatch.setattr(SbxSandbox, "_run_cli", run_cli)

    with pytest.raises(SandboxCreationError, match="provisioning failed"):
        await backend.create()

    assert workspace is not None
    assert not workspace.exists()
    assert [call[0] for call in calls] == ["create", "rm"]


async def test_create_timeout_is_typed_and_cleaned_up(
    backend: SbxSandbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace: Path | None = None

    async def run_cli(self, args, *, timeout, max_output_bytes):
        nonlocal workspace
        if args[0] == "create":
            workspace = Path(args[-1])
            raise asyncio.TimeoutError
        return command_result()

    monkeypatch.setattr(SbxSandbox, "_run_cli", run_cli)

    with pytest.raises(SandboxCreationError, match="exceeded"):
        await backend.create()

    assert workspace is not None
    assert not workspace.exists()


async def test_create_surfaces_cleanup_failure(
    backend: SbxSandbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    sandbox_id: str | None = None

    async def run_cli(self, args, *, timeout, max_output_bytes):
        nonlocal sandbox_id
        if args[0] == "create":
            sandbox_id = args[3]
            return command_result(1, stderr=b"create failed")
        if args[0] == "rm":
            return command_result(1, stderr=b"remove failed")
        return command_result(stdout=f"{sandbox_id}\n".encode())

    monkeypatch.setattr(SbxSandbox, "_run_cli", run_cli)

    with pytest.raises(SandboxCreationError, match="cleanup could not be confirmed"):
        await backend.create()


async def test_exec_preserves_argv_and_forwards_only_explicit_environment(
    backend: SbxSandbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    sandbox = activate(backend)
    calls: list[list[str]] = []

    async def run_cli(self, args, *, timeout, max_output_bytes):
        calls.append(list(args))
        return command_result(7, b"out", b"err")

    monkeypatch.setattr(SbxSandbox, "_run_cli", run_cli)
    monkeypatch.setenv("PREFECT_API_KEY", "host-secret")

    result = await backend.exec(
        sandbox,
        ["python", "-c", "print('argument with spaces')"],
        env={"EXPLICIT": "yes"},
        timeout=12,
        max_output_bytes=123,
    )

    assert calls == [
        [
            "exec",
            "--env",
            "EXPLICIT=yes",
            sandbox.id,
            "python",
            "-c",
            "print('argument with spaces')",
        ]
    ]
    assert "host-secret" not in " ".join(calls[0])
    assert result.exit_code == 7
    assert result.stdout == b"out"
    assert result.stderr == b"err"


@pytest.mark.parametrize(
    ("command", "env", "timeout", "max_output_bytes", "error", "message"),
    [
        ("echo hi", None, None, 1, TypeError, "argv sequence"),
        ([], None, None, 1, ValueError, "must not be empty"),
        (["echo", 1], None, None, 1, TypeError, "must be a string"),
        (
            ["echo"],
            {"BAD=NAME": "value"},
            None,
            1,
            ValueError,
            "invalid environment",
        ),
        (["echo"], {"NAME": 1}, None, 1, TypeError, "must be a string"),
        (["echo"], None, 0, 1, ValueError, "positive, finite"),
        (["echo"], None, float("inf"), 1, ValueError, "positive, finite"),
        (["echo"], None, None, 0, ValueError, "positive integer"),
    ],
)
async def test_exec_validates_portable_arguments(
    backend: SbxSandbox,
    command,
    env,
    timeout,
    max_output_bytes,
    error,
    message,
) -> None:
    sandbox = activate(backend)

    with pytest.raises(error, match=message):
        await backend.exec(
            sandbox,
            command,
            env=env,
            timeout=timeout,
            max_output_bytes=max_output_bytes,
        )


async def test_exec_rejects_unknown_and_destroyed_handles(
    backend: SbxSandbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def run_cli(self, args, *, timeout, max_output_bytes):
        return command_result()

    monkeypatch.setattr(SbxSandbox, "_run_cli", run_cli)

    with pytest.raises(SandboxHandleError, match="not created"):
        await backend.exec(SandboxHandle("forged"), ["true"])

    sandbox = activate(backend)
    await backend.destroy(sandbox)
    with pytest.raises(SandboxHandleError, match="destroyed"):
        await backend.exec(sandbox, ["true"])


async def test_exec_timeout_destroys_sandbox_and_returns_distinct_status(
    backend: SbxSandbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    sandbox = activate(backend)

    async def run_cli(self, args, *, timeout, max_output_bytes):
        if args[0] == "exec":
            raise asyncio.TimeoutError
        return command_result()

    monkeypatch.setattr(SbxSandbox, "_run_cli", run_cli)

    result = await backend.exec(sandbox, ["sleep", "60"], timeout=0.1)

    assert result.timed_out
    assert result.exit_code == -1
    assert not result.ok
    assert backend._sandboxes[sandbox.id] is None


async def test_exec_timeout_surfaces_destroy_failure(
    backend: SbxSandbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    sandbox = activate(backend)

    async def run_cli(self, args, *, timeout, max_output_bytes):
        if args[0] == "exec":
            raise asyncio.TimeoutError
        if args[0] == "rm":
            return command_result(1, stderr=b"remove failed")
        return command_result(stdout=f"{sandbox.id}\n".encode())

    monkeypatch.setattr(SbxSandbox, "_run_cli", run_cli)

    with pytest.raises(SandboxExecutionError, match="could not be confirmed"):
        await backend.exec(sandbox, ["sleep", "60"], timeout=0.1)


async def test_cancelling_exec_destroys_sandbox(
    backend: SbxSandbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    sandbox = activate(backend)
    started = asyncio.Event()

    async def run_cli(self, args, *, timeout, max_output_bytes):
        if args[0] == "exec":
            started.set()
            await asyncio.Event().wait()
        return command_result()

    monkeypatch.setattr(SbxSandbox, "_run_cli", run_cli)
    task = asyncio.create_task(backend.exec(sandbox, ["sleep", "60"]))
    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert backend._sandboxes[sandbox.id] is None


async def test_exec_strips_provider_autostart_notice(
    backend: SbxSandbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    sandbox = activate(backend)

    async def run_cli(self, args, *, timeout, max_output_bytes):
        return command_result(
            stderr=f"Sandbox {sandbox.id} started successfully\ncommand warning\n".encode()
        )

    monkeypatch.setattr(SbxSandbox, "_run_cli", run_cli)

    result = await backend.exec(sandbox, ["true"])

    assert result.stderr == b"command warning\n"


async def test_destroy_is_idempotent(
    backend: SbxSandbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    sandbox = activate(backend)
    calls: list[list[str]] = []

    async def run_cli(self, args, *, timeout, max_output_bytes):
        calls.append(list(args))
        return command_result()

    monkeypatch.setattr(SbxSandbox, "_run_cli", run_cli)

    await backend.destroy(sandbox)
    await backend.destroy(sandbox)

    assert [call[0] for call in calls] == ["rm"]
    assert backend._sandboxes[sandbox.id] is None


async def test_concurrent_destroy_calls_share_cleanup(
    backend: SbxSandbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    sandbox = activate(backend)
    started = asyncio.Event()
    finish = asyncio.Event()
    remove_calls = 0

    async def run_cli(self, args, *, timeout, max_output_bytes):
        nonlocal remove_calls
        if args[0] == "rm":
            remove_calls += 1
            started.set()
            await finish.wait()
        return command_result()

    monkeypatch.setattr(SbxSandbox, "_run_cli", run_cli)
    first = asyncio.create_task(backend.destroy(sandbox))
    await started.wait()
    second = asyncio.create_task(backend.destroy(sandbox))
    finish.set()
    await asyncio.gather(first, second)

    assert remove_calls == 1


async def test_cancelled_destroy_finishes_cleanup_before_cancellation(
    backend: SbxSandbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    sandbox = activate(backend)
    started = asyncio.Event()
    finish = asyncio.Event()

    async def run_cli(self, args, *, timeout, max_output_bytes):
        if args[0] == "rm":
            started.set()
            await finish.wait()
        return command_result()

    monkeypatch.setattr(SbxSandbox, "_run_cli", run_cli)
    task = asyncio.create_task(backend.destroy(sandbox))
    await started.wait()
    task.cancel()

    await asyncio.sleep(0)
    assert not task.done()
    finish.set()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert backend._sandboxes[sandbox.id] is None
    assert sandbox.id not in backend._destroy_tasks


async def test_destroy_accepts_provider_already_absent(
    backend: SbxSandbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    sandbox = activate(backend)

    async def run_cli(self, args, *, timeout, max_output_bytes):
        if args[0] == "rm":
            return command_result(1, stderr=b"not found")
        return command_result(stdout=b"another-sandbox\n")

    monkeypatch.setattr(SbxSandbox, "_run_cli", run_cli)

    await backend.destroy(sandbox)

    assert backend._sandboxes[sandbox.id] is None


async def test_destroy_failure_keeps_handle_retryable(
    backend: SbxSandbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    sandbox = activate(backend)
    workspace = backend._sandboxes[sandbox.id]

    async def run_cli(self, args, *, timeout, max_output_bytes):
        if args[0] == "rm":
            return command_result(1, stderr=b"remove failed")
        return command_result(stdout=f"{sandbox.id}\n".encode())

    monkeypatch.setattr(SbxSandbox, "_run_cli", run_cli)

    with pytest.raises(SandboxError, match="may still be running"):
        await backend.destroy(sandbox)

    assert backend._sandboxes[sandbox.id] == workspace
    assert workspace is not None and not workspace.exists()


async def test_write_file_uses_native_copy_and_removes_staging_file(
    backend: SbxSandbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    sandbox = activate(backend)
    calls: list[list[str]] = []
    staged_path: Path | None = None

    async def run_cli(self, args, *, timeout, max_output_bytes):
        nonlocal staged_path
        calls.append(list(args))
        if args[0] == "cp":
            staged_path = Path(args[1])
            assert staged_path.read_bytes() == b"binary\0payload"
        return command_result()

    monkeypatch.setattr(SbxSandbox, "_run_cli", run_cli)

    await backend.write_file(sandbox, "/tmp/data/input.bin", b"binary\0payload")

    assert calls[0] == ["exec", sandbox.id, "mkdir", "-p", "/tmp/data"]
    assert calls[1][0] == "cp"
    assert calls[1][2] == f"{sandbox.id}:/tmp/data/input.bin"
    assert staged_path is not None and not staged_path.exists()


def test_failed_file_staging_removes_the_partial_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))

    class FullDisk:
        def __init__(self, descriptor: int) -> None:
            self._descriptor = descriptor

        def __enter__(self):
            return self

        def __exit__(self, *exc_info: object) -> bool:
            os.close(self._descriptor)
            return False

        def write(self, content: bytes) -> int:
            os.write(self._descriptor, content[:4])
            raise OSError(28, "No space left on device")

    monkeypatch.setattr(
        sbx_module.os,
        "fdopen",
        lambda descriptor, *args, **kwargs: FullDisk(descriptor),
    )

    with pytest.raises(OSError, match="No space left on device"):
        sbx_module._stage_file(b"sensitive payload")

    assert list(tmp_path.glob("prefect-sandbox-upload-*")) == []


async def test_staged_file_deletion_failure_is_typed(
    backend: SbxSandbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    sandbox = activate(backend)
    staged_path: Path | None = None
    real_unlink = os.unlink

    async def run_cli(self, args, *, timeout, max_output_bytes):
        nonlocal staged_path
        if args[0] == "cp":
            staged_path = Path(args[1])
        return command_result()

    def fail_unlink(path: str | os.PathLike[str]) -> None:
        raise PermissionError(13, "Permission denied", path)

    monkeypatch.setattr(SbxSandbox, "_run_cli", run_cli)
    monkeypatch.setattr(sbx_module.os, "unlink", fail_unlink)

    with pytest.raises(SandboxError, match="failed to remove staged file"):
        await backend.write_file(sandbox, "/input.bin", b"sensitive")

    assert staged_path is not None and staged_path.exists()
    real_unlink(staged_path)


async def test_cancelling_file_staging_joins_and_removes_the_file(
    backend: SbxSandbox,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sandbox = activate(backend)
    staged = tmp_path / "prefect-sandbox-upload-sensitive"
    started = threading.Event()
    release = threading.Event()
    cli_calls: list[list[str]] = []

    def slow_stage(content: bytes) -> str:
        staged.write_bytes(content)
        started.set()
        if not release.wait(5):
            raise RuntimeError("test did not release file staging")
        return str(staged)

    async def run_cli(self, args, *, timeout, max_output_bytes):
        cli_calls.append(list(args))
        return command_result()

    monkeypatch.setattr(sbx_module, "_stage_file", slow_stage)
    monkeypatch.setattr(SbxSandbox, "_run_cli", run_cli)
    writing = asyncio.create_task(
        backend.write_file(sandbox, "/input.bin", b"sensitive")
    )
    try:
        assert await asyncio.to_thread(started.wait, 2)
        writing.cancel()
        await asyncio.sleep(0)
        assert not writing.done()
    finally:
        release.set()

    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(writing, 5)
    assert not staged.exists()
    assert cli_calls == []


@pytest.mark.parametrize("path", ["relative", "/tmp/../secret", "/tmp/bad\0path"])
async def test_write_file_rejects_unsafe_paths(backend: SbxSandbox, path: str) -> None:
    sandbox = activate(backend)

    with pytest.raises(ValueError):
        await backend.write_file(sandbox, path, b"content")


async def test_cli_runner_bounds_each_stream_while_draining() -> None:
    backend = SbxSandbox(sbx_path=sys.executable)
    script = "import sys; sys.stdout.write('abcdef'); sys.stderr.write('uvwxyz')"

    result = await backend._run_cli(["-c", script], timeout=5, max_output_bytes=4)

    assert result.stdout == b"abcd"
    assert result.stderr == b"uvwx"
    assert result.truncated


async def test_cli_runner_kills_timed_out_process() -> None:
    backend = SbxSandbox(sbx_path=sys.executable)

    with pytest.raises(asyncio.TimeoutError):
        await backend._run_cli(
            ["-c", "import time; time.sleep(10)"],
            timeout=0.05,
            max_output_bytes=100,
        )
