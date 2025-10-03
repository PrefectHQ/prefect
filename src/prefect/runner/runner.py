"""
Runners are responsible for managing the execution of all deployments.

When creating a deployment using either `flow.serve` or the `serve` utility,
they also will poll for scheduled runs.

Example:
    ```python
    import time
    from prefect import flow, serve


    @flow
    def slow_flow(sleep: int = 60):
        "Sleepy flow - sleeps the provided amount of time (in seconds)."
        time.sleep(sleep)


    @flow
    def fast_flow():
        "Fastest flow this side of the Mississippi."
        return


    if __name__ == "__main__":
        slow_deploy = slow_flow.to_deployment(name="sleeper", interval=45)
        fast_deploy = fast_flow.to_deployment(name="fast")

        # serve generates a Runner instance
        serve(slow_deploy, fast_deploy)
    ```

"""

from __future__ import annotations

import asyncio
import datetime
import logging
import multiprocessing.context
import os
import shlex
import signal
import subprocess
import sys
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, TypedDict, Union
from uuid import UUID

import anyio
import anyio.abc
import anyio.to_thread

from prefect._experimental.bundles import execute_bundle_in_subprocess
from prefect.client.orchestration import get_client
from prefect.exceptions import Abort
from prefect.flow_engine import run_flow_in_subprocess
from prefect.runner._base import BaseRunner
from prefect.settings import get_current_settings
from prefect.states import AwaitingRetry
from prefect.utilities.asyncutils import asyncnullcontext
from prefect.utilities.engine import propose_state_sync
from prefect.utilities.processutils import get_sys_executable, run_process

if TYPE_CHECKING:
    from prefect.client.schemas.objects import FlowRun

__all__ = ["Runner"]


class ProcessMapEntry(TypedDict):
    flow_run: "FlowRun"
    pid: int


if sys.platform == "win32":
    # exit code indicating that the process was terminated by Ctrl+C or Ctrl+Break
    STATUS_CONTROL_C_EXIT = 0xC000013A


