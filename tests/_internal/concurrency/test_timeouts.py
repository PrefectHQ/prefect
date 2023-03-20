import asyncio
import concurrent.futures
import signal
import threading
import time
from unittest.mock import MagicMock

import anyio
import pytest

from prefect._internal.concurrency.timeouts import (
    CancelContext,
    CancelledError,
    cancel_async_after,
    cancel_async_at,
    cancel_sync_after,
    cancel_sync_at,
    get_deadline,
)


@pytest.fixture
def mock_alarm_signal_handler():
    mock = MagicMock()
    _previous_alarm_handler = signal.signal(signal.SIGALRM, mock)
    try:
        yield mock
    finally:
        signal.signal(signal.SIGALRM, _previous_alarm_handler)


async def test_cancel_context():
    cancel = MagicMock()
    ctx = CancelContext(timeout=1, cancel=cancel)
    assert not ctx.cancelled()
    ctx.cancel()
    assert ctx.cancelled()
    cancel.assert_called_once_with()


async def test_cancel_context_chain():
    cancel1 = MagicMock()
    cancel2 = MagicMock()
    ctx1 = CancelContext(timeout=1, cancel=cancel1)
    ctx2 = CancelContext(timeout=None, cancel=cancel2)
    ctx1.chain(ctx2)
    assert not ctx2.cancelled()
    ctx1.cancel()
    assert ctx1.cancelled()
    assert ctx2.cancelled()
    cancel1.assert_called_once_with()
    cancel2.assert_called_once_with()


async def test_cancel_context_chain_cancelled_first():
    cancel1 = MagicMock()
    cancel2 = MagicMock()
    ctx1 = CancelContext(timeout=1, cancel=cancel1)
    ctx2 = CancelContext(timeout=None, cancel=cancel2)
    ctx1.cancel()
    ctx1.chain(ctx2)
    assert ctx1.cancelled()
    assert ctx2.cancelled()
    cancel1.assert_called_once_with()
    cancel2.assert_called_once_with()


async def test_cancel_context_chain_cancelled_after_completed():
    cancel1 = MagicMock()
    cancel2 = MagicMock()
    ctx1 = CancelContext(timeout=1, cancel=cancel1)
    ctx2 = CancelContext(timeout=None, cancel=cancel2)
    ctx1.chain(ctx2)
    ctx2.mark_completed()
    ctx1.cancel()
    assert ctx1.cancelled()
    assert not ctx2.cancelled()
    cancel1.assert_called_once_with()
    cancel2.assert_not_called()


async def test_cancel_context_chain_bidirectional():
    cancel1 = MagicMock()
    cancel2 = MagicMock()
    ctx1 = CancelContext(timeout=1, cancel=cancel1)
    ctx2 = CancelContext(timeout=None, cancel=cancel2)
    ctx1.chain(ctx2, bidirectional=True)
    ctx2.cancel()
    assert ctx1.cancelled()
    assert ctx2.cancelled()
    cancel1.assert_called_once_with()
    cancel2.assert_called_once_with()


async def test_cancel_context_chain_bidirectional_after_first_completed():
    cancel1 = MagicMock()
    cancel2 = MagicMock()
    ctx1 = CancelContext(timeout=1, cancel=cancel1)
    ctx2 = CancelContext(timeout=None, cancel=cancel2)
    ctx1.chain(ctx2, bidirectional=True)
    ctx1.mark_completed()
    ctx2.cancel()
    assert not ctx1.cancelled()
    assert ctx2.cancelled()
    cancel1.assert_not_called()
    cancel2.assert_called_once_with()


async def test_cancel_context_chain_bidirectional_after_second_completed():
    cancel1 = MagicMock()
    cancel2 = MagicMock()
    ctx1 = CancelContext(timeout=1, cancel=cancel1)
    ctx2 = CancelContext(timeout=None, cancel=cancel2)
    ctx1.chain(ctx2, bidirectional=True)
    ctx2.mark_completed()
    ctx2.cancel()
    assert not ctx1.cancelled()
    assert not ctx2.cancelled()
    cancel1.assert_not_called()
    cancel2.assert_not_called()


