"""`SbxSandbox` driven through a fake `sbx` binary on PATH.

The backend's whole surface is a subprocess, so the interesting failure modes
are subprocess failure modes: a full pipe, a child that ignores its budget, a
grandchild that outlives its parent, an exit code that must be read as data.
Mocking `asyncio` would hide every one of them, so these tests install a real
executable on PATH and let the real event loop talk to it over real pipes.

The fake is a small Python script (`_FAKE_SBX_SOURCE`) that records its argv,
keeps a directory of "existing" sandboxes so `rm` can be idempotent the way the
real CLI is, and — for `exec` — actually runs the argv it was handed. That last
part is what makes the timeout and output-cap assertions meaningful: the exit
codes and the bytes are real.

Behaviour verified against sbx v0.35.0 by recon and reproduced here: `create -q`
prints nothing, `exec` propagates the inner exit code verbatim, `exec` announces
an auto-start on *stderr*, and `rm -f` of a missing sandbox exits 1.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import os
import re
import sys
import time
from pathlib import Path

import pytest
from prefect_sandbox.base import (
    MAX_INLINE_FILE_BYTES,
    SANDBOX_NAME_PREFIX,
    Sandbox,
    SandboxCreationError,
    SandboxError,
    SandboxUnavailableError,
)
from prefect_sandbox.sbx import SbxSandbox, _strip_autostart_notice

if sys.platform == "win32":  # pragma: no cover - the fake relies on POSIX exec
    pytest.skip(
        "the fake sbx binary and process-group assertions are POSIX-only",
        allow_module_level=True,
    )


_FAKE_SBX_SOURCE = r'''
"""A stand-in for the `sbx` CLI, driven by a JSON config file."""

import json
import os
import shutil
import subprocess
import sys
import time

STATE = os.environ["FAKE_SBX_STATE"]


def _config():
    with open(os.path.join(STATE, "config.json")) as handle:
        return json.load(handle)


def _record(argv):
    with open(os.path.join(STATE, "calls.jsonl"), "a") as handle:
        handle.write(json.dumps({"argv": argv, "pid": os.getpid()}) + "\n")


def _sandbox_file(name):
    return os.path.join(STATE, "sandboxes", name)


def _emit(section):
    sys.stdout.write(section.get("stdout", ""))
    sys.stdout.flush()
    sys.stderr.write(section.get("stderr", ""))
    sys.stderr.flush()


def _exit_status(returncode):
    # Shell convention, which is what the real CLI reports: a child killed by
    # signal N exits 128 + N.
    return returncode if returncode >= 0 else 128 - returncode


def _run(command):
    return _exit_status(subprocess.Popen(command).wait())


def _create(argv, section):
    name = argv[argv.index("--name") + 1]
    time.sleep(section.get("sleep", 0))
    _emit(section)
    exit_code = section.get("exit", 0)
    # Even a failed create can leave a live microVM behind, which is precisely
    # what acreate's cleanup path has to remove.
    if exit_code == 0 or section.get("leak", True):
        open(_sandbox_file(name), "w").close()
    return exit_code


def _exec(argv, section):
    rest = argv[1:]
    while rest and rest[0] in ("-e", "-w", "-u"):
        rest = rest[2:]
    name, command = rest[0], rest[1:]
    if not os.path.exists(_sandbox_file(name)):
        sys.stderr.write("ERROR: no sandbox named '%s'\n" % name)
        return 1
    if section.get("autostart_notice"):
        sys.stderr.write("Sandbox %s started successfully\n" % name)
        sys.stderr.flush()
    _emit(section)
    if section.get("mode") == "hang":
        orphan_after = section.get("orphan_after")
        if orphan_after is not None:
            # A grandchild in the same process group, so a plain kill of this
            # process leaves it running and only a killpg reaches it.
            subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    "import sys, time; time.sleep(float(sys.argv[1]));"
                    " open(sys.argv[2], 'w').close()",
                    str(orphan_after),
                    os.path.join(STATE, "orphan-marker"),
                ]
            )
        while True:
            time.sleep(0.05)
    if "exit" in section:
        return section["exit"]
    return _run(command)


def _rm(argv, section):
    if "exit" in section:
        return section["exit"]
    missing = False
    for name in [arg for arg in argv[1:] if not arg.startswith("-")]:
        path = _sandbox_file(name)
        if os.path.exists(path):
            os.unlink(path)
            sys.stdout.write("Sandbox '%s' removed\n" % name)
        else:
            missing = True
            sys.stderr.write(
                "Error: sandbox '%s' not found (run 'sbx ls' to see your"
                " sandboxes)\n" % name
            )
    return 1 if missing else 0


def _ls(argv, section):
    if "exit" in section:
        _emit(section)
        return section["exit"]
    sandboxes = [
        {"name": name} for name in sorted(os.listdir(os.path.join(STATE, "sandboxes")))
    ]
    sys.stdout.write(json.dumps({"sandboxes": sandboxes}))
    return 0


def _cp(argv, section):
    if "exit" in section:
        _emit(section)
        return section["exit"]
    source, destination = argv[1], argv[2]
    name, _, remote = destination.partition(":")
    if not os.path.exists(_sandbox_file(name)):
        sys.stderr.write("ERROR: no sandbox named '%s'\n" % name)
        return 1
    shutil.copyfile(
        source, os.path.join(STATE, "copies", remote.strip("/").replace("/", "__"))
    )
    return 0


def _policy(argv, section):
    if len(argv) > 1 and argv[1] == "ls":
        verification = section.get("verification", "active")
        if verification == "malformed":
            sys.stdout.write("{not-json")
        else:
            rules = []
            if verification != "missing":
                rules.append(
                    {
                        "resource_type": "network",
                        "decision": "deny",
                        "resources": section.get("resources", ["**"]),
                        "status": verification,
                    }
                )
            sys.stdout.write(json.dumps({"rules": rules}))
        return section.get("ls_exit", 0)
    _emit(section)
    return section.get("exit", 0)


HANDLERS = {
    "create": _create,
    "exec": _exec,
    "ls": _ls,
    "rm": _rm,
    "cp": _cp,
    "policy": _policy,
}


def main():
    argv = sys.argv[1:]
    _record(argv)
    handler = HANDLERS.get(argv[0] if argv else "")
    if handler is None:
        sys.stderr.write("ERROR: unknown command\n")
        return 1
    return handler(argv, _config().get(argv[0], {}))


sys.exit(main())
'''


@dataclasses.dataclass
class FakeSbx:
    """Control surface for the fake CLI: configuration in, observations out."""

    root: Path
    config: dict[str, dict[str, object]] = dataclasses.field(default_factory=dict)

    @property
    def binary(self) -> Path:
        return self.root / "bin" / "sbx"

    def configure(self, subcommand: str, **values: object) -> None:
        """Set the behaviour of one subcommand.

        Args:
            subcommand: `create`, `exec`, `rm`, `cp` or `policy`.
            **values: `exit`, `sleep`, `stdout`, `stderr`, `mode`, `leak`,
                `autostart_notice`, `orphan_after`.
        """
        self.config.setdefault(subcommand, {}).update(values)
        self.flush()

    def flush(self) -> None:
        (self.root / "config.json").write_text(json.dumps(self.config))

    @property
    def calls(self) -> list[list[str]]:
        """Every recorded invocation's argv, in order."""
        path = self.root / "calls.jsonl"
        if not path.exists():
            return []
        return [
            json.loads(line)["argv"]
            for line in path.read_text().splitlines()
            if line.strip()
        ]

    def calls_for(self, subcommand: str) -> list[list[str]]:
        return [argv for argv in self.calls if argv and argv[0] == subcommand]

    @property
    def live_sandboxes(self) -> set[str]:
        """Names the fake currently believes exist."""
        return {path.name for path in (self.root / "sandboxes").iterdir()}

    def copied(self, remote_path: str) -> str:
        """The bytes `sbx cp` delivered to `remote_path`, decoded as UTF-8."""
        mangled = remote_path.strip("/").replace("/", "__")
        return (self.root / "copies" / mangled).read_text(encoding="utf-8")

    @property
    def orphan_marker(self) -> Path:
        return self.root / "orphan-marker"


