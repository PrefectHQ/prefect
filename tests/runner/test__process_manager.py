from __future__ import annotations

import asyncio
import signal
import sys
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from prefect.runner._process_manager import ProcessHandle, ProcessManager


class TestProcessHandle:
    def test_pid_from_anyio_process(self):
        mock_proc = MagicMock()
        mock_proc.pid = 42
        mock_proc.returncode = 0
        handle = ProcessHandle(mock_proc)
        assert handle.pid == 42
        assert handle.returncode == 0

    def test_returncode_from_spawn_process(self):
        mock_proc = MagicMock(spec=["pid", "exitcode"])
        mock_proc.pid = 99
        mock_proc.exitcode = 1
        handle = ProcessHandle(mock_proc)
        assert handle.returncode == 1

    def test_raw_process(self):
        mock_proc = MagicMock()
        handle = ProcessHandle(mock_proc)
        assert handle.raw_process is mock_proc


class TestProcessManagerLifecycle:
    async def test_aenter_creates_lock(self):
        async with ProcessManager() as pm:
            assert isinstance(pm._process_map_lock, asyncio.Lock)

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX-only test")
    async def test_aexit_kills_tracked_processes(self):
        killed_ids: list[int] = []

        def fake_kill(pid: int, sig: int) -> None:
            if sig == signal.SIGTERM:
                killed_ids.append(pid)
            elif sig == 0:
                raise ProcessLookupError()

        with patch("prefect.runner._process_manager.os.kill", side_effect=fake_kill):
            async with ProcessManager() as pm:
                for pid in (100, 200):
                    run_id = uuid4()
                    mock_proc = MagicMock()
                    mock_proc.pid = pid
                    await pm.add(run_id, ProcessHandle(mock_proc))

        assert sorted(killed_ids) == [100, 200]

    async def test_aexit_clears_process_map(self):
        with patch(
            "prefect.runner._process_manager.os.kill",
            side_effect=ProcessLookupError(),
        ):
            pm = ProcessManager()
            async with pm:
                run_id = uuid4()
                mock_proc = MagicMock()
                mock_proc.pid = 1
                await pm.add(run_id, ProcessHandle(mock_proc))

        assert pm.get(run_id) is None

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX-only test")
    async def test_aexit_swallows_kill_errors(self):
        with patch(
            "prefect.runner._process_manager.os.kill",
            side_effect=OSError("gone"),
        ):
            async with ProcessManager() as pm:
                run_id = uuid4()
                mock_proc = MagicMock()
                mock_proc.pid = 999
                await pm.add(run_id, ProcessHandle(mock_proc))


class TestProcessManagerAddRemoveGet:
    async def test_add_stores_handle(self):
        async with ProcessManager() as pm:
            run_id = uuid4()
            handle = ProcessHandle(MagicMock())
            await pm.add(run_id, handle)
            assert pm.get(run_id) is handle

    async def test_remove_pops_handle(self):
        async with ProcessManager() as pm:
            run_id = uuid4()
            handle = ProcessHandle(MagicMock())
            await pm.add(run_id, handle)
            await pm.remove(run_id)
            assert pm.get(run_id) is None

    async def test_get_returns_none_for_missing_id(self):
        async with ProcessManager() as pm:
            assert pm.get(uuid4()) is None


class TestProcessManagerCallbacks:
    async def test_on_add_callback_invoked(self):
        on_add = AsyncMock()
        async with ProcessManager(on_add=on_add) as pm:
            run_id = uuid4()
            await pm.add(run_id, ProcessHandle(MagicMock()))
            on_add.assert_awaited_once_with(run_id)

    async def test_on_remove_callback_invoked(self):
        on_remove = AsyncMock()
        async with ProcessManager(on_remove=on_remove) as pm:
            run_id = uuid4()
            await pm.add(run_id, ProcessHandle(MagicMock()))
            await pm.remove(run_id)
            on_remove.assert_awaited_once_with(run_id)

    async def test_on_add_callback_exception_is_swallowed(self):
        on_add = AsyncMock(side_effect=RuntimeError("boom"))
        async with ProcessManager(on_add=on_add) as pm:
            run_id = uuid4()
            handle = ProcessHandle(MagicMock())
            await pm.add(run_id, handle)
            assert pm.get(run_id) is handle

    async def test_on_remove_callback_exception_is_swallowed(self):
        on_remove = AsyncMock(side_effect=RuntimeError("boom"))
        async with ProcessManager(on_remove=on_remove) as pm:
            run_id = uuid4()
            await pm.add(run_id, ProcessHandle(MagicMock()))
            await pm.remove(run_id)

    async def test_on_add_callback_can_reenter_manager(self):
        async def reentrant_on_add(pm: ProcessManager, flow_run_id: UUID) -> None:
            assert pm.get(flow_run_id) is not None

        pm = ProcessManager()
        pm._on_add = lambda fid: reentrant_on_add(pm, fid)
        async with pm:
            run_id = uuid4()
            await pm.add(run_id, ProcessHandle(MagicMock()))


class TestProcessManagerKill:
    async def test_kill_missing_flow_run_id_is_noop(self):
        async with ProcessManager() as pm:
            with patch("os.kill") as mock_kill:
                await pm.kill(uuid4())
                mock_kill.assert_not_called()

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX-only test")
    async def test_kill_sends_sigterm_then_returns_early(self):
        async with ProcessManager() as pm:
            run_id = uuid4()
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            await pm.add(run_id, ProcessHandle(mock_proc))

            call_count = 0

            def fake_kill(pid: int, sig: int) -> None:
                nonlocal call_count
                call_count += 1
                if sig == 0:
                    raise ProcessLookupError()

            with patch(
                "prefect.runner._process_manager.os.kill", side_effect=fake_kill
            ):
                await pm.kill(run_id, grace_seconds=1)
                assert call_count >= 2

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX-only test")
    async def test_kill_propagates_os_error_from_sigterm(self):
        async with ProcessManager() as pm:
            run_id = uuid4()
            mock_proc = MagicMock()
            mock_proc.pid = 99999
            await pm.add(run_id, ProcessHandle(mock_proc))

            with patch(
                "prefect.runner._process_manager.os.kill",
                side_effect=OSError("no such process"),
            ):
                with pytest.raises(OSError):
                    await pm.kill(run_id, grace_seconds=1)

    async def test_kill_handle_with_no_pid_is_noop(self):
        async with ProcessManager() as pm:
            run_id = uuid4()
            mock_proc = MagicMock()
            mock_proc.pid = None
            await pm.add(run_id, ProcessHandle(mock_proc))

            with patch("os.kill") as mock_kill:
                await pm.kill(run_id)
                mock_kill.assert_not_called()

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX-only test")
    async def test_kill_sends_sigkill_after_grace_period(self):
        async with ProcessManager() as pm:
            run_id = uuid4()
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            await pm.add(run_id, ProcessHandle(mock_proc))

            signals_sent: list[int] = []

            def fake_kill(pid: int, sig: int) -> None:
                signals_sent.append(sig)

            with patch(
                "prefect.runner._process_manager.os.kill", side_effect=fake_kill
            ):
                await pm.kill(run_id, grace_seconds=1)
                assert signal.SIGTERM in signals_sent
                assert signal.SIGKILL in signals_sent
