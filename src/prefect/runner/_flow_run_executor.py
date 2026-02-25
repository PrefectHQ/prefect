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

    Concurrency slot management is the caller's responsibility (e.g.
    `ScheduledRunPoller` acquires before spawning and releases after the
    process exits).  This class does not interact with `LimitManager`.

    Lifecycle in `submit()`:
    1. propose_pending — returns False -> return early
    2. already-cancelled precheck — log skip, return early
    3. start process via starter — `task_status.started(handle)` signals caller early
    4. add handle to `process_manager`
    5. block until process exits (starter.start blocks after signaling started)
    6. remove handle from `process_manager` (in finally)
    7. interpret exit code -> propose terminal state (crashed) if non-zero
    8. run crashed hooks if exit was non-zero

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
        state_proposer: StateProposer,
        hook_runner: HookRunner,
        cancellation_manager: CancellationManager,
        runs_task_group: anyio.abc.TaskGroup,
        client: PrefectClient,
    ) -> None:
        self._flow_run = flow_run
        self._starter = starter
        self._process_manager = process_manager
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

        Designed to be called via `runs_task_group.start(executor.submit)` so
        the caller receives the `ProcessHandle` before the process exits.

        The starter's `start()` method calls `task_status.started(handle)`
        before blocking until the process exits.  We wrap the outer
        `task_status` so that we can both forward the handle to the caller
        AND capture it locally for exit-code inspection after the process
        exits.
        """
        handle: ProcessHandle | None = None
        try:
            # Step 1: propose pending — abort if server rejects
            if not await self._state_proposer.propose_pending(self._flow_run):
                return

            # Step 2: already-cancelled precheck
            if self._flow_run.state and self._flow_run.state.is_cancelled():
                self._logger.info(
                    "Flow run '%s' is already in Cancelled state, skipping.",
                    self._flow_run.id,
                )
                return

            # Steps 3-5: start process, signal handle early, block until exit.
            #
            # The starter calls task_status.started(handle) BEFORE blocking on
            # process exit (see ProcessStarter contract).  We wrap task_status
            # so that:
            #   a) the handle is forwarded to *our* caller immediately, and
            #   b) we capture it locally for exit-code inspection afterwards.
            #
            # starter.start() blocks until the process exits, so everything
            # after this await runs only once the process is done.
            handle = await self._start_process(task_status)

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
            # Step 6: remove handle from process_manager
            if handle is not None:
                await self._process_manager.remove(self._flow_run.id)

        # Step 7: interpret exit code and propose terminal state
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
                # Step 8: run crashed hooks
                if crashed_state is not None:
                    await self._hook_runner.run_crashed_hooks(
                        self._flow_run, crashed_state
                    )

    async def _start_process(
        self,
        outer_task_status: anyio.abc.TaskStatus[ProcessHandle],
    ) -> ProcessHandle:
        """Start the process and block until it exits.

        Wraps `outer_task_status` so the handle is both forwarded to the
        caller (via `started()`) and captured locally.  Adds the handle
        to `process_manager` immediately after signaling.

        Returns the `ProcessHandle` after the process has exited.
        """
        captured_handle: ProcessHandle | None = None

        class _CapturingTaskStatus:
            """Intercepts `started(handle)` to capture and forward."""

            def started(self, handle: ProcessHandle) -> None:
                nonlocal captured_handle
                captured_handle = handle
                outer_task_status.started(handle)

        # starter.start() signals started(handle) then blocks until exit
        await self._starter.start(
            self._flow_run,
            task_status=_CapturingTaskStatus(),  # type: ignore[arg-type]
        )

        # Register with process_manager while process was alive
        # (add before cleanup so cancellation can find it during the run)
        if captured_handle is not None:
            await self._process_manager.add(self._flow_run.id, captured_handle)

        assert captured_handle is not None, (
            "Starter did not call task_status.started() — violates ProcessStarter contract"
        )
        return captured_handle
