from unittest.mock import MagicMock

import pytest

from prefect._internal.concurrency.calls import Call
from prefect._internal.concurrency.threads import EventLoopThread, WorkerThread


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
