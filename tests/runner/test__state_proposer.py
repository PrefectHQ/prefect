from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from prefect.exceptions import Abort, ObjectNotFound
from prefect.runner._state_proposer import StateProposer
from prefect.states import AwaitingRetry, Crashed, Pending, Running


def _make_flow_run() -> MagicMock:
    flow_run = MagicMock()
    flow_run.id = uuid4()
    return flow_run


class TestStateProposerProposePending:
    async def test_propose_pending_returns_true_on_success(self):
        client = AsyncMock()
        proposer = StateProposer(client=client)
        flow_run = _make_flow_run()

        with patch(
            "prefect.runner._state_proposer.propose_state",
            new_callable=AsyncMock,
            return_value=Pending(),
        ):
            result = await proposer.propose_pending(flow_run)

        assert result is True

    async def test_propose_pending_returns_false_on_abort(self):
        client = AsyncMock()
        proposer = StateProposer(client=client)
        flow_run = _make_flow_run()

        with patch(
            "prefect.runner._state_proposer.propose_state",
            new_callable=AsyncMock,
            side_effect=Abort("aborted"),
        ):
            result = await proposer.propose_pending(flow_run)

        assert result is False

    async def test_propose_pending_returns_false_on_non_pending_state(self):
        client = AsyncMock()
        proposer = StateProposer(client=client)
        flow_run = _make_flow_run()

        with patch(
            "prefect.runner._state_proposer.propose_state",
            new_callable=AsyncMock,
            return_value=Running(),
        ):
            result = await proposer.propose_pending(flow_run)

        assert result is False

    async def test_propose_pending_returns_false_on_unexpected_exception(self):
        client = AsyncMock()
        proposer = StateProposer(client=client)
        flow_run = _make_flow_run()

        with patch(
            "prefect.runner._state_proposer.propose_state",
            new_callable=AsyncMock,
            side_effect=RuntimeError("unexpected"),
        ):
            result = await proposer.propose_pending(flow_run)

        assert result is False


class TestStateProposerProposeCrashed:
    async def test_propose_crashed_returns_state_on_success(self):
        client = AsyncMock()
        proposer = StateProposer(client=client)
        flow_run = _make_flow_run()
        crashed_state = Crashed(message="boom")

        with patch(
            "prefect.runner._state_proposer.propose_state",
            new_callable=AsyncMock,
            return_value=crashed_state,
        ):
            result = await proposer.propose_crashed(flow_run, "boom")

        assert result is crashed_state

    async def test_propose_crashed_returns_none_on_abort(self):
        client = AsyncMock()
        proposer = StateProposer(client=client)
        flow_run = _make_flow_run()

        with patch(
            "prefect.runner._state_proposer.propose_state",
            new_callable=AsyncMock,
            side_effect=Abort("aborted"),
        ):
            result = await proposer.propose_crashed(flow_run, "boom")

        assert result is None

    async def test_propose_crashed_returns_none_on_object_not_found(self):
        client = AsyncMock()
        proposer = StateProposer(client=client)
        flow_run = _make_flow_run()

        with patch(
            "prefect.runner._state_proposer.propose_state",
            new_callable=AsyncMock,
            side_effect=ObjectNotFound("not found"),
        ):
            result = await proposer.propose_crashed(flow_run, "boom")

        assert result is None

    async def test_propose_crashed_returns_none_on_unexpected_exception(self):
        client = AsyncMock()
        proposer = StateProposer(client=client)
        flow_run = _make_flow_run()

        with patch(
            "prefect.runner._state_proposer.propose_state",
            new_callable=AsyncMock,
            side_effect=RuntimeError("unexpected"),
        ):
            result = await proposer.propose_crashed(flow_run, "boom")

        assert result is None


class TestStateProposerProposeFailed:
    async def test_propose_failed_calls_propose_state(self):
        client = AsyncMock()
        proposer = StateProposer(client=client)
        flow_run = _make_flow_run()
        exc = RuntimeError("submit failed")
        mock_failed_state = MagicMock()

        with (
            patch(
                "prefect.runner._state_proposer.propose_state",
                new_callable=AsyncMock,
            ) as mock_propose,
            patch(
                "prefect.runner._state_proposer.exception_to_failed_state",
                new_callable=AsyncMock,
                return_value=mock_failed_state,
            ),
        ):
            await proposer.propose_failed(flow_run, exc)

        mock_propose.assert_awaited_once()

    async def test_propose_failed_swallows_abort(self):
        client = AsyncMock()
        proposer = StateProposer(client=client)
        flow_run = _make_flow_run()
        exc = RuntimeError("submit failed")

        with (
            patch(
                "prefect.runner._state_proposer.propose_state",
                new_callable=AsyncMock,
                side_effect=Abort("aborted"),
            ),
            patch(
                "prefect.runner._state_proposer.exception_to_failed_state",
                new_callable=AsyncMock,
                return_value=MagicMock(),
            ),
        ):
            result = await proposer.propose_failed(flow_run, exc)

        assert result is None

    async def test_propose_failed_swallows_unexpected_exception(self):
        client = AsyncMock()
        proposer = StateProposer(client=client)
        flow_run = _make_flow_run()
        exc = RuntimeError("submit failed")

        with (
            patch(
                "prefect.runner._state_proposer.propose_state",
                new_callable=AsyncMock,
                side_effect=RuntimeError("unexpected"),
            ),
            patch(
                "prefect.runner._state_proposer.exception_to_failed_state",
                new_callable=AsyncMock,
                return_value=MagicMock(),
            ),
        ):
            result = await proposer.propose_failed(flow_run, exc)

        assert result is None


class TestStateProposerProposeAwaitingRetrySync:
    def test_propose_awaiting_retry_sync_calls_propose_state_sync(self):
        client = AsyncMock()
        proposer = StateProposer(client=client)
        flow_run = _make_flow_run()
        sync_client = MagicMock()

        with patch(
            "prefect.runner._state_proposer.propose_state_sync",
        ) as mock_propose_sync:
            proposer.propose_awaiting_retry_sync(flow_run, sync_client)

        mock_propose_sync.assert_called_once()
        call_args = mock_propose_sync.call_args
        assert call_args[0][0] is sync_client
        assert isinstance(call_args[0][1], AwaitingRetry().__class__)
        assert call_args[1]["flow_run_id"] == flow_run.id

    def test_propose_awaiting_retry_sync_raises_on_failure(self):
        client = AsyncMock()
        proposer = StateProposer(client=client)
        flow_run = _make_flow_run()
        sync_client = MagicMock()

        with patch(
            "prefect.runner._state_proposer.propose_state_sync",
            side_effect=RuntimeError("boom"),
        ):
            with pytest.raises(RuntimeError, match="boom"):
                proposer.propose_awaiting_retry_sync(flow_run, sync_client)
