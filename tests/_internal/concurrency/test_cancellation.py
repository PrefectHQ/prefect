import asyncio
import concurrent.futures
import signal
import threading
import time
from unittest.mock import MagicMock

import anyio
import pytest

from prefect._internal.concurrency.cancellation import (
    AlarmCancelScope,
    AsyncCancelScope,
    CancelledError,
    WatcherThreadCancelScope,
    cancel_async_after,
    cancel_async_at,
    cancel_sync_after,
    cancel_sync_at,
    get_deadline,
    shield,
)


@pytest.fixture
def mock_alarm_signal_handler():
    if threading.current_thread() != threading.main_thread():
        pytest.skip("Can't test signal handlers from a thread")

    mock = MagicMock()
    _previous_alarm_handler = signal.signal(signal.SIGALRM, mock)
    try:
        yield mock
    finally:
        signal.signal(signal.SIGALRM, _previous_alarm_handler)


async def test_alarm_cancel_scope_repr():
    scope = AlarmCancelScope()
    assert "PENDING" in repr(scope)
    assert "runtime" not in repr(scope)
    assert hex(id(scope)) in repr(scope)

    if threading.current_thread() is threading.main_thread():
        with scope:
            assert "RUNNING" in repr(scope)
            assert "runtime" in repr(scope)

        assert "COMPLETED" in repr(scope)
        assert "runtime" in repr(scope)

    if threading.current_thread() is threading.main_thread():
        scope = AlarmCancelScope()
        try:
            with scope:
                scope.cancel()
        except CancelledError:
            pass

        assert "CANCELLED" in repr(scope)

    scope = AlarmCancelScope(name="test")
    assert hex(id(scope)) not in repr(scope)
    assert "name='test'" in repr(scope)

    scope = AlarmCancelScope(timeout=0.1)
    assert "timeout=0.1" in repr(scope)


@pytest.mark.parametrize("cls", [WatcherThreadCancelScope, AsyncCancelScope])
async def test_cancel_scope_repr(cls):
    scope = cls()
    assert "PENDING" in repr(scope)
    assert "runtime" not in repr(scope)
    assert hex(id(scope)) in repr(scope)

    with scope:
        assert "RUNNING" in repr(scope)
        assert "runtime" in repr(scope)

    assert "COMPLETED" in repr(scope)
    assert "runtime" in repr(scope)

    scope = cls()
    try:
        with scope:
            scope.cancel()
    except CancelledError:
        pass

    assert "CANCELLED" in repr(scope)

    scope = cls(name="test")
    assert hex(id(scope)) not in repr(scope)
    assert "name='test'" in repr(scope)

    scope = cls(timeout=0.1)
    assert "timeout=0.1" in repr(scope)


async def test_cancel_async_after():
    completed = False
    with pytest.raises(CancelledError):
        with cancel_async_after(0.1) as scope:
            await asyncio.sleep(1)
            completed = True

    assert scope.cancelled()
    assert not completed


@pytest.mark.timeout(method="thread")  # alarm-based pytest-timeout will interfere
def test_cancel_sync_after_in_main_thread():
    completed = False
    with pytest.raises(CancelledError):
        with cancel_sync_after(0.1) as scope:
            time.sleep(1)
            completed = True

    assert scope.cancelled()
    assert not completed


def test_cancel_sync_after_in_worker_thread():
    completed = False

    def on_worker_thread():
        with pytest.raises(CancelledError):
            with cancel_sync_after(0.1) as scope:
                # this timeout method does not interrupt sleep calls, the timeout is
                # raised on the next instruction
                for _ in range(10):
                    time.sleep(0.1)

                nonlocal completed
                completed = True

        return scope

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(on_worker_thread)
        scope = future.result()

    assert scope.cancelled()
    assert not completed


@pytest.mark.timeout(method="thread")  # alarm-based pytest-timeout will interfere
def test_cancel_sync_after_manual_in_main_thread():
    completed = False
    with pytest.raises(CancelledError):
        with cancel_sync_after(0.1) as scope:
            scope.cancel()
            time.sleep(1)
            completed = True

    assert scope.cancelled()
    assert not completed


def test_cancel_sync_after_manual_in_worker_thread():
    completed = False

    def on_worker_thread():
        with pytest.raises(CancelledError):
            with cancel_sync_after(0.1) as scope:
                scope.cancel()
                for _ in range(10):
                    time.sleep(0.1)

                    nonlocal completed
                    completed = True

        return scope

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(on_worker_thread)
        scope = future.result()

    assert scope.cancelled()
    assert not completed


async def test_cancel_async_after_no_timeout():
    completed = False
    with cancel_async_after(None) as scope:
        await asyncio.sleep(0.1)
        completed = True

    assert scope.completed()
    assert not scope.cancelled()
    assert completed


@pytest.mark.timeout(method="thread")  # alarm-based pytest-timeout will interfere
def test_cancel_sync_after_not_cancelled_in_main_thread():
    completed = False
    with cancel_sync_after(None) as scope:
        time.sleep(0.1)
        completed = True

    assert scope.completed()
    assert not scope.cancelled()
    assert completed


