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


def _hook_command_prefix(command: list[str]) -> list[str]:
    for module_index, argument in enumerate(command[:-1]):
        if argument == "-m" and command[module_index + 1] in {
            "prefect.engine",
            "prefect.flow_engine",
        }:
            return command[:module_index]
    return [get_sys_executable()]


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


async def supervise(config: WorkspaceSupervisorConfig) -> int:
    workspace = await prepare_workspace_for_flow_run(
        config.flow_run_id, config.workspace_root
    )
    environment = sanitize_subprocess_env(workspace_environment(workspace))
    selected_command = _workspace_command(workspace, config.command)
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
        hook_command_prefix=_hook_command_prefix(command),
        environment=environment,
    )
    write_private_model(config.manifest_path, manifest)

    await APILogHandler.aflush()
    process = await anyio.open_process(
        command,
        cwd=workspace.working_directory,
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
    except Exception:
        traceback.print_exc(file=sys.stderr)
        return 1
    finally:
        await APILogHandler.aflush()


def main(argv: list[str] | None = None) -> int:
    exit_code = anyio.run(_main_async, argv)
    if sys.platform != "win32" and exit_code < 0:
        os.kill(os.getpid(), -exit_code)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
