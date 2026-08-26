from __future__ import annotations

import time
from typing import Any, Protocol, TypeVar, cast
from uuid import UUID

import anyio

from prefect.client.schemas import OrchestrationResult
from prefect.client.schemas.responses import (
    SetStateStatus,
    StateAbortDetails,
    StateRejectDetails,
    StateWaitDetails,
)
from prefect.exceptions import Abort, Pause
from prefect.logging.loggers import get_logger
from prefect.states import State

__all__ = ["FlowRunStateProposer", "SyncFlowRunStateProposer"]

T = TypeVar("T")
_proposal_logger = get_logger("engine")


class _FlowRunStateRequest(Protocol):
    """A single asynchronous request to set a flow-run state."""

    async def __call__(
        self,
        flow_run_id: UUID | str,
        state: State[Any],
        force: bool = False,
    ) -> OrchestrationResult[Any]: ...


class _SyncFlowRunStateRequest(Protocol):
    """A single synchronous request to set a flow-run state."""

    def __call__(
        self,
        flow_run_id: UUID | str,
        state: State[Any],
        force: bool = False,
    ) -> OrchestrationResult[Any]: ...


class FlowRunStateProposer:
    """Resolve asynchronous flow-run state proposals through orchestration.

    The bound request performs exactly one server attempt. This proposer owns
    retries after `WAIT` responses and interprets the server's authoritative
    response.
    """

    def __init__(self, request: _FlowRunStateRequest) -> None:
        self._request = request

    async def propose(
        self,
        flow_run_id: UUID,
        state: State[T],
        *,
        force: bool = False,
    ) -> State[T]:
        """Propose `state` until the server returns a non-`WAIT` response."""
        _require_flow_run_id(flow_run_id)

        response = await self._request(flow_run_id, state, force=force)
        while response.status == SetStateStatus.WAIT:
            details = _wait_details(response)
            _proposal_logger.debug(
                "Received wait instruction for %ss: %s",
                details.delay_seconds,
                details.reason,
            )
            await anyio.sleep(details.delay_seconds)
            response = await self._request(flow_run_id, state, force=force)

        return _resolve_response(state, response)


class SyncFlowRunStateProposer:
    """Resolve synchronous flow-run state proposals through orchestration.

    The bound request performs exactly one server attempt. This proposer owns
    retries after `WAIT` responses and interprets the server's authoritative
    response.
    """

    def __init__(self, request: _SyncFlowRunStateRequest) -> None:
        self._request = request

    def propose(
        self,
        flow_run_id: UUID,
        state: State[T],
        *,
        force: bool = False,
    ) -> State[T]:
        """Propose `state` until the server returns a non-`WAIT` response."""
        _require_flow_run_id(flow_run_id)

        response = self._request(flow_run_id, state, force=force)
        while response.status == SetStateStatus.WAIT:
            details = _wait_details(response)
            _proposal_logger.debug(
                "Received wait instruction for %ss: %s",
                details.delay_seconds,
                details.reason,
            )
            time.sleep(details.delay_seconds)
            response = self._request(flow_run_id, state, force=force)

        return _resolve_response(state, response)


def _require_flow_run_id(flow_run_id: UUID) -> None:
    if not flow_run_id:
        raise ValueError("You must provide a `flow_run_id`")


def _wait_details(response: OrchestrationResult[Any]) -> StateWaitDetails:
    if not isinstance(response.details, StateWaitDetails):
        raise TypeError("Received a WAIT response without wait details")
    return response.details


def _resolve_response(
    proposed_state: State[T], response: OrchestrationResult[Any]
) -> State[T]:
    if response.status == SetStateStatus.ACCEPT:
        if response.state is None:
            raise ValueError("Received an ACCEPT response without a state")
        proposed_state.id = response.state.id
        proposed_state.timestamp = response.state.timestamp
        if response.state.state_details:
            proposed_state.state_details = response.state.state_details
        return proposed_state

    if response.status == SetStateStatus.ABORT:
        if not isinstance(response.details, StateAbortDetails):
            raise ValueError("Received an ABORT response without abort details")
        raise Abort(response.details.reason)

    if response.status == SetStateStatus.REJECT:
        if response.state is None or not isinstance(
            response.details, StateRejectDetails
        ):
            raise ValueError("Received a REJECT response without a state and details")
        if response.state.is_paused():
            raise Pause(response.details.reason, state=response.state)
        return cast(State[T], response.state)

    raise ValueError(
        f"Received unexpected `SetStateStatus` from server: {response.status!r}"
    )
