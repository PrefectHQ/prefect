from __future__ import annotations

from unittest.mock import MagicMock, patch

from prefect.runner._process_manager import ProcessHandle
from prefect.runner._starter_direct import DirectSubprocessStarter


class TestDirectSubprocessStarter:
    async def test_start_calls_run_flow_in_subprocess(self):
        mock_flow = MagicMock()
        mock_flow_run = MagicMock()
        mock_process = MagicMock()
        mock_process.join = MagicMock()

        starter = DirectSubprocessStarter(flow=mock_flow)

        with patch(
            "prefect.runner._starter_direct.run_flow_in_subprocess",
            return_value=mock_process,
        ) as mock_run:
            mock_task_status = MagicMock()
            await starter.start(mock_flow_run, task_status=mock_task_status)

            mock_run.assert_called_once_with(
                mock_flow,
                flow_run=mock_flow_run,
                env=None,
            )

    async def test_start_signals_handle_before_join(self):
        """task_status.started(handle) must be called BEFORE process.join."""
        mock_flow = MagicMock()
        mock_flow_run = MagicMock()
        mock_process = MagicMock()

        call_order: list[str] = []
        mock_process.join = MagicMock(side_effect=lambda: call_order.append("join"))

        mock_task_status = MagicMock()
        mock_task_status.started = MagicMock(
            side_effect=lambda h: call_order.append("started")
        )

        starter = DirectSubprocessStarter(flow=mock_flow)

        with patch(
            "prefect.runner._starter_direct.run_flow_in_subprocess",
            return_value=mock_process,
        ):
            await starter.start(mock_flow_run, task_status=mock_task_status)

        assert call_order == ["started", "join"]

    async def test_start_wraps_process_in_handle(self):
        mock_flow = MagicMock()
        mock_flow_run = MagicMock()
        mock_process = MagicMock()
        mock_process.pid = 123
        mock_process.join = MagicMock()

        mock_task_status = MagicMock()

        starter = DirectSubprocessStarter(flow=mock_flow)

        with patch(
            "prefect.runner._starter_direct.run_flow_in_subprocess",
            return_value=mock_process,
        ):
            await starter.start(mock_flow_run, task_status=mock_task_status)

        handle = mock_task_status.started.call_args[0][0]
        assert isinstance(handle, ProcessHandle)
        assert handle.pid == 123

    async def test_start_passes_heartbeat_env(self):
        mock_flow = MagicMock()
        mock_flow_run = MagicMock()
        mock_process = MagicMock()
        mock_process.join = MagicMock()

        starter = DirectSubprocessStarter(flow=mock_flow, heartbeat_seconds=30)

        with patch(
            "prefect.runner._starter_direct.run_flow_in_subprocess",
            return_value=mock_process,
        ) as mock_run:
            await starter.start(mock_flow_run)

            mock_run.assert_called_once_with(
                mock_flow,
                flow_run=mock_flow_run,
                env={"PREFECT_FLOWS_HEARTBEAT_FREQUENCY": "30"},
            )

    async def test_start_no_heartbeat_passes_none_env(self):
        mock_flow = MagicMock()
        mock_flow_run = MagicMock()
        mock_process = MagicMock()
        mock_process.join = MagicMock()

        starter = DirectSubprocessStarter(flow=mock_flow, heartbeat_seconds=None)

        with patch(
            "prefect.runner._starter_direct.run_flow_in_subprocess",
            return_value=mock_process,
        ) as mock_run:
            await starter.start(mock_flow_run)

            mock_run.assert_called_once_with(
                mock_flow,
                flow_run=mock_flow_run,
                env=None,
            )

    async def test_start_uses_default_task_status(self):
        """start() works when no task_status is provided (uses TASK_STATUS_IGNORED)."""
        mock_flow = MagicMock()
        mock_flow_run = MagicMock()
        mock_process = MagicMock()
        mock_process.join = MagicMock()

        starter = DirectSubprocessStarter(flow=mock_flow)

        with patch(
            "prefect.runner._starter_direct.run_flow_in_subprocess",
            return_value=mock_process,
        ):
            # Should not raise — TASK_STATUS_IGNORED silently ignores .started()
            await starter.start(mock_flow_run)
