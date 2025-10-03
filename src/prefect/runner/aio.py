"""
Async task-based runner implementation.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

import anyio
import anyio.abc

from prefect._experimental.bundles import extract_flow_from_bundle
from prefect.flow_engine import load_flow_from_flow_run, run_flow_async
from prefect.runner._base import BaseRunner

if TYPE_CHECKING:
    from prefect.client.schemas.objects import FlowRun

__all__ = ["AsyncRunner"]


class AsyncRunner(BaseRunner[anyio.abc.CancelScope]):
    """
    Async task-based runner implementation.

    Runs flows directly in async tasks using anyio task groups instead of
    spawning subprocesses. Use only with async flows.
    """

    def __init__(self, *args: Any, **kwargs: Any):
        """Initialize the async runner."""
        super().__init__(*args, **kwargs)

        # Task-specific tracking
        self._flow_run_task_map: dict[UUID, tuple[anyio.abc.CancelScope, "FlowRun"]] = (
            dict()
        )
        self.__flow_run_task_map_lock: asyncio.Lock | None = None

    @property
    def _flow_run_task_map_lock(self) -> asyncio.Lock:
        """Lock for task map access."""
        if self.__flow_run_task_map_lock is None:
            self.__flow_run_task_map_lock = asyncio.Lock()
        return self.__flow_run_task_map_lock

    # Implementation of abstract methods

    async def _add_execution_entry(
        self, flow_run: "FlowRun", handle: anyio.abc.CancelScope
    ) -> None:
        """Add a task tracking entry."""
        async with self._flow_run_task_map_lock:
            self._flow_run_task_map[flow_run.id] = (handle, flow_run)

            if TYPE_CHECKING:
                assert self._cancelling_observer is not None
            self._cancelling_observer.add_in_flight_flow_run_id(flow_run.id)

    async def _remove_execution_entry(self, flow_run_id: UUID) -> None:
        """Remove a task tracking entry."""
        async with self._flow_run_task_map_lock:
            self._flow_run_task_map.pop(flow_run_id, None)

            if TYPE_CHECKING:
                assert self._cancelling_observer is not None
            self._cancelling_observer.remove_in_flight_flow_run_id(flow_run_id)

    async def _get_all_execution_entries(self) -> list[tuple[UUID, "FlowRun"]]:
        """Get all active task entries."""
        return [
            (fid, flow_run) for fid, (_, flow_run) in self._flow_run_task_map.items()
        ]

    async def _cancel_execution(self, flow_run: "FlowRun") -> None:
        """Cancel a running task."""
        task_map_entry = self._flow_run_task_map.get(flow_run.id)
        if task_map_entry:
            task_map_entry[0].cancel()

    async def _execute_flow_run_impl(
        self,
        flow_run: "FlowRun",
        task_status: anyio.abc.TaskStatus[
            anyio.abc.CancelScope
        ] = anyio.TASK_STATUS_IGNORED,
        entrypoint: str | None = None,
        command: str | None = None,
        cwd: Path | str | None = None,
        env: dict[str, str | None] | None = None,
        stream_output: bool = True,
    ) -> Optional[int]:
        """Execute a flow run directly in an async task."""
        # Signal that we've started with the task's cancel scope
        with anyio.CancelScope() as scope:
            task_status.started(scope)

            # Load the flow
            flow = await self._load_flow(flow_run)
            if not flow:
                self._logger.error(f"Failed to load flow for flow run {flow_run.id}")
                return 1

            flow_run_logger = self._get_flow_run_logger(flow_run)
            flow_run_logger.info("Starting flow run execution in async task...")

            try:
                # Run the flow using the flow engine
                # This will handle the flow run context and state management
                result = await run_flow_async(
                    flow=flow,
                    flow_run=flow_run,
                    parameters=flow_run.parameters or {},
                    return_type="state",
                )

                if result is not None:
                    from prefect.client.schemas.objects import State

                    if isinstance(result, State):
                        flow_run_logger.info(
                            f"Flow run completed with state: {result.type.value}"
                        )

                        # Return 0 for success states, 1 for failure states
                        if result.is_completed() or result.is_final():
                            return 0 if not result.is_failed() else 1
                    else:
                        flow_run_logger.info(
                            f"Flow run completed with result: {type(result).__name__}"
                        )

                return 0  # Default to success

            except asyncio.CancelledError:
                flow_run_logger.info("Flow run was cancelled")
                raise
            except Exception:
                flow_run_logger.exception(
                    f"Flow run {flow_run.id} failed with exception"
                )
                return 1  # Failure

    async def _load_flow(self, flow_run: "FlowRun") -> Any:
        """Load the flow for execution."""
        # Try to get from bundle map first
        if flow_run.id in self._flow_run_bundle_map:
            return extract_flow_from_bundle(self._flow_run_bundle_map[flow_run.id])

        # Try to get from deployment map
        if flow_run.deployment_id and self._deployment_flow_map.get(
            flow_run.deployment_id
        ):
            return self._deployment_flow_map[flow_run.deployment_id]

        # Otherwise load from storage
        self._logger.info(f"Loading flow for flow run {flow_run.id}")
        return await load_flow_from_flow_run(
            flow_run, storage_base_path=str(self._tmp_dir)
        )

    async def _handle_execution_result(
        self, flow_run: "FlowRun", exit_code: Optional[int]
    ) -> None:
        """
        Handle the result of task execution.

        For async runner, exit codes are simpler:
        - 0 = success
        - 1 = failure
        - None = cancelled or unknown
        """
        flow_run_logger = self._get_flow_run_logger(flow_run)

        if exit_code == 0:
            flow_run_logger.info(f"Flow run {flow_run.name!r} completed successfully.")
        elif exit_code == 1:
            flow_run_logger.error(f"Flow run {flow_run.name!r} failed.")
            await self._propose_crashed_state(
                flow_run,
                "Flow run execution failed in async task.",
            )
        elif exit_code is None:
            flow_run_logger.info(
                f"Flow run {flow_run.name!r} was cancelled or did not complete."
            )

        # Check final state and run hooks
        api_flow_run = await self._client.read_flow_run(flow_run_id=flow_run.id)
        terminal_state = api_flow_run.state
        if terminal_state and terminal_state.is_crashed():
            await self._run_on_crashed_hooks(flow_run=flow_run, state=terminal_state)

    async def execute_flow_run(
        self,
        flow_run_id: UUID,
        entrypoint: str | None = None,
        command: str | None = None,
        cwd: Path | str | None = None,
        env: dict[str, str | None] | None = None,
        task_status: anyio.abc.TaskStatus[
            anyio.abc.CancelScope
        ] = anyio.TASK_STATUS_IGNORED,
        stream_output: bool = True,
    ) -> Optional[anyio.abc.CancelScope]:
        """
        Executes a single flow run with the given ID in an async task.

        Returns:
            The cancel scope for the flow run task.
        """
        from prefect.utilities.asyncutils import asyncnullcontext

        self.pause_on_shutdown = False
        context = self if not self.started else asyncnullcontext()

        async with context:
            if not self._acquire_limit_slot(flow_run_id):
                return None

            self._submitting_flow_run_ids.add(flow_run_id)
            flow_run = await self._client.read_flow_run(flow_run_id)

            cancel_scope: (
                anyio.abc.CancelScope | Exception
            ) = await self._runs_task_group.start(
                self._submit_run_and_capture_errors,
                flow_run,
                task_status,
                entrypoint,
                command,
                cwd,
                env,
                stream_output,
            )

            if isinstance(cancel_scope, Exception):
                return None

            task_status.started(cancel_scope)

            if self.heartbeat_seconds is not None:
                await self._emit_flow_run_heartbeat(flow_run)

            # Add the cancel scope to tracking
            await self._add_execution_entry(flow_run, cancel_scope)

            # Wait for completion by checking if it's still in the map
            while True:
                await anyio.sleep(0.1)
                if self._flow_run_task_map.get(flow_run.id) is None:
                    break

            return cancel_scope

    async def execute_bundle(
        self,
        bundle: Any,
        cwd: Path | str | None = None,
        env: dict[str, str | None] | None = None,
    ) -> None:
        """
        Executes a bundle in an async task.
        """
        from prefect.client.schemas.objects import FlowRun
        from prefect.utilities.asyncutils import asyncnullcontext

        self.pause_on_shutdown = False
        context = self if not self.started else asyncnullcontext()

        flow_run = FlowRun.model_validate(bundle["flow_run"])

        async with context:
            if not self._acquire_limit_slot(flow_run.id):
                return

            # Store bundle for later access
            self._flow_run_bundle_map[flow_run.id] = bundle

            # Create a cancel scope for tracking
            with anyio.CancelScope() as cancel_scope:
                if self.heartbeat_seconds is not None:
                    await self._emit_flow_run_heartbeat(flow_run)

                await self._add_execution_entry(flow_run, cancel_scope)

                try:
                    # Execute the flow
                    exit_code = await self._execute_flow_run_impl(
                        flow_run=flow_run,
                        task_status=anyio.TASK_STATUS_IGNORED,
                        cwd=cwd,
                        env=env,
                    )

                    await self._handle_execution_result(flow_run, exit_code)

                finally:
                    await self._remove_execution_entry(flow_run.id)
                    self._flow_run_bundle_map.pop(flow_run.id, None)
