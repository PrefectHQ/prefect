from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import anyio
import anyio.abc

from prefect.logging import get_logger
from prefect.runner._exit_code_interpreter import interpret_exit_code

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient
    from prefect.client.schemas.objects import FlowRun
    from prefect.runner._cancellation_manager import CancellationManager
    from prefect.runner._hook_runner import HookRunner
    from prefect.runner._limit_manager import LimitManager
    from prefect.runner._process_manager import ProcessHandle, ProcessManager
    from prefect.runner._state_proposer import StateProposer


class ProcessStarter(Protocol):
    """Structural typing interface for process-starting strategies.

    Any object with a conforming `.start()` signature qualifies -- no
    inheritance required. Test doubles can use simple AsyncMock or a plain
    async function.

    Contract for `start()`:
    - Call `task_status.started(handle)` BEFORE blocking (signals caller that
      `ProcessHandle` is available before process completes)
    - Block until process exits
    - Return None after process exits
    """

    async def start(
        self,
        flow_run: FlowRun,
        task_status: anyio.abc.TaskStatus[ProcessHandle] = anyio.TASK_STATUS_IGNORED,
    ) -> None: ...


class FlowRunExecutor:
    """Owns full lifecycle for a single flow run execution.

    Constructed fresh per run by the factory above it (Poller or Runner facade).
    Not a pool — one instance per run, discarded after `submit()` completes.

    Lifecycle in `submit()`:
    1. acquire_slot  — raises `WouldBlock` if at capacity (caller handles)
    2. propose_pending — returns False -> release slot, return early
    3. already-cancelled precheck — log skip, release slot, return early
    4. start process via starter — `task_status.started(handle)` signals caller early
    5. add handle to `process_manager`
    6. await process exit (via `runs_task_group.start` which blocks until starter finishes)
    7. release slot (in finally — BEFORE hooks/state)
    8. remove handle from `process_manager` (in finally)
    9. interpret exit code -> propose terminal state (crashed) if non-zero
    10. run crashed hooks if exit was non-zero

    ASYNCEXITSTACK 6-STEP DEPENDENCY ORDER (for Phase 5 `Runner.__aenter__`):
    Entry order (LIFO teardown is exact reverse):
    1. client           -> exits LAST  (underlying connection, needed by all)
    2. process_manager  -> exits 5th   (kills remaining after runs finish)
    3. limit_manager    -> exits 4th   (no deps after runs finish)
    4. event_emitter    -> exits 3rd   (flush events before client closes)
    5. runs_task_group  -> exits 2nd   (wait for in-flight runs)
    6. cancellation_manager -> exits FIRST (stop detection against partial teardown)
    """

    def __init__(
        self,
        *,
        flow_run: FlowRun,
        starter: ProcessStarter,
        process_manager: ProcessManager,
        limit_manager: LimitManager,
        state_proposer: StateProposer,
        hook_runner: HookRunner,
        cancellation_manager: CancellationManager,
        runs_task_group: anyio.abc.TaskGroup,
        client: PrefectClient,
    ) -> None:
        self._flow_run = flow_run
        self._starter = starter
        self._process_manager = process_manager
        self._limit_manager = limit_manager
        self._state_proposer = state_proposer
        self._hook_runner = hook_runner
        self._cancellation_manager = cancellation_manager
        self._runs_task_group = runs_task_group
        self._client = client
        self._logger = get_logger("runner.flow_run_executor")

    async def submit(
        self,
        task_status: anyio.abc.TaskStatus[ProcessHandle] = anyio.TASK_STATUS_IGNORED,
    ) -> None:
        """Execute the full run lifecycle. Returns None.

        Designed to be called via `task_group.start(executor.submit)` so the caller
        receives the `ProcessHandle` before the process exits.
        """
        # Step 1: acquire slot
        try:
            slot_token = self._limit_manager.acquire()
        except anyio.WouldBlock:
            self._logger.debug(
                "No concurrency slots available for flow run '%s'",
                self._flow_run.id,
            )
            return

        handle: ProcessHandle | None = None
        try:
            # Step 2: propose pending — abort if server rejects
            if not await self._state_proposer.propose_pending(self._flow_run):
                return

            # Step 3: already-cancelled precheck
            if self._flow_run.state and self._flow_run.state.is_cancelled():
                self._logger.info(
                    "Flow run '%s' is already in Cancelled state, skipping.",
                    self._flow_run.id,
                )
                return

            # Steps 4-6: start process via starter; get handle
            # runs_task_group.start blocks until task_status.started(handle)
            # fires inside the starter, then continues blocking until process exits
            handle = await self._runs_task_group.start(
                self._starter.start, self._flow_run
            )

            # Signal outer caller with handle (before process exits)
            if handle is not None:
                task_status.started(handle)
                await self._process_manager.add(self._flow_run.id, handle)

        except Exception as exc:
            self._logger.exception(
                "Flow run '%s' could not start: %s",
                self._flow_run.id,
                exc,
            )
            await self._state_proposer.propose_crashed(
                self._flow_run,
                message=f"Flow run could not start: {exc}",
            )
            return
        finally:
            # Step 7: release slot BEFORE hooks/state (always — even on exception)
            self._limit_manager.release(slot_token)
            # Step 8: remove handle from process_manager
            if handle is not None:
                await self._process_manager.remove(self._flow_run.id)

        # Step 9: interpret exit code and propose terminal state
        exit_code = handle.returncode if handle else None
        if exit_code is not None and exit_code != 0:
            result = interpret_exit_code(exit_code)
            msg = f"Process exited with status code: {exit_code}"
            if result.help_message:
                msg += f". {result.help_message}"
            self._logger.log(
                result.level, msg, extra={"flow_run_id": self._flow_run.id}
            )
            if result.is_crash:
                crashed_state = await self._state_proposer.propose_crashed(
                    self._flow_run, message=msg
                )
                # Step 10: run crashed hooks
                if crashed_state is not None:
                    await self._hook_runner.run_crashed_hooks(
                        self._flow_run, crashed_state
                    )