def test_cancel_sync_after_not_cancelled_in_worker_thread():
    completed = False

    def on_worker_thread():
        with cancel_sync_after(None) as scope:
            for _ in range(10):
                time.sleep(0.1)

            nonlocal completed
            completed = True

        return scope

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(on_worker_thread)
        scope = future.result()

    assert scope.completed()
    assert not scope.cancelled()
    assert completed


async def test_cancel_async_at():
    completed = False
    with pytest.raises(CancelledError):
        with cancel_async_at(get_deadline(timeout=0.1)) as scope:
            await asyncio.sleep(1)
            completed = True

    assert scope.cancelled()
    assert not completed


@pytest.mark.timeout(method="thread")  # alarm-based pytest-timeout will interfere
def test_cancel_sync_at():
    completed = False
    with pytest.raises(CancelledError):
        with cancel_sync_at(get_deadline(timeout=0.1)) as scope:
            time.sleep(1)
            completed = True

    assert scope.cancelled()
    assert not completed


async def test_cancel_async_manual_without_timeout():
    completed = False
    with pytest.raises(CancelledError):
        with cancel_async_at(None) as scope:
            async with anyio.create_task_group() as tg:
                tg.start_soon(asyncio.sleep, 1)
                scope.cancel()

            completed = True

    assert scope.cancelled()
    assert not completed


async def test_cancel_async_after_manual_with_timeout():
    completed = False
    with pytest.raises(CancelledError):
        with cancel_async_after(0.1) as scope:
            scope.cancel()
            await asyncio.sleep(1)
            completed = True

    assert scope.cancelled()
    assert not completed


async def test_cancel_async_from_another_thread():
    completed = False
    with pytest.raises(CancelledError):
        with cancel_async_after(None) as scope:
            async with anyio.create_task_group() as tg:
                tg.start_soon(asyncio.sleep, 1)
                with concurrent.futures.ThreadPoolExecutor() as thread:
                    thread.submit(scope.cancel)

            completed = True

    assert scope.cancelled()
    assert not completed


@pytest.mark.timeout(method="thread")  # alarm-based pytest-timeout will interfere
def test_cancel_sync_manually_in_main_thread():
    completed = False
    main_thread_ready = threading.Event()
    cancel_sent = threading.Event()

    with pytest.raises(CancelledError):
        # Set a timeout or we'll use a watcher thread instead of an alarm
        with cancel_sync_after(timeout=10) as scope:

            def cancel_when_sleeping():
                main_thread_ready.wait()
                scope.cancel()
                cancel_sent.set()

            # Start cancellation in another thread
            thread = threading.Thread(target=cancel_when_sleeping, daemon=True)
            thread.start()

            # Signal that the thread can send cancellation
            main_thread_ready.set()

            # Wait for the cancel_sent thread to cancel the scope
            cancel_sent.wait()

            # Then sleep
            time.sleep(2)

            completed = True

    assert scope.cancelled()
    assert not completed

    # Shutdown the thread
    thread.join()


def test_cancel_sync_manually_in_worker_thread():
    completed = False
    scope_future = concurrent.futures.Future()

    def on_worker_thread():
        with pytest.raises(CancelledError):
            with cancel_sync_at(None) as scope:
                # send the scope back to the parent so it can cancel it
                scope_future.set_result(scope)

                # this cancel method does not interrupt sleep calls, the timeout is
                # raised on the next instruction
                for _ in range(30):
                    time.sleep(0.1)

                nonlocal completed
                completed = True

        return scope

    with concurrent.futures.ThreadPoolExecutor() as executor:
        worker_future = executor.submit(on_worker_thread)

        # Wait for the cancel scope to be entered
        scope = scope_future.result()
        scope.cancel()

        scope = worker_future.result()

    assert scope.cancelled()
    assert not completed


@pytest.mark.timeout(method="thread")  # alarm-based pytest-timeout will interfere
def test_cancel_sync_nested_alarm_and_watcher_inner_cancelled():
    completed = False
    with cancel_sync_after(1) as outer_scope:
        with pytest.raises(CancelledError):
            with cancel_sync_after(0.1) as inner_scope:
                # this cancel method does not interrupt sleep calls, the timeout is
                # raised on the next instruction
                for _ in range(10):
                    time.sleep(0.1)
            completed = True

    assert not outer_scope.cancelled()
    assert inner_scope.cancelled()
    assert not completed


@pytest.mark.timeout(method="thread")  # alarm-based pytest-timeout will interfere
def test_cancel_sync_nested_alarm_and_watcher_outer_cancelled():
    completed = False

    with pytest.raises(CancelledError):
        with cancel_sync_after(0.1) as outer_scope:
            with cancel_sync_after(2) as inner_scope:
                time.sleep(1)
            completed = True

    assert not inner_scope.cancelled()
    assert outer_scope.cancelled()
    assert not completed