@pytest.fixture
def fake_sbx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeSbx:
    """Install a controllable `sbx` executable as the first thing on PATH."""
    root = tmp_path / "fake-sbx"
    for subdirectory in ("bin", "sandboxes", "copies"):
        (root / subdirectory).mkdir(parents=True)
    fake = FakeSbx(root=root)
    fake.binary.write_text(f"#!{sys.executable}\n{_FAKE_SBX_SOURCE}")
    fake.binary.chmod(0o755)
    fake.flush()
    monkeypatch.setenv("FAKE_SBX_STATE", str(root))
    monkeypatch.setenv("PATH", f"{root / 'bin'}{os.pathsep}{os.environ['PATH']}")
    return fake


@pytest.fixture
def backend(fake_sbx: FakeSbx) -> SbxSandbox:
    """A backend that resolves `sbx` by name, exactly as a user's would."""
    return SbxSandbox(create_timeout=60.0)


def sleep_command(seconds: float) -> list[str]:
    """Argv that sleeps inside the sandbox.

    The backend never interprets the argv, so the host interpreter standing in
    for a guest one changes nothing about what is under test.
    """
    return [sys.executable, "-c", f"import time; time.sleep({seconds})"]


def write_command(stream: str, byte_count: int) -> list[str]:
    """Argv that floods `stream` with `byte_count` bytes."""
    return [
        sys.executable,
        "-c",
        f"import sys; sys.{stream}.write('x' * {byte_count})",
    ]


