"""Tests for supervised in-process dbt invocation."""

import ctypes
import threading
import time
from contextlib import contextmanager
from unittest.mock import Mock, patch

import pytest
from dbt.cli.main import dbtRunnerResult
from prefect_dbt.core import _invoke
from prefect_dbt.core._invoke import cancel_open_adapter_connections, invoke_dbt

from prefect import task
from prefect._internal.concurrency.cancellation import CancelledError
from prefect.states import StateType


class FakeDbtRunner:
    """Mimics `dbtRunner`: blocks until interrupted or released, and swallows
    any `BaseException` into the returned result like dbt does."""

    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()
        self.finished = threading.Event()
        self.interrupted: BaseException | None = None
        self.invocations = 0

    def invoke(self, args):
        self.invocations += 1
        self.started.set()
        try:
            while not self.release.is_set():
                time.sleep(0.01)
            return dbtRunnerResult(success=True, result=Mock())
        except BaseException as exc:
            self.interrupted = exc
            return dbtRunnerResult(success=False, exception=exc)
        finally:
            self.finished.set()


class FakeAdapter:
    def __init__(self, cancelable: bool = True):
        self.cancelable = cancelable
        self.cancel_calls = 0
        self.connection_names: list[str] = []

    def type(self):
        return "fake"

    def is_cancelable(self):
        return self.cancelable

    @contextmanager
    def connection_named(self, name: str):
        self.connection_names.append(name)
        yield

    def cancel_open_connections(self):
        self.cancel_calls += 1


@pytest.fixture
def registered_adapter():
    adapter = FakeAdapter()
    with patch.dict(_invoke.FACTORY.adapters, {"fake": adapter}, clear=True):
        yield adapter


def _cancel_thread_after(thread: threading.Thread, delay: float):
    def _fire():
        time.sleep(delay)
        _invoke._inject_keyboard_interrupt(thread)

    threading.Thread(target=_fire, daemon=True).start()


def _dbt_threads() -> list[threading.Thread]:
    return [t for t in threading.enumerate() if t.name == "prefect-dbt-invoke"]


class TestInvokeDbt:
    def test_returns_result_on_success(self):
        runner = FakeDbtRunner()
        runner.release.set()

        res = invoke_dbt(runner, ["build"])

        assert res.success is True
        assert _dbt_threads() == []

    def test_propagates_exception_raised_by_runner(self):
        runner = Mock()
        runner.invoke.side_effect = RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            invoke_dbt(runner, ["build"])

    def test_cancellation_interrupts_dbt_and_cancels_connections(
        self, registered_adapter
    ):
        runner = FakeDbtRunner()

        def _target():
            invoke_dbt(runner, ["build"])

        errors: list[BaseException] = []

        def _guarded():
            try:
                _target()
            except BaseException as exc:
                errors.append(exc)

        caller = threading.Thread(target=_guarded)
        caller.start()
        assert runner.started.wait(5)
        _cancel_thread_after(caller, 0)
        caller.join(5)

        assert not caller.is_alive()
        assert isinstance(errors[0], KeyboardInterrupt)
        assert isinstance(runner.interrupted, KeyboardInterrupt)
        assert runner.finished.is_set()
        assert registered_adapter.cancel_calls >= 1
        assert registered_adapter.connection_names[0] == "master"
        assert _dbt_threads() == []

    def test_cancellation_waits_for_dbt_thread_to_exit(self, registered_adapter):
        """The cancellation is not re-raised while dbt is still running."""
        runner = FakeDbtRunner()
        dbt_finished_when_caller_exited: list[bool] = []

        def _guarded():
            try:
                invoke_dbt(runner, ["build"])
            except KeyboardInterrupt:
                dbt_finished_when_caller_exited.append(runner.finished.is_set())

        caller = threading.Thread(target=_guarded)
        caller.start()
        assert runner.started.wait(5)
        _cancel_thread_after(caller, 0)
        caller.join(5)

        assert dbt_finished_when_caller_exited == [True]

    def test_connections_are_re_cancelled_while_dbt_is_shutting_down(
        self, registered_adapter, monkeypatch
    ):
        monkeypatch.setattr(_invoke, "_CANCEL_RETRY_INTERVAL", 0.05)
        runner = FakeDbtRunner()

        def _slow_invoke(args):
            # Swallow the interrupt so dbt "keeps running" after cancellation.

            runner.started.set()
            while not runner.release.is_set():
                try:
                    time.sleep(0.01)
                except KeyboardInterrupt:
                    pass
            runner.finished.set()
            return dbtRunnerResult(success=True, result=Mock())

        runner.invoke = _slow_invoke

        def _guarded():
            try:
                invoke_dbt(runner, ["build"])
            except KeyboardInterrupt:
                pass

        caller = threading.Thread(target=_guarded)
        caller.start()
        assert runner.started.wait(5)
        _cancel_thread_after(caller, 0)
        time.sleep(0.5)
        runner.release.set()
        caller.join(5)

        assert not caller.is_alive()
        assert registered_adapter.cancel_calls >= 3


