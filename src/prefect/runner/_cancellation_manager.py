from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING

from prefect.logging import get_logger

if TYPE_CHECKING:
    from uuid import UUID

    from prefect.client.orchestration import PrefectClient
    from prefect.client.schemas.objects import FlowRun
    from prefect.runner._control_channel import ControlChannel
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
        control_channel: ControlChannel | None = None,
    ) -> None:
        self._process_manager = process_manager
        self._hook_runner = hook_runner
        self._state_proposer = state_proposer
        self._event_emitter = event_emitter
        self._client = client
        self._control_channel = control_channel
        self._logger = get_logger("runner.cancellation_manager")

    async def _finalize_cancelled_state(
        self,
        flow_run: FlowRun,
        state_updates: dict[str, object] | None = None,
    ) -> bool:
        """Persist a terminal state after a cancelled child exits.

        Returns `True` if the run is durably `Cancelled`. If that cannot be
        verified, a terminal `Crashed` fallback is proposed so the flow run is
        not left stranded in `Cancelling` after the process has already exited.
        """
        try:
            await self._state_proposer.propose_cancelled(flow_run, state_updates)
        except Exception:
            self._logger.exception(
                "Failed to persist Cancelled state for flow run '%s'.",
                flow_run.id,
            )
        else:
            return True

        try:
            current_run = await self._client.read_flow_run(flow_run.id)
        except Exception:
            self._logger.exception(
                "Failed to verify terminal cancellation state for flow run '%s'.",
                flow_run.id,
            )
        else:
            current_state = current_run.state
            if current_state is not None and current_state.is_cancelled():
                return True
            if current_state is not None and current_state.is_final():
                self._logger.warning(
                    "Flow run '%s' exited after cancellation but finalized as %s"
                    " instead of Cancelled; not emitting a cancelled event.",
                    flow_run.id,
                    current_state.type.value,
                )
                return False

        await self._state_proposer.propose_crashed(
            flow_run,
            message=(
                "Flow run process exited after a cancellation request, but the"
                " runner could not durably persist a Cancelled terminal state."
            ),
        )
        return False

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

        # Deliver cancel intent over the control channel BEFORE killing the
        # process. On POSIX, an ack only means "intent recorded and SIGTERM
        # bridge armed"; the runner's real `SIGTERM` remains the actual
        # cancellation trigger, so we should kill immediately after an ack.
        # On Windows, an ack means the child has queued a local
        # `_thread.interrupt_main(SIGTERM)`, so we can give it a bounded
        # grace window to self-exit before falling back to the external kill
        # path.
        acked = False
        grace_seconds = 30.0
        if self._control_channel is not None:
            try:
                acked = await self._control_channel.signal(flow_run.id, "cancel")
                if not acked:
                    self._logger.debug(
                        "Cancel intent for flow run '%s' was not acked on the"
                        " control channel; proceeding with forced kill.",
                        flow_run.id,
                    )
            except Exception:
                self._logger.exception(
                    "Failed to deliver cancel intent for flow run '%s' on the"
                    " control channel; proceeding with forced kill.",
                    flow_run.id,
                )

        try:
            exited_after_ack = False
            remaining_grace = grace_seconds
            if acked and os.name == "nt":
                wait_started = time.monotonic()
                exited_after_ack = await self._process_manager.wait_for_exit(
                    flow_run.id, grace_seconds=grace_seconds
                )
                remaining_grace = max(
                    0.0, grace_seconds - (time.monotonic() - wait_started)
                )
                if not exited_after_ack:
                    self._logger.debug(
                        "Flow run '%s' did not exit within the graceful"
                        " cancellation window after ack; proceeding with"
                        " forced kill.",
                        flow_run.id,
                    )
            if not exited_after_ack:
                await self._process_manager.kill(
                    flow_run.id, grace_seconds=remaining_grace
                )
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

        cancelled = await self._finalize_cancelled_state(
            flow_run,
            state_updates={
                "message": state_msg or "Flow run was cancelled successfully."
            },
        )

        if cancelled:
            flow, deployment = await self._event_emitter.get_flow_and_deployment(
                flow_run
            )
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
