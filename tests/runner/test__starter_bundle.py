from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from prefect.runner._process_manager import ProcessHandle
from prefect.runner._starter_bundle import BundleExecutionStarter


class TestBundleExecutionStarter:
    async def test_start_calls_execute_bundle_in_subprocess(self):
        mock_bundle = MagicMock()
        mock_flow_run = MagicMock()
        mock_process = MagicMock()
        mock_process.join = MagicMock()

        starter = BundleExecutionStarter(bundle=mock_bundle)

        with patch(
            "prefect.runner._starter_bundle.execute_bundle_in_subprocess",
            return_value=mock_process,
        ) as mock_exec:
            await starter.start(mock_flow_run)

            mock_exec.assert_called_once_with(
                mock_bundle,
                cwd=None,
                env=None,
            )

    async def test_start_signals_handle_before_join(self):
        """task_status.started(handle) must be called BEFORE process.join."""
        mock_bundle = MagicMock()
        mock_flow_run = MagicMock()
        mock_process = MagicMock()

        call_order: list[str] = []
        mock_process.join = MagicMock(side_effect=lambda: call_order.append("join"))

        mock_task_status = MagicMock()
        mock_task_status.started = MagicMock(
            side_effect=lambda h: call_order.append("started")
        )

        starter = BundleExecutionStarter(bundle=mock_bundle)

        with patch(
            "prefect.runner._starter_bundle.execute_bundle_in_subprocess",
            return_value=mock_process,
        ):
            await starter.start(mock_flow_run, task_status=mock_task_status)

        assert call_order == ["started", "join"]

    async def test_start_wraps_process_in_handle(self):
        mock_bundle = MagicMock()
        mock_flow_run = MagicMock()
        mock_process = MagicMock()
        mock_process.pid = 456
        mock_process.join = MagicMock()

        mock_task_status = MagicMock()

        starter = BundleExecutionStarter(bundle=mock_bundle)

        with patch(
            "prefect.runner._starter_bundle.execute_bundle_in_subprocess",
            return_value=mock_process,
        ):
            await starter.start(mock_flow_run, task_status=mock_task_status)

        handle = mock_task_status.started.call_args[0][0]
        assert isinstance(handle, ProcessHandle)
        assert handle.pid == 456

    async def test_start_passes_cwd(self):
        mock_bundle = MagicMock()
        mock_flow_run = MagicMock()
        mock_process = MagicMock()
        mock_process.join = MagicMock()

        starter = BundleExecutionStarter(
            bundle=mock_bundle,
            cwd=Path("/my/working/dir"),
        )

        with patch(
            "prefect.runner._starter_bundle.execute_bundle_in_subprocess",
            return_value=mock_process,
        ) as mock_exec:
            await starter.start(mock_flow_run)

            mock_exec.assert_called_once_with(
                mock_bundle,
                cwd=Path("/my/working/dir"),
                env=None,
            )

    async def test_start_passes_env(self):
        mock_bundle = MagicMock()
        mock_flow_run = MagicMock()
        mock_process = MagicMock()
        mock_process.join = MagicMock()

        starter = BundleExecutionStarter(
            bundle=mock_bundle,
            env={"MY_VAR": "value"},
        )

        with patch(
            "prefect.runner._starter_bundle.execute_bundle_in_subprocess",
            return_value=mock_process,
        ) as mock_exec:
            await starter.start(mock_flow_run)

            mock_exec.assert_called_once_with(
                mock_bundle,
                cwd=None,
                env={"MY_VAR": "value"},
            )

    async def test_start_empty_env_passes_none(self):
        """When env is empty dict (default), passes None to subprocess."""
        mock_bundle = MagicMock()
        mock_flow_run = MagicMock()
        mock_process = MagicMock()
        mock_process.join = MagicMock()

        starter = BundleExecutionStarter(bundle=mock_bundle)

        with patch(
            "prefect.runner._starter_bundle.execute_bundle_in_subprocess",
            return_value=mock_process,
        ) as mock_exec:
            await starter.start(mock_flow_run)

            mock_exec.assert_called_once_with(
                mock_bundle,
                cwd=None,
                env=None,
            )

    async def test_start_uses_default_task_status(self):
        """start() works when no task_status is provided."""
        mock_bundle = MagicMock()
        mock_flow_run = MagicMock()
        mock_process = MagicMock()
        mock_process.join = MagicMock()

        starter = BundleExecutionStarter(bundle=mock_bundle)

        with patch(
            "prefect.runner._starter_bundle.execute_bundle_in_subprocess",
            return_value=mock_process,
        ):
            # Should not raise — TASK_STATUS_IGNORED silently ignores .started()
            await starter.start(mock_flow_run)