class TestBinaryAvailability:
    async def test_a_missing_binary_is_reported_as_unavailable(self) -> None:
        backend = SbxSandbox(sbx_path="sbx-that-is-not-installed")
        with pytest.raises(SandboxUnavailableError) as excinfo:
            await backend.acreate()
        message = str(excinfo.value)
        assert "sbx-that-is-not-installed" in message
        assert "sbx login" in message

    async def test_an_unexecutable_binary_is_reported_as_unavailable(
        self, tmp_path: Path
    ) -> None:
        """The `shutil.which` preflight can be raced or simply be wrong.

        A file that is executable but not a program passes `which` and fails at
        `execvp`; that OSError must still surface as `SandboxUnavailableError`
        rather than escaping raw.
        """
        broken = tmp_path / "sbx"
        broken.write_bytes(b"\xff\xfe not a program")
        broken.chmod(0o755)
        backend = SbxSandbox(sbx_path=str(broken))
        with pytest.raises(SandboxUnavailableError):
            await backend.acreate()

    async def test_a_failed_preflight_leaves_no_workspace(self, tmp_path: Path) -> None:
        before = set(
            Path(os.environ.get("TMPDIR", "/tmp")).glob("prefect-sandbox-ws-*")
        )
        backend = SbxSandbox(sbx_path="sbx-that-is-not-installed")
        with pytest.raises(SandboxUnavailableError):
            await backend.acreate()
        after = set(Path(os.environ.get("TMPDIR", "/tmp")).glob("prefect-sandbox-ws-*"))
        assert after == before


class TestCreate:
    async def test_argv_and_handle(
        self, backend: SbxSandbox, fake_sbx: FakeSbx
    ) -> None:
        sandbox = await backend.acreate()

        workspace = sandbox.metadata["workspace"]
        assert fake_sbx.calls_for("create") == [
            [
                "create",
                "-q",
                "--name",
                sandbox.id,
                "--memory",
                "2g",
                "--template",
                "python:3.12-slim",
                # `shell` is a required agent subcommand and the workspace path
                # must follow it.
                "shell",
                workspace,
            ]
        ]
        assert sandbox.id.startswith(SANDBOX_NAME_PREFIX)
        assert sandbox.backend == "sbx"
        assert fake_sbx.live_sandboxes == {sandbox.id}

    async def test_the_workspace_is_a_fresh_empty_host_directory(
        self, backend: SbxSandbox
    ) -> None:
        """It is mounted read-write at the same path inside the microVM, so it
        being empty is what keeps the host filesystem out of reach."""
        sandbox = await backend.acreate()
        workspace = Path(sandbox.metadata["workspace"])
        assert workspace.is_absolute()
        assert workspace.is_dir()
        assert list(workspace.iterdir()) == []

    async def test_cpus_are_passed_only_when_set(self, fake_sbx: FakeSbx) -> None:
        sandbox = await SbxSandbox(cpus=4).acreate()
        argv = fake_sbx.calls_for("create")[0]
        assert argv[argv.index("--cpus") + 1] == "4"
        assert argv.index("--cpus") < argv.index("--template")
        assert sandbox.id in argv

    async def test_image_and_memory_come_from_the_block(
        self, fake_sbx: FakeSbx
    ) -> None:
        await SbxSandbox(image="alpine:3.20", memory="512m").acreate()
        argv = fake_sbx.calls_for("create")[0]
        assert argv[argv.index("--template") + 1] == "alpine:3.20"
        assert argv[argv.index("--memory") + 1] == "512m"

    async def test_concurrent_creates_on_one_block_are_isolated(
        self, backend: SbxSandbox, fake_sbx: FakeSbx
    ) -> None:
        """Invariant 1: one shared block instance, no shared per-sandbox state."""
        first, second = await asyncio.gather(backend.acreate(), backend.acreate())
        assert first.id != second.id
        assert first.metadata["workspace"] != second.metadata["workspace"]
        assert fake_sbx.live_sandboxes == {first.id, second.id}


class TestCreateFailureCleanup:
    """Invariant 4: a failed create leaks neither a microVM nor host state."""

    async def test_a_nonzero_create_cleans_up(
        self, backend: SbxSandbox, fake_sbx: FakeSbx
    ) -> None:
        fake_sbx.configure("create", exit=1, stderr="Error: invalid memory value\n")

        with pytest.raises(SandboxCreationError) as excinfo:
            await backend.acreate()

        message = str(excinfo.value)
        assert "exit code 1" in message
        assert "invalid memory value" in message

        name = fake_sbx.calls_for("create")[0][3]
        assert fake_sbx.calls_for("rm") == [["rm", "-f", name]]
        assert fake_sbx.live_sandboxes == set()
        workspace = fake_sbx.calls_for("create")[0][-1]
        assert not Path(workspace).exists()

    async def test_a_timed_out_create_cleans_up(self, fake_sbx: FakeSbx) -> None:
        fake_sbx.configure("create", sleep=30)
        backend = SbxSandbox(create_timeout=2)

        with pytest.raises(SandboxCreationError) as excinfo:
            await backend.acreate()
        assert "create_timeout" in str(excinfo.value)

        assert fake_sbx.calls_for("rm")
        # The half-created sandbox is gone even though `create` never returned.
        assert fake_sbx.live_sandboxes == set()
        workspace = fake_sbx.calls_for("create")[0][-1]
        assert not Path(workspace).exists()

    async def test_a_cancelled_create_cleans_up(
        self, backend: SbxSandbox, fake_sbx: FakeSbx
    ) -> None:
        """A cancelled flow run must not abandon a live microVM.

        The cleanup in `acreate` is shielded for exactly this: without it the
        first await in the handler re-raises and the sandbox is orphaned.
        """
        fake_sbx.configure("create", sleep=5)
        task = asyncio.ensure_future(backend.acreate())
        while not fake_sbx.calls_for("create"):
            await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert fake_sbx.calls_for("rm")
        assert fake_sbx.live_sandboxes == set()
        workspace = fake_sbx.calls_for("create")[0][-1]
        assert not Path(workspace).exists()

    async def test_a_cleanup_failure_reports_a_possible_live_sandbox(
        self, backend: SbxSandbox, fake_sbx: FakeSbx
    ) -> None:
        fake_sbx.configure("create", exit=1, stderr="create failed\n")
        fake_sbx.configure("rm", exit=1, stderr="daemon unreachable\n")

        with pytest.raises(SandboxCreationError, match="may still be running"):
            await backend.acreate()

        assert fake_sbx.live_sandboxes


