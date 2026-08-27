from __future__ import annotations

import argparse
import os
import signal
import sys
import traceback
from pathlib import Path
from types import FrameType

import anyio

from prefect.logging.handlers import APILogHandler
from prefect.runner._process_manager import create_isolated_termination_scope
from prefect.runner._workspace_resolver import prepare_workspace_for_flow_run
from prefect.runner._workspace_runtime import (
    PreparedWorkspaceManifest,
    WorkspaceSupervisorConfig,
    read_model,
    write_private_model,
)
from prefect.runner._workspace_starter import (
    _workspace_command,
    workspace_environment,
)
from prefect.utilities.processutils import (
    command_from_string,
    get_sys_executable,
    sanitize_subprocess_env,
)

_RUNNER_OWNED_ENV_KEYS = {
    "PATH",
    "PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES",
    "PREFECT__WORKER_ID",
    "PREFECT__WORKER_NAME",
    "PREFECT__FLOW_ID",
    "PREFECT__FLOW_NAME",
    "PREFECT__FLOW_RUN_ID",
    "PREFECT__ENABLE_CANCELLATION_AND_CRASHED_HOOKS",
    "PREFECT__CONTROL_PORT",
    "PREFECT__CONTROL_TOKEN",
    "PREFECT__DEPLOYMENT_ID",
    "PREFECT__DEPLOYMENT_NAME",
    "PREFECT_FLOWS_HEARTBEAT_FREQUENCY",
}


def _runner_owns_environment_key(key: str) -> bool:
    return key in _RUNNER_OWNED_ENV_KEYS or key.startswith("PREFECT_API_")


def _hook_command(command: list[str]) -> list[str] | None:
    bootstrap = str(Path(__file__).with_name("_workspace_runtime_bootstrap.py"))
    for bootstrap_index, argument in enumerate(command[:-1]):
        if argument == bootstrap and command[bootstrap_index + 1] == "engine":
            return [*command[:bootstrap_index], bootstrap, "hook"]

    for module_index, argument in enumerate(command[:-1]):
        if argument == "-m" and command[module_index + 1] in {
            "prefect.engine",
            "prefect.flow_engine",
        }:
            return [*command[:module_index], bootstrap, "hook"]
    return None


def _restore_runner_environment(
    environment: dict[str, str], runner_environment: dict[str, str]
) -> None:
    for key in environment.keys() | runner_environment.keys():
        if not _runner_owns_environment_key(key):
            continue
        if key in runner_environment:
            environment[key] = runner_environment[key]
        else:
            environment.pop(key, None)


def _install_engine_signal_handlers() -> dict[int, signal.Handlers]:
    """Keep the supervisor alive while its engine handles group signals."""
    previous: dict[int, signal.Handlers] = {}

    def ignore_signal(_signum: int, _frame: FrameType | None) -> None:
        pass

    handled_signals = [signal.SIGTERM]
    if sys.platform == "win32" and hasattr(signal, "SIGBREAK"):
        handled_signals.append(signal.SIGBREAK)

    for handled_signal in handled_signals:
        previous[handled_signal] = signal.getsignal(handled_signal)
        signal.signal(handled_signal, ignore_signal)
    return previous


def _restore_signal_handlers(previous: dict[int, signal.Handlers]) -> None:
    for handled_signal, handler in previous.items():
        signal.signal(handled_signal, handler)


async def _launch_engine(
    command: list[str], *, cwd: Path, environment: dict[str, str]
) -> int:
    if sys.platform != "win32":
        # Keep the infrastructure PID and process group stable so targeted and
        # group-wide signals reach the engine after workspace preparation.
        os.chdir(cwd)
        os.execvpe(command[0], command, environment)

    process = await anyio.open_process(
        command,
        cwd=cwd,
        env=environment,
        stdin=None,
        stdout=None,
        stderr=None,
    )
    previous_handlers = _install_engine_signal_handlers()
    try:
        return await process.wait()
    finally:
        _restore_signal_handlers(previous_handlers)
        await process.aclose()


async def supervise(config: WorkspaceSupervisorConfig) -> int:
    runner_environment = {
        key: value
        for key, value in os.environ.items()
        if _runner_owns_environment_key(key)
    }
    workspace = await prepare_workspace_for_flow_run(
        config.flow_run_id, config.workspace_root
    )
    environment = sanitize_subprocess_env(workspace_environment(workspace))
    _restore_runner_environment(environment, runner_environment)
    environment["PREFECT__FLOW_RUN_ID"] = str(config.flow_run_id)
    environment["PREFECT__ENABLE_CANCELLATION_AND_CRASHED_HOOKS"] = "false"
    selected_command = _workspace_command(
        workspace,
        config.command,
        environment=environment,
    )
    command = (
        command_from_string(selected_command)
        if selected_command is not None
        else [get_sys_executable(), "-m", "prefect.engine"]
    )
    environment["PREFECT__FLOW_ENTRYPOINT"] = workspace.runtime_entrypoint

    manifest = PreparedWorkspaceManifest(
        working_directory=workspace.working_directory,
        project_root=workspace.project_root,
        runtime_entrypoint=workspace.runtime_entrypoint,
        hook_command=_hook_command(command),
        environment=environment,
    )
    write_private_model(config.manifest_path, manifest)

    await APILogHandler.aflush()
    return await _launch_engine(
        command,
        cwd=workspace.working_directory,
        environment=environment,
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare a flow workspace and supervise its engine process."
    )
    parser.add_argument("config", type=Path)
    return parser.parse_args(argv)


async def _main_async(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        config = read_model(args.config, WorkspaceSupervisorConfig)
        return await supervise(config)
    except Exception:  # noqa: BLE001
        traceback.print_exc(file=sys.stderr)
        return 1
    finally:
        await APILogHandler.aflush()


def main(argv: list[str] | None = None) -> int:
    # On Windows the supervisor must own its kill-on-close job before pull steps
    # can spawn descendants. Keep the scope alive until this one-shot process exits.
    _windows_job_scope = (
        create_isolated_termination_scope(os.getpid())
        if sys.platform == "win32"
        else None
    )
    exit_code = anyio.run(_main_async, argv)
    if sys.platform != "win32" and exit_code < 0:
        os.kill(os.getpid(), -exit_code)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
