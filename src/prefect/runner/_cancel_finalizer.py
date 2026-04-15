from __future__ import annotations

from logging import Logger
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient
    from prefect.client.schemas.objects import FlowRun
    from prefect.runner._state_proposer import StateProposer


async def finalize_cancelled_state(
    *,
    flow_run: FlowRun,
    state_proposer: StateProposer,
    client: PrefectClient,
    logger: Logger,
    state_updates: dict[str, Any] | None = None,
) -> bool:
    """Persist Cancelled if possible, otherwise force some terminal state.

    Returns `True` when the flow run is durably `Cancelled`. If the runner
    cannot verify that outcome after the child process has already exited,
    it falls back to a terminal `Crashed` state so the run is not left in
    `Cancelling` with no live infrastructure.
    """
    propose_cancelled_succeeded = False
    try:
        propose_cancelled_succeeded = await state_proposer.propose_cancelled(
            flow_run, state_updates
        )
    except Exception:
        logger.exception(
            "Failed to persist Cancelled state for flow run '%s'.",
            flow_run.id,
        )

    if propose_cancelled_succeeded:
        return True

    try:
        current_run = await client.read_flow_run(flow_run.id)
    except Exception:
        logger.exception(
            "Failed to verify terminal cancellation state for flow run '%s'.",
            flow_run.id,
        )
    else:
        current_state = current_run.state
        if current_state is not None and current_state.is_cancelled():
            return True
        if current_state is not None and current_state.is_final():
            logger.warning(
                "Flow run '%s' exited after cancellation but finalized as %s"
                " instead of Cancelled; not emitting a cancelled event.",
                flow_run.id,
                current_state.type.value,
            )
            return False

    await state_proposer.propose_crashed(
        flow_run,
        message=(
            "Flow run process exited after a cancellation request, but the"
            " runner could not durably persist a Cancelled terminal state."
        ),
    )
    return False


async def should_skip_cancel_after_acked_process_exit(
    *,
    flow_run: FlowRun,
    client: PrefectClient,
    logger: Logger,
) -> bool:
    """Return whether cancellation finalization should be skipped.

    On POSIX, an acked child can still exit normally in the narrow window
    between the control-channel ack and the runner's subsequent SIGTERM. If
    the process is already gone when the runner tries to send SIGTERM, do not
    force `Cancelled` over an already-final run.
    """

    try:
        current_run = await client.read_flow_run(flow_run.id)
    except Exception:
        logger.exception(
            "Failed to verify flow run state after the process disappeared"
            " during an acked cancellation for flow run '%s'.",
            flow_run.id,
        )
        return False

    current_state = current_run.state
    if current_state is not None and current_state.is_final():
        logger.info(
            "Flow run '%s' was already finalized as %s before the runner"
            " could deliver SIGTERM after cancellation ack; skipping"
            " cancellation finalization.",
            flow_run.id,
            current_state.type.value,
        )
        return True

    return False