class TestEgress:
    async def test_inherit_adds_no_policy_rule(
        self, backend: SbxSandbox, fake_sbx: FakeSbx
    ) -> None:
        await backend.acreate()
        assert fake_sbx.calls_for("policy") == []

    async def test_deny_layers_a_deny_all_rule(self, fake_sbx: FakeSbx) -> None:
        sandbox = await SbxSandbox(egress="deny").acreate()
        assert fake_sbx.calls_for("policy") == [
            ["policy", "deny", "network", "--sandbox", sandbox.id, "**"],
            ["policy", "ls", sandbox.id, "--json"],
        ]

    async def test_a_rejected_rule_is_fatal_and_cleans_up(
        self, fake_sbx: FakeSbx
    ) -> None:
        """Shipping a sandbox with the egress the caller asked to block is
        worse than failing to create one."""
        fake_sbx.configure("policy", exit=1, stderr="policy store not initialized\n")

        with pytest.raises(SandboxCreationError) as excinfo:
            await SbxSandbox(egress="deny").acreate()
        message = str(excinfo.value)
        assert "policy store not initialized" in message
        assert "sbx policy init" in message

        assert fake_sbx.calls_for("rm")
        assert fake_sbx.live_sandboxes == set()
        workspace = fake_sbx.calls_for("create")[0][-1]
        assert not Path(workspace).exists()

    @pytest.mark.parametrize("verification", ["inactive", "missing", "malformed"])
    async def test_an_unverified_deny_rule_is_fatal_and_cleans_up(
        self, fake_sbx: FakeSbx, verification: str
    ) -> None:
        fake_sbx.configure("policy", verification=verification)

        with pytest.raises(SandboxCreationError, match="verify|blocked egress"):
            await SbxSandbox(egress="deny").acreate()

        assert fake_sbx.calls_for("rm")
        assert fake_sbx.live_sandboxes == set()

    async def test_malformed_policy_resources_fail_as_a_creation_error(
        self, fake_sbx: FakeSbx
    ) -> None:
        fake_sbx.configure("policy", resources=None)

        with pytest.raises(SandboxCreationError, match="blocked egress"):
            await SbxSandbox(egress="deny").acreate()

        assert fake_sbx.live_sandboxes == set()

    def test_an_unknown_egress_value_is_rejected_up_front(self) -> None:
        with pytest.raises(ValueError):
            SbxSandbox(egress="allow-all")  # type: ignore[arg-type]


