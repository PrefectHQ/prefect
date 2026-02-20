from __future__ import annotations

from typing import TYPE_CHECKING, Any

from prefect.exceptions import Abort, ObjectNotFound
from prefect.logging import get_logger
from prefect.states import AwaitingRetry, Crashed, Pending, exception_to_failed_state
from prefect.utilities.engine import propose_state, propose_state_sync

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient, SyncPrefectClient
    from prefect.client.schemas.objects import FlowRun
    from prefect.states import State


class StateProposer:
    """Encapsulates all API state-transition proposals for flow runs.

    Stateless service — no `__aenter__`/`__aexit__`. Dependencies injected via
    keyword-only constructor arguments.
    """

    def __init__(
        self,
        *,
        client: PrefectClient,
    ) -> None:
        self._client = client
        self._logger = get_logger("runner.state_proposer")

    async def propose_pending(self, flow_run: FlowRun) -> bool:
        """Propose Pending state. Returns True if ready to submit, False if aborted/rejected."""
        try:
            state = await propose_state(
                self._client, Pending(), flow_run_id=flow_run.id
            )
        except Abort as exc:
            self._logger.info(
                "Aborted submission of flow run '%s'. Server sent an abort signal: %s",
                flow_run.id,
                exc,
            )
            return False
        except Exception:
            self._logger.exception(
                "Failed to update state of flow run '%s'", flow_run.id
            )
            return False
        if not state.is_pending():
            self._logger.info(
                "Aborted submission of flow run '%s': Server returned a non-pending"
                " state %r",
                flow_run.id,
                state.type.value,
            )
            return False
        return True

    async def propose_crashed(
        self, flow_run: FlowRun, message: str
    ) -> State[Any] | None:
        """Propose Crashed state. Returns new state on success, None otherwise."""
        state = None
        try:
            state = await propose_state(
                self._client, Crashed(message=message), flow_run_id=flow_run.id
            )
        except Abort:
            self._logger.debug(
                "Aborted crash state proposal for flow run '%s'", flow_run.id
            )
        except ObjectNotFound:
            self._logger.debug(
                "Flow run '%s' was deleted before state could be updated", flow_run.id
            )
        except Exception:
            self._logger.exception(
                "Failed to update state of flow run '%s'", flow_run.id
            )
        else:
            if state.is_crashed():
                self._logger.info(
                    "Reported flow run '%s' as crashed: %s", flow_run.id, message
                )
        return state

    async def propose_failed(self, flow_run: FlowRun, exc: Exception) -> None:
        """Propose Failed state. Abort is swallowed (already failed). Logs other errors."""
        try:
            await propose_state(
                self._client,
                await exception_to_failed_state(message="Submission failed.", exc=exc),
                flow_run_id=flow_run.id,
            )
        except Abort:
            self._logger.debug(
                "Aborted failed state proposal for flow run '%s'", flow_run.id
            )
        except Exception:
            self._logger.error(
                "Failed to update state of flow run '%s'",
                flow_run.id,
                exc_info=True,
            )

    def propose_awaiting_retry_sync(
        self,
        flow_run: FlowRun,
        sync_client: SyncPrefectClient,
    ) -> None:
        """Sync method for SIGTERM signal handler boundary.

        Caller creates and manages `sync_client` lifecycle. Exceptions propagate
        to caller — the `handle_sigterm` caller is responsible for catching.
        """
        propose_state_sync(sync_client, AwaitingRetry(), flow_run_id=flow_run.id)