async def test_cancel_async_after():
    t0 = time.perf_counter()
    with pytest.raises(TimeoutError):
        with cancel_async_after(0.1) as ctx:
            await asyncio.sleep(1)
    t1 = time.perf_counter()

    assert ctx.cancelled()
    assert t1 - t0 < 1


@pytest.mark.timeout(method="thread")  # alarm-based pytest-timeout will interfere
def test_cancel_sync_after_in_main_thread():
    t0 = time.perf_counter()
    with pytest.raises(TimeoutError):
        with cancel_sync_after(0.1) as ctx:
            time.sleep(1)
    t1 = time.perf_counter()

    assert ctx.cancelled()
    assert t1 - t0 < 1


def test_cancel_sync_after_in_worker_thread():
    def on_worker_thread():
        t0 = time.perf_counter()
        with pytest.raises(TimeoutError):
            with cancel_sync_after(0.1) as ctx:
                # this timeout method does not interrupt sleep calls, the timeout is
                # raised on the next instruction
                for _ in range(10):
                    time.sleep(0.1)
        t1 = time.perf_counter()
        return t1 - t0, ctx

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(on_worker_thread)
        elapsed_time, ctx = future.result()

    assert elapsed_time < 1
    assert ctx.cancelled()


async def test_cancel_async_after_no_timeout():
    t0 = time.perf_counter()
    with cancel_async_after(None) as ctx:
        await asyncio.sleep(0.1)
    t1 = time.perf_counter()

    assert ctx.completed()
    assert not ctx.cancelled()
    assert t1 - t0 > 0.1


@pytest.mark.timeout(method="thread")  # alarm-based pytest-timeout will interfere
def test_cancel_sync_after_not_cancelled_in_main_thread():
    t0 = time.perf_counter()
    with cancel_sync_after(None) as ctx:
        time.sleep(0.1)
    t1 = time.perf_counter()

    assert ctx.completed()
    assert not ctx.cancelled()
    assert t1 - t0 > 0.1


def test_cancel_sync_after_not_cancelled_in_worker_thread():
    def on_worker_thread():
        t0 = time.perf_counter()
        with cancel_sync_after(None) as ctx:
            for _ in range(10):
                time.sleep(0.1)
        t1 = time.perf_counter()
        return t1 - t0, ctx

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(on_worker_thread)
        elapsed_time, ctx = future.result()

    assert ctx.completed()
    assert not ctx.cancelled()
    assert elapsed_time > 1


async def test_cancel_async_at():
    t0 = time.perf_counter()
    with pytest.raises(TimeoutError):
        with cancel_async_at(get_deadline(timeout=0.1)) as ctx:
            await asyncio.sleep(1)
    t1 = time.perf_counter()

    assert ctx.cancelled()
    assert t1 - t0 < 1


@pytest.mark.timeout(method="thread")  # alarm-based pytest-timeout will interfere
def test_cancel_sync_at():
    t0 = time.perf_counter()
    with pytest.raises(TimeoutError):
        with cancel_sync_at(get_deadline(timeout=0.1)) as ctx:
            time.sleep(1)
    t1 = time.perf_counter()

    assert ctx.cancelled()
    assert t1 - t0 < 1


async def test_cancel_async_manually():
    t0 = time.perf_counter()
    with pytest.raises(CancelledError):
        with cancel_async_at(None) as ctx:
            async with anyio.create_task_group() as tg:
                tg.start_soon(asyncio.sleep, 1)
                ctx.cancel()

    t1 = time.perf_counter()

    assert ctx.cancelled()
    assert t1 - t0 < 1


@pytest.mark.timeout(method="thread")  # alarm-based pytest-timeout will interfere
def test_cancel_sync_manually_in_main_thread():
    t0 = time.perf_counter()
    event = threading.Event()

    with pytest.raises(CancelledError):
        with cancel_sync_at(None) as ctx:

            def cancel_when_sleeping():
                event.wait()
                ctx.cancel()

            # Start cancellation in another thread
            thread = threading.Thread(target=cancel_when_sleeping, daemon=True)
            thread.start()

            # Sleep in the main thread
            event.set()
            time.sleep(2)

    t1 = time.perf_counter()
    assert ctx.cancelled()
    assert t1 - t0 < 2