class TestExecArgv:
    async def test_passes_the_command_as_an_argv_list(
        self, backend: SbxSandbox, fake_sbx: FakeSbx
    ) -> None:
        sandbox = await backend.acreate()
        await backend.aexec(sandbox, ["echo", "hi"], timeout=5)

        assert fake_sbx.calls_for("exec") == [["exec", sandbox.id, "echo", "hi"]]

    async def test_env_and_working_dir_use_native_flags(
        self, backend: SbxSandbox, fake_sbx: FakeSbx
    ) -> None:
        """No shell trampoline: nothing the caller passes is ever re-parsed."""
        sandbox = await backend.acreate()
        await backend.aexec(
            sandbox,
            ["echo", "hi"],
            timeout=5,
            env={"FIRST": "1", "SECOND": "two words"},
            working_dir="/work dir",
        )

        argv = fake_sbx.calls_for("exec")[0]
        assert argv[:8] == [
            "exec",
            "-e",
            "FIRST=1",
            "-e",
            "SECOND=two words",
            "-w",
            "/work dir",
            sandbox.id,
        ]
        assert "sh" not in argv
        assert "-c" not in argv

    async def test_no_worker_credentials_reach_the_command_line(
        self,
        backend: SbxSandbox,
        fake_sbx: FakeSbx,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Invariant 7, as far as a fake CLI can prove it.

        The CLI child inherits the worker environment on purpose — it needs the
        host's Docker credentials — but nothing of the worker's may be forwarded
        into the sandbox, and `sbx exec` forwards only `-e` values. So the check
        is that no worker secret appears anywhere in the argv.
        """
        monkeypatch.setenv("PREFECT_API_KEY", "pnu_supersecret")
        monkeypatch.setenv("PREFECT_API_URL", "https://api.prefect.cloud/x")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "canary-aws-secret")

        sandbox = await backend.acreate()
        await backend.aexec(sandbox, ["env"], timeout=5, env={"SAFE": "yes"})

        flat = " ".join(fake_sbx.calls_for("exec")[0])
        assert "SAFE=yes" in flat
        for secret in ("pnu_supersecret", "api.prefect.cloud", "canary-aws-secret"):
            assert secret not in flat
        assert "PREFECT_API_KEY" not in flat

    @pytest.mark.parametrize(
        ("kwargs", "match"),
        [
            ({"command": [], "timeout": 5}, "must not be empty"),
            ({"command": ["true"], "timeout": 0}, "positive"),
            ({"command": ["true"], "timeout": -1}, "positive"),
            ({"command": ["true"], "timeout": float("inf")}, "positive"),
            ({"command": ["true"], "timeout": float("nan")}, "positive"),
        ],
    )
    async def test_invalid_arguments_are_rejected_before_any_subprocess(
        self,
        backend: SbxSandbox,
        fake_sbx: FakeSbx,
        kwargs: dict[str, object],
        match: str,
    ) -> None:
        sandbox = await backend.acreate()
        with pytest.raises(ValueError, match=match):
            await backend.aexec(sandbox, **kwargs)  # type: ignore[arg-type]
        assert fake_sbx.calls_for("exec") == []

    async def test_an_inexpressible_env_is_rejected(
        self, backend: SbxSandbox, fake_sbx: FakeSbx
    ) -> None:
        sandbox = await backend.acreate()
        with pytest.raises(ValueError, match="Invalid environment variable name"):
            await backend.aexec(sandbox, ["true"], timeout=5, env={"BAD=NAME": "value"})
        assert fake_sbx.calls_for("exec") == []


class TestExecResults:
    async def test_stdout_is_captured(self, backend: SbxSandbox) -> None:
        sandbox = await backend.acreate()
        result = await backend.aexec(
            sandbox, [sys.executable, "-c", "print('hello')"], timeout=30
        )
        assert result.stdout == "hello\n"
        assert result.stderr == ""
        assert result.exit_code == 0
        assert result.ok
        assert not result.truncated

    async def test_the_streams_stay_separate(self, backend: SbxSandbox) -> None:
        sandbox = await backend.acreate()
        result = await backend.aexec(
            sandbox,
            [
                sys.executable,
                "-c",
                "import sys; sys.stdout.write('out'); sys.stderr.write('err')",
            ],
            timeout=30,
        )
        assert (result.stdout, result.stderr) == ("out", "err")

    async def test_a_nonzero_exit_is_data_not_an_exception(
        self, backend: SbxSandbox
    ) -> None:
        """Invariant 8."""
        sandbox = await backend.acreate()
        result = await backend.aexec(
            sandbox, [sys.executable, "-c", "raise SystemExit(3)"], timeout=30
        )
        assert result.exit_code == 3
        assert not result.ok
        assert not result.timed_out
        assert not result.sandbox_terminated
        # Only asking for a raise produces one.
        with pytest.raises(SandboxError):
            result.raise_for_status()

    async def test_undecodable_output_does_not_crash(self, backend: SbxSandbox) -> None:
        sandbox = await backend.acreate()
        result = await backend.aexec(
            sandbox,
            [
                sys.executable,
                "-c",
                "import sys; sys.stdout.buffer.write(b'\\xff\\xfeok')",
            ],
            timeout=30,
        )
        assert result.stdout.endswith("ok")
        assert "�" in result.stdout

    async def test_a_vanished_sandbox_is_a_plain_failure(
        self, backend: SbxSandbox
    ) -> None:
        """`sbx exec` cannot be told apart from a command that exited 1, so the
        CLI's own message is preserved rather than guessed at."""
        result = await backend.aexec(
            Sandbox(id="never-created", backend="sbx"), ["true"], timeout=5
        )
        assert result.exit_code == 1
        assert "no sandbox named" in result.stderr
        assert not result.timed_out


class TestTimeoutSemantics:
    """Invariant 6: `timed_out` only when the budget actually fired."""

    async def test_a_command_that_exits_124_is_not_mislabeled_as_timed_out(
        self, backend: SbxSandbox, fake_sbx: FakeSbx
    ) -> None:
        fake_sbx.configure("exec", exit=124)
        sandbox = await backend.acreate()
        result = await backend.aexec(sandbox, ["whatever"], timeout=5)
        assert not result.timed_out
        assert result.exit_code == 124
        assert not result.sandbox_terminated
        assert fake_sbx.live_sandboxes == {sandbox.id}

    async def test_a_real_overrun_destroys_the_sandbox(
        self, backend: SbxSandbox, fake_sbx: FakeSbx
    ) -> None:
        sandbox = await backend.acreate()
        started = time.monotonic()
        result = await backend.aexec(sandbox, sleep_command(30), timeout=0.5)
        elapsed = time.monotonic() - started

        assert result.exit_code == -1
        assert result.timed_out
        assert result.sandbox_terminated
        assert fake_sbx.live_sandboxes == set()
        assert elapsed < 10, "the command was not stopped by its own budget"

    @pytest.mark.parametrize("exit_code", [1, 2, 124, 126, 127, 137, 143])
    async def test_no_other_exit_code_is_read_as_a_timeout(
        self, backend: SbxSandbox, fake_sbx: FakeSbx, exit_code: int
    ) -> None:
        fake_sbx.configure("exec", exit=exit_code)
        sandbox = await backend.acreate()
        result = await backend.aexec(sandbox, ["whatever"], timeout=5)
        assert result.exit_code == exit_code
        assert not result.timed_out

    async def test_an_oom_kill_keeps_its_own_exit_code(
        self, backend: SbxSandbox
    ) -> None:
        """137 is what an OOM kill looks like, and `--signal=KILL` would make a
        timeout indistinguishable from it."""
        sandbox = await backend.acreate()
        result = await backend.aexec(
            sandbox,
            [
                sys.executable,
                "-c",
                "import os, signal; os.kill(os.getpid(), signal.SIGKILL)",
            ],
            timeout=30,
        )
        assert result.exit_code == 137
        assert not result.timed_out

    async def test_a_wedged_cli_costs_the_sandbox(
        self,
        backend: SbxSandbox,
        fake_sbx: FakeSbx,
    ) -> None:
        """A timed-out CLI may leave the guest command alive, so the VM must go."""
        fake_sbx.configure("exec", mode="hang")
        sandbox = await backend.acreate()

        result = await backend.aexec(sandbox, ["whatever"], timeout=0.5)

        assert result.timed_out
        assert result.sandbox_terminated
        assert result.exit_code == -1
        assert "destroyed" in result.stderr
        assert fake_sbx.calls_for("rm") == [["rm", "-f", sandbox.id]]
        assert fake_sbx.live_sandboxes == set()

    async def test_a_timeout_does_not_claim_termination_when_removal_fails(
        self, backend: SbxSandbox, fake_sbx: FakeSbx
    ) -> None:
        fake_sbx.configure("exec", mode="hang")
        fake_sbx.configure("rm", exit=1, stderr="daemon unreachable\n")
        sandbox = await backend.acreate()

        with pytest.raises(SandboxError, match="may still be running"):
            await backend.aexec(sandbox, ["whatever"], timeout=0.5)

        assert sandbox.id in fake_sbx.live_sandboxes

    async def test_a_wedged_cli_leaves_no_descendants(
        self,
        backend: SbxSandbox,
        fake_sbx: FakeSbx,
    ) -> None:
        """Killing only the CLI would leave its daemon-facing child behind, so
        the whole process group goes."""
        fake_sbx.configure("exec", mode="hang", orphan_after=3)
        sandbox = await backend.acreate()

        await backend.aexec(sandbox, ["whatever"], timeout=0.5)

        await asyncio.sleep(4)
        assert not fake_sbx.orphan_marker.exists(), (
            "a grandchild of the killed CLI survived the teardown"
        )


class TestOutputCap:
    """Invariant 5: capped while streaming, never buffered then trimmed."""

    async def test_a_flood_of_stdout_is_capped_without_deadlocking(
        self, fake_sbx: FakeSbx
    ) -> None:
        backend = SbxSandbox(max_output_bytes=1024)
        sandbox = await backend.acreate()

        started = time.monotonic()
        # Two orders of magnitude past the OS pipe buffer: a reader that simply
        # stopped at the cap would block the writer forever here.
        result = await backend.aexec(
            sandbox, write_command("stdout", 8 * 1024 * 1024), timeout=60
        )
        elapsed = time.monotonic() - started

        assert len(result.stdout.encode()) == 1024
        assert result.truncated
        assert result.exit_code == 0, "the flooding command did not finish"
        assert elapsed < 30

    async def test_stderr_is_capped_independently(self, fake_sbx: FakeSbx) -> None:
        backend = SbxSandbox(max_output_bytes=512)
        sandbox = await backend.acreate()
        result = await backend.aexec(
            sandbox, write_command("stderr", 4 * 1024 * 1024), timeout=60
        )
        assert len(result.stderr.encode()) == 512
        assert result.truncated
        assert result.exit_code == 0

    async def test_output_exactly_at_the_cap_is_not_flagged(
        self, fake_sbx: FakeSbx
    ) -> None:
        backend = SbxSandbox(max_output_bytes=64)
        sandbox = await backend.acreate()
        result = await backend.aexec(sandbox, write_command("stdout", 64), timeout=30)
        assert result.stdout == "x" * 64
        assert not result.truncated


class TestAutoStartNotice:
    async def test_the_notice_is_stripped_from_stderr(
        self, backend: SbxSandbox, fake_sbx: FakeSbx
    ) -> None:
        """`sbx exec` silently starts a stopped sandbox and says so on stderr;
        that chatter must not be attributed to the sandboxed program."""
        fake_sbx.configure("exec", autostart_notice=True)
        sandbox = await backend.acreate()
        result = await backend.aexec(
            sandbox,
            [sys.executable, "-c", "import sys; sys.stderr.write('real warning\\n')"],
            timeout=30,
        )
        assert result.stderr == "real warning\n"

    async def test_only_the_notice_is_stripped(self) -> None:
        stderr = (
            "before\nSandbox my-sandbox started successfully\nafter\n"
            "Sandbox other started successfully\n"
        )
        assert _strip_autostart_notice(stderr, "my-sandbox") == (
            "before\nafter\nSandbox other started successfully\n"
        )

    async def test_unrelated_stderr_is_untouched(self) -> None:
        stderr = "Traceback (most recent call last):\n  File ...\n"
        assert _strip_autostart_notice(stderr, "my-sandbox") == stderr

    async def test_a_notice_without_a_trailing_newline_is_stripped(self) -> None:
        assert _strip_autostart_notice("Sandbox s started successfully", "s") == ""


class TestDestroy:
    async def test_removes_the_sandbox_and_its_workspace(
        self, backend: SbxSandbox, fake_sbx: FakeSbx
    ) -> None:
        sandbox = await backend.acreate()
        workspace = Path(sandbox.metadata["workspace"])

        await backend.adestroy(sandbox)

        assert fake_sbx.calls_for("rm") == [["rm", "-f", sandbox.id]]
        assert fake_sbx.live_sandboxes == set()
        assert not workspace.exists()

    async def test_is_idempotent(self, backend: SbxSandbox, fake_sbx: FakeSbx) -> None:
        """Invariant 3. `sbx rm -f` exits 1 for a sandbox that is already gone,
        so a successful `sbx ls --json` must confirm it is absent."""
        sandbox = await backend.acreate()
        await backend.adestroy(sandbox)
        await backend.adestroy(sandbox)
        assert len(fake_sbx.calls_for("rm")) == 2
        assert fake_sbx.calls_for("ls") == [["ls", "--json"]]

    async def test_destroying_a_handle_that_was_never_created_succeeds(
        self, backend: SbxSandbox, fake_sbx: FakeSbx
    ) -> None:
        await backend.adestroy(Sandbox(id="never-created", backend="sbx"))
        assert fake_sbx.calls_for("rm") == [["rm", "-f", "never-created"]]

    async def test_a_failing_rm_is_loud_and_preserves_the_workspace_for_retry(
        self, backend: SbxSandbox, fake_sbx: FakeSbx
    ) -> None:
        sandbox = await backend.acreate()
        fake_sbx.configure("rm", exit=1, stderr="daemon unreachable\n")

        with pytest.raises(SandboxError, match="may still be running"):
            await backend.adestroy(sandbox)

        assert sandbox.id in fake_sbx.live_sandboxes
        assert Path(sandbox.metadata["workspace"]).exists()

    async def test_unowned_workspace_is_never_recursively_deleted(
        self, backend: SbxSandbox, fake_sbx: FakeSbx, tmp_path: Path
    ) -> None:
        handle = Sandbox(
            id="forged",
            backend="sbx",
            metadata={"workspace": str(tmp_path)},
        )

        with pytest.raises(SandboxError, match="Refusing to remove unowned"):
            await backend.adestroy(handle)

        assert tmp_path.exists()
        assert fake_sbx.calls_for("rm") == [["rm", "-f", "forged"]]

    async def test_an_already_deleted_workspace_is_not_an_error(
        self, backend: SbxSandbox
    ) -> None:
        sandbox = await backend.acreate()
        Path(sandbox.metadata["workspace"]).rmdir()
        await backend.adestroy(sandbox)

    async def test_destroying_one_sandbox_leaves_the_other_alone(
        self, backend: SbxSandbox, fake_sbx: FakeSbx
    ) -> None:
        """Invariant 1: one shared backend, two flow runs, no crosstalk."""
        first, second = await asyncio.gather(backend.acreate(), backend.acreate())

        await backend.adestroy(first)

        assert fake_sbx.live_sandboxes == {second.id}
        assert not Path(first.metadata["workspace"]).exists()
        assert Path(second.metadata["workspace"]).is_dir()
        # And the survivor is still usable.
        result = await backend.aexec(
            second, [sys.executable, "-c", "print('alive')"], timeout=30
        )
        assert result.stdout == "alive\n"


class TestSession:
    async def test_destroys_the_sandbox_when_the_body_raises(
        self, backend: SbxSandbox, fake_sbx: FakeSbx
    ) -> None:
        with pytest.raises(RuntimeError):
            async with backend.asession() as sandbox:
                assert fake_sbx.live_sandboxes == {sandbox.id}
                raise RuntimeError("boom")
        assert fake_sbx.live_sandboxes == set()

    async def test_concurrent_sessions_get_their_own_sandbox(
        self, backend: SbxSandbox, fake_sbx: FakeSbx
    ) -> None:
        async def run(marker: str) -> str:
            async with backend.asession() as sandbox:
                result = await backend.aexec(
                    sandbox,
                    [sys.executable, "-c", f"print({marker!r})"],
                    timeout=30,
                )
                return result.stdout.strip()

        assert await asyncio.gather(run("first"), run("second")) == [
            "first",
            "second",
        ]
        assert fake_sbx.live_sandboxes == set()


class TestWriteFile:
    async def test_uses_the_native_copy(
        self, backend: SbxSandbox, fake_sbx: FakeSbx
    ) -> None:
        sandbox = await backend.acreate()
        await backend.awrite_file(
            sandbox, "/tmp/prefect-sandbox/main.py", "print('hi')\n"
        )

        # `sbx cp` does not create missing parents.
        assert fake_sbx.calls_for("exec")[0][-3:] == [
            "mkdir",
            "-p",
            "/tmp/prefect-sandbox",
        ]
        (copy_argv,) = fake_sbx.calls_for("cp")
        assert copy_argv[2] == f"{sandbox.id}:/tmp/prefect-sandbox/main.py"
        assert fake_sbx.copied("/tmp/prefect-sandbox/main.py") == "print('hi')\n"

    async def test_the_host_temp_file_is_deleted(
        self, backend: SbxSandbox, fake_sbx: FakeSbx
    ) -> None:
        sandbox = await backend.acreate()
        await backend.awrite_file(sandbox, "/tmp/prefect-sandbox/main.py", "x")
        host_path = fake_sbx.calls_for("cp")[0][1]
        assert not Path(host_path).exists()

    async def test_no_mkdir_for_a_bare_filename(
        self, backend: SbxSandbox, fake_sbx: FakeSbx
    ) -> None:
        sandbox = await backend.acreate()
        await backend.awrite_file(sandbox, "main.py", "x")
        assert fake_sbx.calls_for("exec") == []

    async def test_is_not_bound_by_the_inline_fallback_ceiling(
        self, backend: SbxSandbox, fake_sbx: FakeSbx
    ) -> None:
        """The base fallback smuggles the payload through the command line and
        is capped; `sbx cp` streams from a host file and is not."""
        content = "y" * (MAX_INLINE_FILE_BYTES * 4)
        sandbox = await backend.acreate()
        await backend.awrite_file(sandbox, "/tmp/prefect-sandbox/big.txt", content)
        assert fake_sbx.copied("/tmp/prefect-sandbox/big.txt") == content

    async def test_content_is_written_verbatim(
        self, backend: SbxSandbox, fake_sbx: FakeSbx
    ) -> None:
        content = "quotes ' \" $(id)\nunicode héllo 🌍\n"
        sandbox = await backend.acreate()
        await backend.awrite_file(sandbox, "/tmp/prefect-sandbox/tricky.txt", content)
        assert fake_sbx.copied("/tmp/prefect-sandbox/tricky.txt") == content

    async def test_a_failed_copy_raises(
        self, backend: SbxSandbox, fake_sbx: FakeSbx
    ) -> None:
        sandbox = await backend.acreate()
        fake_sbx.configure("cp", exit=1, stderr="no space left on device\n")

        with pytest.raises(SandboxError) as excinfo:
            await backend.awrite_file(sandbox, "/tmp/prefect-sandbox/main.py", "x")
        message = str(excinfo.value)
        assert "/tmp/prefect-sandbox/main.py" in message
        assert "no space left on device" in message

    async def test_a_failed_mkdir_stops_before_copying(
        self, backend: SbxSandbox, fake_sbx: FakeSbx
    ) -> None:
        sandbox = await backend.acreate()
        fake_sbx.configure("exec", exit=1, stderr="Read-only file system\n")

        with pytest.raises(SandboxError, match="/tmp/prefect-sandbox"):
            await backend.awrite_file(sandbox, "/tmp/prefect-sandbox/main.py", "x")
        assert fake_sbx.calls_for("cp") == []

    async def test_the_host_temp_file_is_deleted_even_when_the_copy_fails(
        self, backend: SbxSandbox, fake_sbx: FakeSbx
    ) -> None:
        sandbox = await backend.acreate()
        fake_sbx.configure("cp", exit=1)
        with pytest.raises(SandboxError):
            await backend.awrite_file(sandbox, "/tmp/prefect-sandbox/main.py", "x")
        host_path = fake_sbx.calls_for("cp")[0][1]
        assert not Path(host_path).exists()


class TestBlockShape:
    def test_construction_resolves_nothing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Invariant 2: blocks are built at import time, so `__init__` must not
        even look for the binary."""
        monkeypatch.setenv("PATH", "")
        assert SbxSandbox().backend_name == "sbx"

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"image": ""},
            {"memory": ""},
            {"cpus": 0},
            {"cpus": -1},
            {"sbx_path": ""},
            {"create_timeout": 0},
            {"max_output_bytes": 0},
        ],
    )
    def test_invalid_configuration_is_rejected(self, kwargs: dict[str, object]) -> None:
        with pytest.raises(ValueError):
            SbxSandbox(**kwargs)  # type: ignore[arg-type]

    async def test_saving_and_loading_the_block_round_trips(self) -> None:
        await SbxSandbox(image="alpine:3.20", egress="deny").save(
            "sbx-round-trip", overwrite=True
        )
        loaded = await SbxSandbox.aload("sbx-round-trip")
        assert (loaded.image, loaded.egress) == ("alpine:3.20", "deny")

    def test_field_descriptions_document_the_late_memory_validation(self) -> None:
        # `sbx` only validates `--memory` after the image pull, so a typo
        # surfaces as a slow failure; the field has to say so.
        description = SbxSandbox.model_fields["memory"].description or ""
        assert "server-side" in description

    def test_the_logo_url_is_declared(self) -> None:
        assert re.match(r"https://", str(SbxSandbox._logo_url))
