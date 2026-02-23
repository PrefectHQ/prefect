from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import anyio
import anyio.abc

from prefect.runner._process_manager import ProcessHandle
from prefect.settings import get_current_settings
from prefect.utilities.processutils import get_sys_executable, run_process

if TYPE_CHECKING:
    from prefect.client.schemas.objects import FlowRun
    from prefect.runner.storage import RunnerStorage


class EngineCommandStarter:
    """Starts a flow run via `python -m prefect.engine` subprocess.

    Source: runner.py lines 891-965.
    Uses module-level `run_process` reference -- patch the module to override.

    `task_status_handler=lambda p: ProcessHandle(p)` ensures the signaled
    value is a `ProcessHandle`, not a raw `anyio.abc.Process`.
    """

    def __init__(
        self,
        *,
        tmp_dir: Path,
        storage: RunnerStorage | None = None,
        entrypoint: str | None = None,
        command: str | None = None,
        env: dict[str, str | None] | None = None,
        stream_output: bool = True,
        heartbeat_seconds: int | None = None,
    ) -> None:
        self._tmp_dir = tmp_dir
        self._storage = storage
        self._entrypoint = entrypoint
        self._command = command
        self._env = env or {}
        self._stream_output = stream_output
        self._heartbeat_seconds = heartbeat_seconds

    async def start(
        self,
        flow_run: FlowRun,
        task_status: anyio.abc.TaskStatus[ProcessHandle] = anyio.TASK_STATUS_IGNORED,
    ) -> None:
        # Assemble command -- mirrors runner.py lines 891-894
        if self._command is None:
            runner_command = [get_sys_executable(), "-m", "prefect.engine"]
        else:
            runner_command = shlex.split(self._command, posix=(os.name != "nt"))

        # We must add creationflags to a dict so it is only passed as a
        # function parameter on Windows, because the presence of
        # creationflags causes errors on Unix even if set to None
        kwargs: dict[str, object] = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        # Build env following runner.py lines 907-929
        env: dict[str, str | None] = {**self._env}
        env.update(get_current_settings().to_environment_variables(exclude_unset=True))
        env.update(
            {
                "PREFECT__FLOW_RUN_ID": str(flow_run.id),
                "PREFECT__STORAGE_BASE_PATH": str(self._tmp_dir),
                "PREFECT__ENABLE_CANCELLATION_AND_CRASHED_HOOKS": "false",
                **(
                    {"PREFECT__FLOW_ENTRYPOINT": self._entrypoint}
                    if self._entrypoint
                    else {}
                ),
                **(
                    {
                        "PREFECT_FLOWS_HEARTBEAT_FREQUENCY": str(
                            int(self._heartbeat_seconds)
                        )
                    }
                    if self._heartbeat_seconds is not None
                    else {}
                ),
            }
        )
        env.update(**os.environ)

        # Resolve storage destination and perform adhoc pull if needed
        cwd: Path | str | None = self._tmp_dir
        if self._storage is not None:
            cwd = self._storage.destination
        # NOTE: adhoc pull_interval logic is intentionally NOT extracted here.
        # That responsibility stays with the Runner orchestration layer (or a
        # future dedicated service), not with the process-starting strategy.

        # run_process signals task_status via task_status_handler;
        # task_status_handler wraps raw process in ProcessHandle before
        # signaling.
        await run_process(
            command=runner_command,
            stream_output=self._stream_output,
            task_status=task_status,
            task_status_handler=lambda p: ProcessHandle(p),
            env=env,
            cwd=cwd,
            **kwargs,
        )
        # run_process blocks until exit; returns when process done
