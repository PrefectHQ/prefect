from unittest.mock import MagicMock

import pytest

from prefect._internal.concurrency.portals import Call, WorkerThreadPortal


def identity(x):
    return x


async def aidentity(x):
    return x


def test_worker_thread_with_failure_in_start():
    worker_thread = WorkerThreadPortal()

    # Simulate a failure during loop thread start
    worker_thread._ready_future.set_result = MagicMock(side_effect=ValueError("test"))

    # The error should propagate to the main thread
    with pytest.raises(ValueError, match="test"):
        worker_thread.start()


@pytest.mark.parametrize("daemon", [True, False])
def test_worker_thread_daemon(daemon):
    worker_thread = WorkerThreadPortal(daemon=daemon)
    worker_thread.start()
    assert worker_thread.thread.daemon is daemon
    worker_thread.shutdown()


def test_worker_thread_run_once():
    worker_thread = WorkerThreadPortal(run_once=True)
    worker_thread.start()

    call = Call.new(identity, 1)
    worker_thread.submit(call)

    with pytest.raises(
        RuntimeError,
        match="Worker configured to only run once. A call has already been submitted.",
    ):
        worker_thread.submit(call)

    assert call.future.result() == 1
    assert worker_thread._shutdown_event.is_set()


@pytest.mark.parametrize("work", [identity, aidentity])
def test_worker_thread_submit(work):
    worker_thread = WorkerThreadPortal()
    call = worker_thread.submit(Call.new(work, 1))
    assert call.result() == 1
    worker_thread.shutdown()
