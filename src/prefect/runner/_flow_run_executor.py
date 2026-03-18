from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import anyio
import anyio.abc

from prefect.logging import get_logger
from prefect.utilities._infrastructure_exit_codes import get_infrastructure_exit_info

if TYPE_CHECKING:
    from prefect.client.schemas.objects import FlowRun
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
    ) -> None:
        self._flow_run = flow_run
        self._starter = starter
        self._process_manager = process_manager
        self._state_proposer = state_proposer
        self._hook_runner = hook_runner
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

        except anyio.get_cancelled_exc_class():
            if self._process_manager.get(self._flow_run.id) is not None:
                with anyio.CancelScope(shield=True):
                    await self._state_proposer.propose_crashed(
                        self._flow_run,
                        message="Flow run process exited due to worker shutdown.",
                    )
            raise
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
            if handle is not None or self._process_manager.get(self._flow_run.id):
                await self._process_manager.remove(self._flow_run.id)

        # Step 7: interpret exit code and propose terminal state
        exit_code = handle.returncode if handle else None
        if exit_code is not None and exit_code != 0:
            info = get_infrastructure_exit_info(exit_code)
            msg = f"Process exited with status code: {exit_code}. {info.explanation}"
            self._logger.log(
                info.log_level, msg, extra={"flow_run_id": self._flow_run.id}
            )
            if info.resolution:
                self._logger.info(
                    info.resolution,
                    extra={"flow_run_id": self._flow_run.id},
                )
            crashed_state = await self._state_proposer.propose_crashed(
                self._flow_run, message=msg
            )
            # Step 8: run crashed hooks
            if crashed_state is not None:
                await self._hook_runner.run_crashed_hooks(self._flow_run, crashed_state)

    async def _start_process(
        self,
        outer_task_status: anyio.abc.TaskStatus[ProcessHandle],
    ) -> ProcessHandle:
        """Start the process and block until it exits.

        Uses an inner task group so that the handle is registered in
        ProcessManager while the process is still alive (not after exit).
        The inner task group's `start()` returns when the starter calls
        `task_status.started(handle)`, at which point we register the
        handle and forward it to the outer caller.  The inner task group
        then waits for the starter coroutine to complete (process exits).

        Returns the `ProcessHandle` after the process has exited.
        """
        captured_handle: ProcessHandle | None = None

        async def _run_starter(
            *, task_status: anyio.abc.TaskStatus[ProcessHandle]
        ) -> None:
            await self._starter.start(self._flow_run, task_status=task_status)

        async with anyio.create_task_group() as inner_tg:
            # inner_tg.start() returns when starter calls task_status.started(handle)
            captured_handle = await inner_tg.start(_run_starter)

            # Handle is now available; process is still running
            await self._process_manager.add(self._flow_run.id, captured_handle)
            outer_task_status.started(captured_handle)

            # inner_tg waits for _run_starter to complete (process exits)

        assert captured_handle is not None, (
            "Starter did not call task_status.started() -- violates ProcessStarter contract"
        )
        return captured_handle
