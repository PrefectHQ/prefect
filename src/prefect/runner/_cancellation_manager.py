from __future__ import annotations

from typing import TYPE_CHECKING

from prefect.logging import get_logger

if TYPE_CHECKING:
    from uuid import UUID

    from prefect.client.orchestration import PrefectClient
    from prefect.client.schemas.objects import FlowRun
    from prefect.runner._event_emitter import EventEmitter
    from prefect.runner._hook_runner import HookRunner
    from prefect.runner._process_manager import ProcessManager
    from prefect.runner._state_proposer import StateProposer


class CancellationManager:
    """Executes the kill->hooks->state->event cancellation sequence.

    Pure sequence executor -- does NOT gatekeep. Callers are responsible
    for verifying the run is in a cancellable state before calling `cancel()`.

    Composes: `ProcessManager` (kill), `HookRunner` (cancellation hooks),
    `StateProposer` (`propose_cancelled`), `EventEmitter` (`emit_flow_run_cancelled`).
    """

    def __init__(
        self,
        *,
        process_manager: ProcessManager,
        hook_runner: HookRunner,
        state_proposer: StateProposer,
        event_emitter: EventEmitter,
        client: PrefectClient,
    ) -> None:
        self._process_manager = process_manager
        self._hook_runner = hook_runner
        self._state_proposer = state_proposer
        self._event_emitter = event_emitter
        self._client = client
        self._logger = get_logger("runner.cancellation_manager")

    async def cancel(
        self,
        flow_run: FlowRun,
        state_msg: str | None = None,
    ) -> None:
        """Execute kill->hooks->state->event for a single flow run.

        `ProcessLookupError` (process already gone) is expected -- sequence continues.
        Any other kill exception aborts the sequence (logged at exception level).
        Hook failures are logged as ERROR but state/event always run.
        """
        handle = self._process_manager.get(flow_run.id)
        pid = handle.pid if handle else None
        if not pid:
            self._logger.debug(
                "Received cancellation request for flow run '%s'"
                " but no process was found.",
                flow_run.id,
            )
            return

        try:
            await self._process_manager.kill(flow_run.id)
        except ProcessLookupError:
            self._logger.debug(
                "Process for flow run '%s' was already gone during cancel.",
                flow_run.id,
            )
        except Exception:
            self._logger.exception(
                "Unexpected error killing process for flow run '%s'."
                " Aborting cancellation sequence.",
                flow_run.id,
            )
            return  # Unexpected errors abort; do not proceed to hooks/state/event

        # Hooks: always continue on failure (log and continue pattern)
        if flow_run.state:
            try:
                await self._hook_runner.run_cancellation_hooks(flow_run, flow_run.state)
            except Exception:
                self._logger.exception(
                    "Error running cancellation hooks for flow run '%s'."
                    " Proceeding with state proposal.",
                    flow_run.id,
                )

        # State: propose cancelled (terminal state is non-negotiable)
        await self._state_proposer.propose_cancelled(
            flow_run,
            state_updates={
                "message": state_msg or "Flow run was cancelled successfully."
            },
        )

        # Event: emit
        flow, deployment = await self._event_emitter.get_flow_and_deployment(flow_run)
        await self._event_emitter.emit_flow_run_cancelled(
            flow_run=flow_run, flow=flow, deployment=deployment
        )
        self._logger.info("Cancelled flow run '%s'", flow_run.name)

    async def cancel_by_id(self, flow_run_id: UUID) -> None:
        """Fetch flow run by ID then cancel. Used by FlowRunCancellingObserver callback."""
        flow_run = await self._client.read_flow_run(flow_run_id)
        await self.cancel(flow_run)

    async def cancel_all(self, state_msg: str = "Runner is shutting down.") -> None:
        """Cancel all currently tracked flow runs.

        Snapshots flow run IDs before iterating to avoid RuntimeError
        when `cancel()` triggers `remove()` mid-iteration.
        """
        # Snapshot before iterating -- avoids dict-changed-during-iteration
        flow_run_ids = self._process_manager.flow_run_ids()
        for flow_run_id in flow_run_ids:
            handle = self._process_manager.get(flow_run_id)
            if handle is None:
                continue
            # cancel() needs a FlowRun object; fetch it
            try:
                flow_run = await self._client.read_flow_run(flow_run_id)
                await self.cancel(flow_run, state_msg=state_msg)
            except Exception:
                self._logger.exception(
                    "Exception while cancelling flow run '%s'",
                    flow_run_id,
                )