class Runner(
    BaseRunner[Union[anyio.abc.Process, multiprocessing.context.SpawnProcess]]
):
    """
    Process-based runner implementation.

    Responsible for managing the execution of remotely initiated flow runs
    using subprocess execution.
    """

    def __init__(self, *args: Any, **kwargs: Any):
        """Initialize the process-based runner."""
        super().__init__(*args, **kwargs)

        # Process-specific tracking
        self._flow_run_process_map: dict[UUID, ProcessMapEntry] = dict()
        self.__flow_run_process_map_lock: asyncio.Lock | None = None
        self._rescheduling: bool = False

    @property
    def _flow_run_process_map_lock(self) -> asyncio.Lock:
        """Lock for process map access."""
        if self.__flow_run_process_map_lock is None:
            self.__flow_run_process_map_lock = asyncio.Lock()
        return self.__flow_run_process_map_lock

    # Implementation of abstract methods

    async def _add_execution_entry(
        self,
        flow_run: "FlowRun",
        handle: Union[anyio.abc.Process, multiprocessing.context.SpawnProcess],
    ) -> None:
        """Add a process tracking entry."""
        async with self._flow_run_process_map_lock:
            if handle.pid is None:
                raise RuntimeError("Process has no PID")

            self._flow_run_process_map[flow_run.id] = ProcessMapEntry(
                pid=handle.pid, flow_run=flow_run
            )

            if TYPE_CHECKING:
                assert self._cancelling_observer is not None
            self._cancelling_observer.add_in_flight_flow_run_id(flow_run.id)

    async def _remove_execution_entry(self, flow_run_id: UUID) -> None:
        """Remove a process tracking entry."""
        async with self._flow_run_process_map_lock:
            self._flow_run_process_map.pop(flow_run_id, None)

            if TYPE_CHECKING:
                assert self._cancelling_observer is not None
            self._cancelling_observer.remove_in_flight_flow_run_id(flow_run_id)

    async def _get_execution_handle(
        self, flow_run_id: UUID
    ) -> Optional[Union[anyio.abc.Process, multiprocessing.context.SpawnProcess]]:
        """Get the process handle for a flow run (returns PID for cancellation)."""
        # For cancellation purposes, we need the PID
        # Since we can't store the process object (it may not be picklable),
        # we just return None here and use the PID directly from the map
        return None

    async def _get_execution_pid(self, flow_run_id: UUID) -> Optional[int]:
        """Get the PID for a flow run."""
        process_map_entry = self._flow_run_process_map.get(flow_run_id)
        if process_map_entry:
            return process_map_entry.get("pid")
        return None

    async def _get_all_execution_entries(self) -> list[tuple[UUID, "FlowRun"]]:
        """Get all active process entries."""
        return [
            (fid, entry["flow_run"])
            for fid, entry in self._flow_run_process_map.items()
        ]

    async def _cancel_execution(
        self,
        flow_run: "FlowRun",
        handle: Union[anyio.abc.Process, multiprocessing.context.SpawnProcess],
    ) -> None:
        """Cancel a running process."""
        # We need to get the PID from the map since the handle might not be available
        pid = await self._get_execution_pid(flow_run.id)
        if pid is not None:
            await self._kill_process(pid)

    async def _execute_flow_run_impl(
        self,
        flow_run: "FlowRun",
        task_status: anyio.abc.TaskStatus[
            Union[anyio.abc.Process, multiprocessing.context.SpawnProcess]
        ] = anyio.TASK_STATUS_IGNORED,
        entrypoint: str | None = None,
        command: str | None = None,
        cwd: Path | str | None = None,
        env: dict[str, str | None] | None = None,
        stream_output: bool = True,
    ) -> Optional[int]:
        """Execute a flow run in a subprocess."""
        exit_code = await self._run_process(
            flow_run=flow_run,
            task_status=task_status,
            entrypoint=entrypoint,
            command=command,
            cwd=cwd,
            env=env,
            stream_output=stream_output,
        )
        return exit_code

    async def _handle_execution_result(
        self, flow_run: "FlowRun", exit_code: Optional[int]
    ) -> None:
        """Handle the result of process execution."""
        flow_run_logger = self._get_flow_run_logger(flow_run)

        if exit_code:
            help_message = None
            level = logging.ERROR
            if exit_code == -9:
                level = logging.INFO
                help_message = (
                    "This indicates that the process exited due to a SIGKILL signal. "
                    "Typically, this is either caused by manual cancellation or "
                    "high memory usage causing the operating system to "
                    "terminate the process."
                )
            if exit_code == -15:
                level = logging.INFO
                help_message = (
                    "This indicates that the process exited due to a SIGTERM signal. "
                    "Typically, this is caused by manual cancellation."
                )
            elif exit_code == 247:
                help_message = (
                    "This indicates that the process was terminated due to high "
                    "memory usage."
                )
            elif sys.platform == "win32" and exit_code == STATUS_CONTROL_C_EXIT:
                level = logging.INFO
                help_message = (
                    "Process was terminated due to a Ctrl+C or Ctrl+Break signal. "
                    "Typically, this is caused by manual cancellation."
                )

            flow_run_logger.log(
                level,
                f"Process for flow run {flow_run.name!r} exited with status code:"
                f" {exit_code}" + (f"; {help_message}" if help_message else ""),
            )
        else:
            flow_run_logger.info(
                f"Process for flow run {flow_run.name!r} exited cleanly."
            )

        if exit_code != 0 and not self._rescheduling:
            await self._propose_crashed_state(
                flow_run,
                f"Flow run process exited with non-zero status code {exit_code}.",
            )

        api_flow_run = await self._client.read_flow_run(flow_run_id=flow_run.id)
        terminal_state = api_flow_run.state
        if terminal_state and terminal_state.is_crashed():
            await self._run_on_crashed_hooks(flow_run=flow_run, state=terminal_state)

    # Process-specific methods

    async def execute_flow_run(
        self,
        flow_run_id: UUID,
        entrypoint: str | None = None,
        command: str | None = None,
        cwd: Path | str | None = None,
        env: dict[str, str | None] | None = None,
        task_status: anyio.abc.TaskStatus[int] = anyio.TASK_STATUS_IGNORED,
        stream_output: bool = True,
    ) -> Union[anyio.abc.Process, multiprocessing.context.SpawnProcess, None]:
        """
        Executes a single flow run with the given ID.

        Execution will wait to monitor for cancellation requests. Exits once
        the flow run process has exited.

        Returns:
            The flow run process.
        """
        self.pause_on_shutdown = False
        context = self if not self.started else asyncnullcontext()

        async with context:
            if not self._acquire_limit_slot(flow_run_id):
                return None

            self._submitting_flow_run_ids.add(flow_run_id)
            flow_run = await self._client.read_flow_run(flow_run_id)

            process: Union[
                anyio.abc.Process, multiprocessing.context.SpawnProcess, Exception
            ] = await self._runs_task_group.start(
                partial(
                    self._submit_run_and_capture_errors,
                    flow_run=flow_run,
                    entrypoint=entrypoint,
                    command=command,
                    cwd=cwd,
                    env=env,
                    stream_output=stream_output,
                ),
            )
            if isinstance(process, Exception):
                return None

            if process.pid is None:
                raise RuntimeError("Process has no PID")

            task_status.started(process.pid)

            if self.heartbeat_seconds is not None:
                await self._emit_flow_run_heartbeat(flow_run)

            # Only add the process to the map if it is still running
            if (
                getattr(process, "returncode", None)
                or getattr(process, "exitcode", None)
            ) is None:
                await self._add_execution_entry(flow_run, process)

            while True:
                # Wait until flow run execution is complete
                await anyio.sleep(0.1)
                if self._flow_run_process_map.get(flow_run.id) is None:
                    break

            return process

    async def execute_bundle(
        self,
        bundle: Any,
        cwd: Path | str | None = None,
        env: dict[str, str | None] | None = None,
    ) -> None:
        """
        Executes a bundle in a subprocess.
        """
        from prefect.client.schemas.objects import FlowRun

        self.pause_on_shutdown = False
        context = self if not self.started else asyncnullcontext()

        flow_run = FlowRun.model_validate(bundle["flow_run"])

        async with context:
            if not self._acquire_limit_slot(flow_run.id):
                return

            process = execute_bundle_in_subprocess(bundle, cwd=cwd, env=env)

            if process.pid is None:
                msg = "Failed to start process for flow execution. No PID returned."
                await self._propose_crashed_state(flow_run, msg)
                raise RuntimeError(msg)

            if self.heartbeat_seconds is not None:
                await self._emit_flow_run_heartbeat(flow_run)

            await self._add_execution_entry(flow_run, process)
            self._flow_run_bundle_map[flow_run.id] = bundle

            await anyio.to_thread.run_sync(process.join)

            await self._remove_execution_entry(flow_run.id)

            flow_run_logger = self._get_flow_run_logger(flow_run)
            if process.exitcode is None:
                raise RuntimeError("Process has no exit code")

            if process.exitcode:
                help_message = None
                level = logging.ERROR
                if process.exitcode == -9:
                    level = logging.INFO
                    help_message = (
                        "This indicates that the process exited due to a SIGKILL signal. "
                        "Typically, this is either caused by manual cancellation or "
                        "high memory usage causing the operating system to "
                        "terminate the process."
                    )
                if process.exitcode == -15:
                    level = logging.INFO
                    help_message = (
                        "This indicates that the process exited due to a SIGTERM signal. "
                        "Typically, this is caused by manual cancellation."
                    )
                elif process.exitcode == 247:
                    help_message = (
                        "This indicates that the process was terminated due to high "
                        "memory usage."
                    )
                elif (
                    sys.platform == "win32"
                    and process.exitcode == STATUS_CONTROL_C_EXIT
                ):
                    level = logging.INFO
                    help_message = (
                        "Process was terminated due to a Ctrl+C or Ctrl+Break signal. "
                        "Typically, this is caused by manual cancellation."
                    )

                flow_run_logger.log(
                    level,
                    f"Process for flow run {flow_run.name!r} exited with status code:"
                    f" {process.exitcode}"
                    + (f"; {help_message}" if help_message else ""),
                )
                terminal_state = await self._propose_crashed_state(
                    flow_run, help_message or "Process exited with non-zero exit code"
                )
                if terminal_state:
                    await self._run_on_crashed_hooks(
                        flow_run=flow_run, state=terminal_state
                    )
            else:
                flow_run_logger.info(
                    f"Process for flow run {flow_run.name!r} exited cleanly."
                )

    async def _run_process(
        self,
        flow_run: "FlowRun",
        task_status: anyio.abc.TaskStatus[
            Union[anyio.abc.Process, multiprocessing.context.SpawnProcess]
        ] = anyio.TASK_STATUS_IGNORED,
        entrypoint: str | None = None,
        command: str | None = None,
        cwd: Path | str | None = None,
        env: dict[str, str | None] | None = None,
        stream_output: bool = True,
    ) -> Optional[int]:
        """
        Runs the given flow run in a subprocess.

        Args:
            flow_run: Flow run to execute via process.
            task_status: anyio task status used to send a message to the caller
                that the flow run process has started.
        """
        # If we have an instance of the flow for this deployment, run it directly
        if flow_run.deployment_id is not None:
            flow = self._deployment_flow_map.get(flow_run.deployment_id)
            if flow:
                process = run_flow_in_subprocess(flow, flow_run=flow_run)
                task_status.started(process)
                await anyio.to_thread.run_sync(process.join)
                return process.exitcode

        # Otherwise, run via prefect.engine
        if command is None:
            runner_command = [get_sys_executable(), "-m", "prefect.engine"]
        else:
            runner_command = shlex.split(command, posix=(os.name != "nt"))

        flow_run_logger = self._get_flow_run_logger(flow_run)

        kwargs: dict[str, object] = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        flow_run_logger.info("Opening process...")

        if env is None:
            env = {}
        env.update(get_current_settings().to_environment_variables(exclude_unset=True))
        env.update(
            {
                **{
                    "PREFECT__FLOW_RUN_ID": str(flow_run.id),
                    "PREFECT__STORAGE_BASE_PATH": str(self._tmp_dir),
                    "PREFECT__ENABLE_CANCELLATION_AND_CRASHED_HOOKS": "false",
                },
                **({" PREFECT__FLOW_ENTRYPOINT": entrypoint} if entrypoint else {}),
            }
        )
        env.update(**os.environ)

        storage = (
            self._deployment_storage_map.get(flow_run.deployment_id)
            if flow_run.deployment_id
            else None
        )
        if storage and storage.pull_interval:
            # perform an adhoc pull of code before running the flow
            last_adhoc_pull = getattr(storage, "last_adhoc_pull", None)
            if (
                last_adhoc_pull is None
                or last_adhoc_pull
                < datetime.datetime.now()
                - datetime.timedelta(seconds=storage.pull_interval)
            ):
                self._logger.debug(
                    "Performing adhoc pull of code for flow run %s with storage %r",
                    flow_run.id,
                    storage,
                )
                await storage.pull_code()
                setattr(storage, "last_adhoc_pull", datetime.datetime.now())

        process = await run_process(
            command=runner_command,
            stream_output=stream_output,
            task_status=task_status,
            task_status_handler=lambda process: process,
            env=env,
            cwd=storage.destination if storage else cwd,
            **kwargs,
        )

        return process.returncode

    async def _kill_process(
        self,
        pid: int,
        grace_seconds: int = 30,
    ):
        """
        Kills a given flow run process.

        Args:
            pid: ID of the process to kill
            grace_seconds: Number of seconds to wait for the process to end.
        """
        if sys.platform == "win32":
            try:
                os.kill(pid, signal.CTRL_BREAK_EVENT)
            except (ProcessLookupError, WindowsError):
                raise RuntimeError(
                    f"Unable to kill process {pid!r}: The process was not found."
                )
        else:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                raise RuntimeError(
                    f"Unable to kill process {pid!r}: The process was not found."
                )

            check_interval = max(grace_seconds / 10, 1)

            with anyio.move_on_after(grace_seconds):
                while True:
                    await anyio.sleep(check_interval)

                    try:
                        os.kill(pid, 0)
                    except ProcessLookupError:
                        return

            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                return

    def reschedule_current_flow_runs(
        self,
    ) -> None:
        """
        Reschedules all flow runs that are currently running.

        This should only be called when the runner is shutting down.
        """
        self._rescheduling = True
        with get_client(sync_client=True) as client:
            self._logger.info("Rescheduling flow runs...")
            for process_info in self._flow_run_process_map.values():
                flow_run = process_info["flow_run"]
                run_logger = self._get_flow_run_logger(flow_run)
                run_logger.info(
                    "Rescheduling flow run for resubmission in response to SIGTERM"
                )
                try:
                    propose_state_sync(client, AwaitingRetry(), flow_run_id=flow_run.id)
                    os.kill(process_info["pid"], signal.SIGTERM)
                    run_logger.info("Rescheduled flow run for resubmission")
                except ProcessLookupError:
                    pass
                except Abort as exc:
                    run_logger.info(
                        (
                            "Aborted submission of flow run. "
                            f"Server sent an abort signal: {exc}"
                        ),
                    )
                except Exception:
                    run_logger.exception(
                        "Failed to reschedule flow run",
                    )
