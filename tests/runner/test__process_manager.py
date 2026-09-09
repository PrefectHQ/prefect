from __future__ import annotations

import asyncio
import signal
import sys
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import anyio
import pytest

from prefect.runner._process_manager import (
    ProcessHandle,
    ProcessManager,
    _create_windows_job_termination_scope,
    _pid_is_alive,
    _PosixProcessGroupTerminationScope,
)

pytestmark = pytest.mark.clear_db


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

    async def test_force_kill_uses_owned_termination_scope(self):
        async with ProcessManager() as pm:
            run_id = uuid4()
            process = MagicMock(pid=12345, returncode=None)
            termination_scope = MagicMock()
            await pm.add(
                run_id,
                ProcessHandle(process, termination_scope=termination_scope),
            )

            await pm.kill(run_id, force=True)

            termination_scope.hard_kill.assert_called_once_with(12345)
            termination_scope.graceful_kill.assert_not_called()
            await pm.remove(run_id)

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

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX-only signals")
    async def test_kill_force_does_not_probe_or_signal_an_unowned_group(self):
        async with ProcessManager() as pm:
            run_id = uuid4()
            process = MagicMock(pid=12345, returncode=None)
            await pm.add(run_id, ProcessHandle(process))

            with (
                patch("prefect.runner._process_manager.os.getpgid") as getpgid,
                patch("prefect.runner._process_manager.os.killpg") as killpg,
                patch("prefect.runner._process_manager.os.kill") as kill,
            ):
                await pm.kill(run_id, force=True)

            getpgid.assert_not_called()
            killpg.assert_not_called()
            kill.assert_called_once_with(12345, signal.SIGKILL)

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX-only signals")
    async def test_kill_force_sends_only_sigkill_without_grace_period(self):
        async with ProcessManager() as pm:
            run_id = uuid4()
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            await pm.add(
                run_id,
                ProcessHandle(
                    mock_proc,
                    termination_scope=_PosixProcessGroupTerminationScope(),
                ),
            )

            sent: list[tuple[str, int]] = []
            with (
                patch(
                    "prefect.runner._process_manager.os.killpg",
                    side_effect=lambda pid, sig: sent.append(("killpg", sig)),
                ),
                patch(
                    "prefect.runner._process_manager.os.kill",
                    side_effect=lambda pid, sig: sent.append(("kill", sig)),
                ),
                anyio.fail_after(1),  # must not wait out the grace period
            ):
                await pm.kill(run_id, grace_seconds=30, force=True)

            assert sent == [("killpg", signal.SIGKILL)]

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX-only signals")
    async def test_kill_signals_isolated_process_group(self):
        async with ProcessManager() as pm:
            run_id = uuid4()
            process = MagicMock(pid=12345, returncode=None)
            await pm.add(
                run_id,
                ProcessHandle(
                    process,
                    termination_scope=_PosixProcessGroupTerminationScope(),
                ),
            )
            sent: list[tuple[int, int]] = []

            with (
                patch(
                    "prefect.runner._process_manager.os.killpg",
                    side_effect=lambda pid, sig: sent.append((pid, sig)),
                ),
                patch(
                    "prefect.runner._process_manager.os.kill",
                    side_effect=ProcessLookupError,
                ),
            ):
                await pm.kill(run_id, grace_seconds=0)

            assert sent == [
                (12345, signal.SIGTERM),
                (12345, signal.SIGKILL),
            ]

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX-only signals")
    async def test_kill_escalates_when_group_leader_exits_before_child(self):
        async with ProcessManager() as pm:
            run_id = uuid4()
            process = MagicMock(pid=12345, returncode=None)
            await pm.add(
                run_id,
                ProcessHandle(
                    process,
                    termination_scope=_PosixProcessGroupTerminationScope(),
                ),
            )
            signals_sent: list[int] = []
            original_sleep = anyio.sleep
            sleep_count = 0

            async def allow_one_poll(delay: float) -> None:
                nonlocal sleep_count
                sleep_count += 1
                if sleep_count > 1:
                    await original_sleep(delay)

            def process_is_gone(_pid: int, sig: int) -> None:
                assert sig == 0
                raise ProcessLookupError

            with (
                patch(
                    "prefect.runner._process_manager.os.killpg",
                    side_effect=lambda _pid, sig: signals_sent.append(sig),
                ),
                patch(
                    "prefect.runner._process_manager.os.kill",
                    side_effect=process_is_gone,
                ),
                patch(
                    "prefect.runner._process_manager.anyio.sleep",
                    side_effect=allow_one_poll,
                ),
            ):
                await pm.kill(run_id, grace_seconds=0.01)

            assert signals_sent == [signal.SIGTERM, 0, signal.SIGKILL]

    async def test_kill_ignores_an_already_reaped_process(self):
        """`__aexit__` re-kills entries whose cleanup was skipped by cancellation."""
        async with ProcessManager() as pm:
            run_id = uuid4()
            mock_proc = MagicMock()
            mock_proc.pid = 99999
            await pm.add(run_id, ProcessHandle(mock_proc))

            with patch(
                "prefect.runner._process_manager.os.kill",
                side_effect=ProcessLookupError("no such process"),
            ):
                await pm.kill(run_id, grace_seconds=1)

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