class TestCancelOpenAdapterConnections:
    def test_no_adapter_registered_is_a_noop(self):
        with patch.dict(_invoke.FACTORY.adapters, {}, clear=True):
            cancel_open_adapter_connections()

    def test_skips_non_cancelable_adapter(self):
        adapter = FakeAdapter(cancelable=False)
        with patch.dict(_invoke.FACTORY.adapters, {"fake": adapter}, clear=True):
            cancel_open_adapter_connections()
        assert adapter.cancel_calls == 0
        assert adapter.connection_names == []

    def test_adapter_errors_are_logged_not_raised(self):
        adapter = FakeAdapter()
        adapter.cancel_open_connections = Mock(side_effect=RuntimeError("db down"))
        with patch.dict(_invoke.FACTORY.adapters, {"fake": adapter}, clear=True):
            cancel_open_adapter_connections()


class TestPrefectTaskIntegration:
    def test_task_timeout_stops_dbt_before_retry(self, registered_adapter):
        """A timed-out attempt's dbt invocation has fully exited before the
        retry starts, and the retry gets a fresh dbt invocation."""
        runners: list[FakeDbtRunner] = []
        overlaps: list[bool] = []

        @task(timeout_seconds=0.5, retries=1, retry_delay_seconds=0)
        def run_dbt():
            if runners:
                overlaps.append(not runners[-1].finished.is_set())
            runner = FakeDbtRunner()
            runners.append(runner)
            if len(runners) == 2:
                runner.release.set()
            return invoke_dbt(runner, ["build"]).success

        state = run_dbt(return_state=True)

        assert state.type == StateType.COMPLETED
        assert state.result() is True
        assert len(runners) == 2
        assert overlaps == [False]
        assert isinstance(runners[0].interrupted, KeyboardInterrupt)
        assert registered_adapter.cancel_calls >= 1
        assert _dbt_threads() == []

    def test_task_timeout_without_retry_ends_timed_out(self, registered_adapter):
        @task(timeout_seconds=0.5)
        def run_dbt():
            invoke_dbt(FakeDbtRunner(), ["build"])

        state = run_dbt(return_state=True)

        assert state.type == StateType.FAILED
        assert state.name == "TimedOut"
        assert _dbt_threads() == []

    def test_cancelled_error_propagates_unchanged(self, registered_adapter):
        runner = FakeDbtRunner()
        raised: list[BaseException] = []

        def _guarded():
            try:
                invoke_dbt(runner, ["build"])
            except BaseException as exc:
                raised.append(exc)

        caller = threading.Thread(target=_guarded)
        caller.start()
        assert runner.started.wait(5)
        ctypes.pythonapi.PyThreadState_SetAsyncExc(
            ctypes.c_ulong(caller.ident), ctypes.py_object(CancelledError)
        )
        caller.join(5)

        assert isinstance(raised[0], CancelledError)
        assert runner.finished.is_set()