def test_cancel_sync_nested_watchers_inner_cancelled(mock_alarm_signal_handler):
    completed = False
    with cancel_sync_after(1) as outer_scope:
        with pytest.raises(CancelledError):
            with cancel_sync_after(0.1) as inner_scope:
                # this cancel method does not interrupt sleep calls, the timeout is
                # raised on the next instruction
                for _ in range(10):
                    time.sleep(0.1)
                completed = True

    assert not outer_scope.cancelled()
    assert inner_scope.cancelled()
    assert not completed

    (
        mock_alarm_signal_handler.assert_not_called(),
        "Alarm based handler should not be used",
    )


def test_cancel_sync_nested_watchers_outer_cancelled(mock_alarm_signal_handler):
    completed = False

    with pytest.raises(CancelledError):
        with cancel_sync_after(0.1) as outer_scope:
            with cancel_sync_after(2) as inner_scope:
                # this cancel method does not interrupt sleep calls, the timeout is
                # raised on the next instruction
                for _ in range(10):
                    time.sleep(0.1)
                completed = True

    assert not inner_scope.cancelled()
    assert outer_scope.cancelled()
    assert not completed

    (
        mock_alarm_signal_handler.assert_not_called(),
        "Alarm based handler should not be used",
    )


@pytest.mark.timeout(method="thread")  # alarm-based pytest-timeout will interfere
def test_cancel_sync_with_existing_alarm_handler(mock_alarm_signal_handler):
    completed = False

    with pytest.raises(CancelledError):
        with cancel_sync_after(0.1) as scope:
            # this cancel method does not interrupt sleep calls, the timeout is
            # raised on the next instruction
            for _ in range(10):
                time.sleep(0.1)
            completed = True

    assert scope.cancelled()
    assert not completed
    mock_alarm_signal_handler.assert_not_called()


@pytest.mark.timeout(method="thread")  # alarm-based pytest-timeout will interfere
def test_cancel_sync_after_nested_in_main_thread_inner_fails():
    completed = False
    with pytest.raises(CancelledError):
        with cancel_sync_after(2) as outer:
            with cancel_sync_after(0.1) as inner:
                for _ in range(10):
                    time.sleep(0.1)
                completed = True

    assert inner.cancelled()
    assert not outer.cancelled()
    assert not completed


@pytest.mark.timeout(method="thread")  # alarm-based pytest-timeout will interfere
def test_cancel_sync_after_nested_in_main_thread_outer_fails():
    completed = False
    with pytest.raises(CancelledError):
        with cancel_sync_after(1) as outer:
            with cancel_sync_after(5) as inner:
                time.sleep(2)
            completed = True

    assert outer.cancelled()
    assert not inner.cancelled()
    assert not completed


async def test_shield_async():
    completed = False
    completed_shield = False
    with pytest.raises(CancelledError):
        with cancel_async_after(0.1) as scope:
            with shield():
                await asyncio.sleep(1)
                completed_shield = True
            await asyncio.sleep(1)
            completed = True

    assert scope.cancelled()
    assert not completed
    assert completed_shield


async def test_shield_async_nested():
    completed = False
    completed_shieldA = False
    completed_shieldB = False
    with pytest.raises(CancelledError):
        with cancel_async_after(0.1) as scope:
            with shield():
                await asyncio.sleep(0.5)
                with shield():
                    await asyncio.sleep(0.5)
                    completed_shieldB = True
                completed_shieldA = True
            await asyncio.sleep(1)
            completed = True

    assert scope.cancelled()
    assert not completed
    assert completed_shieldA
    assert completed_shieldB


@pytest.mark.timeout(method="thread")  # alarm-based pytest-timeout will interfere
def test_shield_sync_in_main_thread():
    completed = False
    completed_shield = False
    with pytest.raises(CancelledError):
        with cancel_sync_after(0.1) as scope:
            with shield():
                time.sleep(1)
                completed_shield = True
            time.sleep(1)
            completed = True

    assert scope.cancelled()
    assert not completed
    assert completed_shield


@pytest.mark.timeout(method="thread")  # alarm-based pytest-timeout will interfere
def test_shield_sync_in_main_thread_nested():
    completed = False
    completed_shieldA = False
    completed_shieldB = False
    with pytest.raises(CancelledError):
        with cancel_sync_after(0.1) as scope:
            with shield():
                time.sleep(0.5)
                with shield():
                    time.sleep(0.5)
                    completed_shieldB = True
                completed_shieldA = True

            time.sleep(1)
            completed = True

    assert scope.cancelled()
    assert not completed
    assert completed_shieldA
    assert completed_shieldB


def test_shield_sync_in_worker_thread_nested():
    completed = False
    completed_shieldA = False
    completed_shieldB = False

    def on_worker_thread():
        with pytest.raises(CancelledError):
            with cancel_sync_after(0.1) as scope:
                with shield():
                    for _ in range(5):
                        time.sleep(0.1)
                    with shield():
                        for _ in range(5):
                            time.sleep(0.1)

                        nonlocal completed_shieldB
                        completed_shieldB = True

                    nonlocal completed_shieldA
                    completed_shieldA = True

                for _ in range(10):
                    time.sleep(0.1)

                nonlocal completed
                completed = True

        return scope

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(on_worker_thread)
        future.result()

    assert not completed
    assert completed_shieldA
    assert completed_shieldB