class TestProcessManagerWaitForExit:
    async def test_wait_for_exit_returns_true_when_process_disappears(self):
        async with ProcessManager() as pm:
            run_id = uuid4()
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            mock_proc.returncode = None
            await pm.add(run_id, ProcessHandle(mock_proc))

            with patch(
                "prefect.runner._process_manager._pid_is_alive", return_value=False
            ):
                assert await pm.wait_for_exit(run_id, grace_seconds=1) is True

    async def test_wait_for_exit_returns_false_on_timeout(self):
        async with ProcessManager() as pm:
            run_id = uuid4()
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            mock_proc.returncode = None
            await pm.add(run_id, ProcessHandle(mock_proc))

            with patch(
                "prefect.runner._process_manager._pid_is_alive", return_value=True
            ):
                assert await pm.wait_for_exit(run_id, grace_seconds=0) is False


class TestPidIsAlive:
    def test_pid_is_alive_uses_wait_timeout_on_windows(self, monkeypatch):
        fake_kernel32 = MagicMock()
        fake_kernel32.OpenProcess.return_value = 123
        fake_kernel32.WaitForSingleObject.return_value = 0x00000102

        monkeypatch.setattr("prefect.runner._process_manager.sys.platform", "win32")
        monkeypatch.setattr(
            "prefect.runner._process_manager._get_windows_kernel32",
            lambda: fake_kernel32,
        )

        assert _pid_is_alive(12345) is True
        fake_kernel32.CloseHandle.assert_called_once_with(123)

    def test_pid_is_alive_detects_exited_process_on_windows(self, monkeypatch):
        fake_kernel32 = MagicMock()
        fake_kernel32.OpenProcess.return_value = 456
        fake_kernel32.WaitForSingleObject.return_value = 0x00000000

        monkeypatch.setattr("prefect.runner._process_manager.sys.platform", "win32")
        monkeypatch.setattr(
            "prefect.runner._process_manager._get_windows_kernel32",
            lambda: fake_kernel32,
        )

        assert _pid_is_alive(67890) is False
        fake_kernel32.CloseHandle.assert_called_once_with(456)


async def test_windows_job_scope_force_kills_and_closes_the_owned_tree(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_kernel32 = MagicMock()
    fake_kernel32.CreateJobObjectW.return_value = 111
    fake_kernel32.SetInformationJobObject.return_value = 1
    fake_kernel32.OpenProcess.return_value = 222
    fake_kernel32.AssignProcessToJobObject.return_value = 1
    fake_kernel32.TerminateJobObject.return_value = 1
    monkeypatch.setattr(
        "prefect.runner._process_manager._get_windows_kernel32",
        lambda: fake_kernel32,
    )
    termination_scope = _create_windows_job_termination_scope(12345)

    async with ProcessManager() as pm:
        flow_run_id = uuid4()
        process = MagicMock(pid=12345, returncode=None)
        await pm.add(
            flow_run_id,
            ProcessHandle(process, termination_scope=termination_scope),
        )

        await pm.kill(flow_run_id, force=True)
        await pm.remove(flow_run_id)

    fake_kernel32.AssignProcessToJobObject.assert_called_once_with(111, 222)
    fake_kernel32.TerminateJobObject.assert_called_once_with(111, 1)
    fake_kernel32.CloseHandle.assert_any_call(222)
    fake_kernel32.CloseHandle.assert_any_call(111)
