import concurrent.futures
from unittest.mock import MagicMock, call

import pytest

from prefect._internal.concurrency.calls import Call
from prefect._internal.concurrency.threads import EventLoopThread, WorkerThread
from prefect.testing.utilities import AsyncMock


def identity(x):
    return x


async def aidentity(x):
    return x


def test_event_loop_thread_with_failure_in_start():
    event_loop_thread = EventLoopThread()

    # Simulate a failure during loop thread start
    event_loop_thread._ready_future.set_result = MagicMock(
        side_effect=ValueError("test")
    )

    # The error should propagate to the main thread
    with pytest.raises(ValueError, match="test"):
        event_loop_thread.start()


def test_event_loop_thread_start_race_condition():
    event_loop_thread = EventLoopThread()
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for _ in range(10):
            executor.submit(event_loop_thread.start)

    event_loop_thread.shutdown()


def test_event_loop_thread_with_on_shutdown_hook():
    event_loop_thread = EventLoopThread()
    mock = AsyncMock()

    event_loop_thread.start()
    event_loop_thread.add_shutdown_call(Call.new(mock))
    mock.assert_not_called()

    event_loop_thread.shutdown()
    event_loop_thread.thread.join()
    mock.assert_awaited_once()


def test_event_loop_thread_with_on_shutdown_hooks():
    event_loop_thread = EventLoopThread()
    mock = AsyncMock()

    event_loop_thread.start()
    for i in range(5):
        event_loop_thread.add_shutdown_call(Call.new(mock, i))
    mock.assert_not_called()

    event_loop_thread.shutdown()
    event_loop_thread.thread.join()

    mock.assert_has_awaits(call(i) for i in range(5))


def test_event_loop_thread_clears_shutdown_hooks_after_shutdown():
    event_loop_thread = EventLoopThread()

    event_loop_thread.start()
    for i in range(5):
        event_loop_thread.add_shutdown_call(Call.new(AsyncMock(), i))
    event_loop_thread.shutdown()
    event_loop_thread.thread.join()

    assert not event_loop_thread._on_shutdown


@pytest.mark.parametrize("thread_cls", [WorkerThread, EventLoopThread])
@pytest.mark.parametrize("daemon", [True, False])
def test_thread_daemon(daemon, thread_cls):
    thread = thread_cls(daemon=daemon)
    thread.start()
    assert thread.thread.daemon is daemon
    thread.shutdown()


@pytest.mark.parametrize("thread_cls", [WorkerThread, EventLoopThread])
def test_thread_run_once(thread_cls):
    thread = thread_cls(run_once=True)
    thread.start()

    call = Call.new(identity, 1)
    thread.submit(call)

    with pytest.raises(
        RuntimeError,
        match="Worker configured to only run once. A call has already been submitted.",
    ):
        thread.submit(Call.new(identity, 1))

    assert call.future.result() == 1


@pytest.mark.parametrize("thread_cls", [WorkerThread, EventLoopThread])
@pytest.mark.parametrize("work", [identity, aidentity])
def test_thread_submit(work, thread_cls):
    thread = thread_cls()
    call = thread.submit(Call.new(work, 1))
    assert call.result() == 1
    thread.shutdown()
