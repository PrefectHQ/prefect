from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock

import anyio
import anyio.abc

from prefect.runner._flow_run_executor import ProcessStarter
from prefect.runner._process_manager import ProcessHandle


class TestProcessStarterProtocol:
    def test_protocol_is_importable(self):
        """ProcessStarter can be imported from the module."""
        assert ProcessStarter is not None

    def test_protocol_defines_start_method(self):
        """ProcessStarter Protocol defines a start() method."""
        assert hasattr(ProcessStarter, "start")
        sig = inspect.signature(ProcessStarter.start)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "flow_run" in params
        assert "task_status" in params

    def test_async_mock_can_serve_as_starter(self):
        """An AsyncMock with start() attribute works as a stand-in."""
        mock_starter = MagicMock()
        mock_starter.start = AsyncMock()
        # Verifies the mock has the expected attribute
        assert hasattr(mock_starter, "start")

    async def test_conforming_class_can_be_called(self):
        """A conforming class can actually be awaited."""

        class FakeStarter:
            async def start(
                self,
                flow_run,
                task_status=anyio.TASK_STATUS_IGNORED,
            ) -> None:
                handle = ProcessHandle(MagicMock(pid=42, returncode=0))
                task_status.started(handle)

        starter = FakeStarter()
        mock_flow_run = MagicMock()
        mock_task_status = MagicMock()
        mock_task_status.started = MagicMock()

        await starter.start(mock_flow_run, task_status=mock_task_status)
        mock_task_status.started.assert_called_once()
        handle = mock_task_status.started.call_args[0][0]
        assert isinstance(handle, ProcessHandle)
        assert handle.pid == 42