def test_cancel_sync_manually_in_worker_thread():
    context_future = concurrent.futures.Future()

    def on_worker_thread():
        t0 = time.perf_counter()
        with pytest.raises(CancelledError):
            with cancel_sync_at(None) as ctx:
                # send the context back to the parent so it can cancel it
                context_future.set_result(ctx)

                # this cancel method does not interrupt sleep calls, the timeout is
                # raised on the next instruction
                for _ in range(30):
                    time.sleep(0.1)

        t1 = time.perf_counter()
        return t1 - t0, ctx

    with concurrent.futures.ThreadPoolExecutor() as executor:
        worker_future = executor.submit(on_worker_thread)

        # Wait for the cancel context to be entered
        context: CancelContext = context_future.result()
        context.cancel()

        elapsed_time, ctx = worker_future.result()

    assert elapsed_time < 1
    assert ctx.cancelled()


@pytest.mark.timeout(method="thread")  # alarm-based pytest-timeout will interfere
def test_cancel_sync_nested_alarm_and_watcher_inner_cancelled():
    t0 = time.perf_counter()
    with cancel_sync_after(1) as outer_ctx:
        with pytest.raises(TimeoutError):
            with cancel_sync_after(0.1) as inner_ctx:
                # this cancel method does not interrupt sleep calls, the timeout is
                # raised on the next instruction
                for _ in range(10):
                    time.sleep(0.1)
    t1 = time.perf_counter()

    assert not outer_ctx.cancelled()
    assert inner_ctx.cancelled()
    assert t1 - t0 < 1


@pytest.mark.timeout(method="thread")  # alarm-based pytest-timeout will interfere
def test_cancel_sync_nested_alarm_and_watcher_outer_cancelled():
    t0 = time.perf_counter()

    with pytest.raises(TimeoutError):
        with cancel_sync_after(0.1) as outer_ctx:
            with cancel_sync_after(2) as inner_ctx:
                time.sleep(1)
    t1 = time.perf_counter()

    assert not inner_ctx.cancelled()
    assert outer_ctx.cancelled()
    assert t1 - t0 < 1


def test_cancel_sync_nested_watchers_inner_cancelled(mock_alarm_signal_handler):
    t0 = time.perf_counter()
    with cancel_sync_after(1) as outer_ctx:
        with pytest.raises(TimeoutError):
            with cancel_sync_after(0.1) as inner_ctx:
                # this cancel method does not interrupt sleep calls, the timeout is
                # raised on the next instruction
                for _ in range(10):
                    time.sleep(0.1)
    t1 = time.perf_counter()

    assert not outer_ctx.cancelled()
    assert inner_ctx.cancelled()
    assert t1 - t0 < 1

    mock_alarm_signal_handler.assert_not_called(), "Alarm based handler should not be used"


def test_cancel_sync_nested_watchers_outer_cancelled(mock_alarm_signal_handler):
    t0 = time.perf_counter()

    with pytest.raises(TimeoutError):
        with cancel_sync_after(0.1) as outer_ctx:
            with cancel_sync_after(2) as inner_ctx:
                # this cancel method does not interrupt sleep calls, the timeout is
                # raised on the next instruction
                for _ in range(10):
                    time.sleep(0.1)
    t1 = time.perf_counter()

    assert not inner_ctx.cancelled()
    assert outer_ctx.cancelled()
    assert t1 - t0 < 1

    mock_alarm_signal_handler.assert_not_called(), "Alarm based handler should not be used"


@pytest.mark.timeout(method="thread")  # alarm-based pytest-timeout will interfere
def test_cancel_sync_with_existing_alarm_handler(mock_alarm_signal_handler):
    t0 = time.perf_counter()

    with pytest.raises(TimeoutError):
        with cancel_sync_after(0.1) as ctx:
            # this cancel method does not interrupt sleep calls, the timeout is
            # raised on the next instruction
            for _ in range(10):
                time.sleep(0.1)
    t1 = time.perf_counter()

    assert ctx.cancelled()
    assert t1 - t0 < 1
    mock_alarm_signal_handler.assert_not_called()
