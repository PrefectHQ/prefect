from __future__ import annotations

from contextlib import AsyncExitStack
from typing import TYPE_CHECKING, Callable, Protocol
from uuid import UUID

import anyio
import anyio.abc

from prefect._observers import FlowRunCancellingObserver
from prefect.client.orchestration import PrefectClient, get_client
from prefect.logging import get_logger
from prefect.runner._cancellation_manager import CancellationManager
from prefect.runner._event_emitter import EventEmitter
from prefect.runner._hook_runner import HookRunner
from prefect.runner._process_manager import ProcessHandle, ProcessManager
from prefect.runner._state_proposer import StateProposer
from prefect.settings.context import get_current_settings
from prefect.utilities._infrastructure_exit_codes import get_infrastructure_exit_info

if TYPE_CHECKING:
    from prefect.client.schemas.objects import FlowRun
    from prefect.flows import Flow


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
    1. propose_submitting — returns False -> return early
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
        propose_submitting: bool = True,
    ) -> None:
        self._flow_run = flow_run
        self._starter = starter
        self._process_manager = process_manager
        self._state_proposer = state_proposer
        self._hook_runner = hook_runner
        self._propose_submitting = propose_submitting
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
            # Step 1: propose submitting — abort if server rejects
            if self._propose_submitting:
                if not await self._state_proposer.propose_submitting(self._flow_run):
                    # If the run is already cancelling, move it to terminal Cancelled
                    if self._flow_run.state and self._flow_run.state.is_cancelling():
                        self._logger.info(
                            "Flow run '%s' is cancelling, marking as cancelled.",
                            self._flow_run.id,
                        )
                        await self._state_proposer.propose_cancelled(
                            self._flow_run,
                            state_updates={
                                "message": "Flow run was cancelled before execution started."
                            },
                        )
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


async def _placeholder_resolve_flow(flow_run: "FlowRun") -> "Flow":
    raise RuntimeError("resolve_flow not configured — call create_executor() first")


class FlowRunExecutorContext:
    """Async context manager for standalone FlowRunExecutor usage (outside Runner).

    Manages lifecycle of shared components: client, ProcessManager, StateProposer,
    EventEmitter, CancellationManager, and FlowRunCancellingObserver.
    The Runner manages these itself; this class is for one-shot execution paths
    (bundle execution, CLI `prefect flow-run execute`).
    """

    client: PrefectClient
    process_manager: ProcessManager

    async def __aenter__(self) -> FlowRunExecutorContext:
        self._stack = AsyncExitStack()
        await self._stack.__aenter__()
        self._logger = get_logger("runner.executor_context")

        # Step 1: client
        self.client = get_client()
        await self._stack.enter_async_context(self.client)

        # Create observer object early so we can wire ProcessManager callbacks.
        # on_cancelling lambda captures self._cancellation_manager (assigned in step 4).
        self._observer = FlowRunCancellingObserver(
            on_cancelling=lambda frid: self._cancellation_task_group.start_soon(
                self._cancellation_manager.cancel_by_id, frid
            ),
            on_failure=lambda flow_run_ids: self._handle_cancellation_observer_failure(
                flow_run_ids
            ),
        )

        # Step 2: ProcessManager with observer add/remove callbacks
        async def _on_add(flow_run_id: UUID) -> None:
            self._observer.add_in_flight_flow_run_id(flow_run_id)

        async def _on_remove(flow_run_id: UUID) -> None:
            self._observer.remove_in_flight_flow_run_id(flow_run_id)

        self.process_manager = ProcessManager(on_add=_on_add, on_remove=_on_remove)
        await self._stack.enter_async_context(self.process_manager)

        # Step 3: StateProposer, placeholder HookRunner, EventEmitter
        self._state_proposer = StateProposer(client=self.client)
        self._hook_runner = HookRunner(resolve_flow=_placeholder_resolve_flow)
        self._event_emitter = EventEmitter(runner_name="standalone", client=self.client)
        await self._stack.enter_async_context(self._event_emitter)

        # Step 3.5: Task group to track in-flight cancellation tasks
        self._cancellation_task_group = await self._stack.enter_async_context(
            anyio.create_task_group()
        )

        # Step 4: CancellationManager
        self._cancellation_manager = CancellationManager(
            process_manager=self.process_manager,
            hook_runner=self._hook_runner,
            state_proposer=self._state_proposer,
            event_emitter=self._event_emitter,
            client=self.client,
        )

        # Step 5: Observer enters LAST (starts websocket/polling)
        await self._stack.enter_async_context(self._observer)

        return self

    async def __aexit__(self, *exc_info: object) -> bool | None:
        return await self._stack.__aexit__(*exc_info)

    def _handle_cancellation_observer_failure(self, flow_run_ids: set) -> None:
        """Handle failure of both cancellation observer mechanisms.

        When crash_on_cancellation_failure is enabled, kills all in-flight
        processes (which triggers crash handling when they terminate).
        Otherwise, logs a warning.
        """
        will_crash = get_current_settings().runner.crash_on_cancellation_failure
        if will_crash:
            self._logger.error(
                "Cancellation observing failed — killing %d in-flight flow run(s).",
                len(flow_run_ids),
            )
            for flow_run_id in flow_run_ids:
                self._cancellation_task_group.start_soon(
                    self.process_manager.kill, flow_run_id
                )
        else:
            self._logger.warning(
                "Cancellation observer failed. Flow run cancellation disabled. "
                "Set PREFECT_RUNNER_CRASH_ON_CANCELLATION_FAILURE=true to "
                "crash flow runs when this occurs."
            )

    def create_executor(
        self,
        flow_run: FlowRun,
        starter: ProcessStarter,
        resolve_flow: Callable[[FlowRun], Flow[..., ...]],
        propose_submitting: bool = True,
    ) -> FlowRunExecutor:
        hook_runner = HookRunner(resolve_flow=resolve_flow)
        # Wire the real resolver into CancellationManager for on_cancellation hooks
        self._cancellation_manager._hook_runner = hook_runner
        return FlowRunExecutor(
            flow_run=flow_run,
            starter=starter,
            process_manager=self.process_manager,
            state_proposer=self._state_proposer,
            hook_runner=hook_runner,
            propose_submitting=propose_submitting,
        )
