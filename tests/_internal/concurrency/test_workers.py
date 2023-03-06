from unittest.mock import MagicMock

import pytest

from prefect._internal.concurrency.workers import Call, WorkerThread


def identity(x):
    return x


def test_worker_with_failure_in_start():
    worker = WorkerThread()

    # Simulate a failure during loop thread start
    worker._ready_future.set_result = MagicMock(side_effect=ValueError("test"))

    # The error should propagate to the main thread
    with pytest.raises(ValueError, match="test"):
        worker.start()


@pytest.mark.parametrize("daemon", [True, False])
def test_worker_daemon(daemon):
    worker = WorkerThread(daemon=daemon)
    worker.start()
    assert worker.thread.daemon is daemon
    worker.shutdown()


def test_worker_run_once():
    worker = WorkerThread(run_once=True)
    worker.start()

    call = Call.new(identity, 1)
    worker.submit(call)

    with pytest.raises(
        RuntimeError,
        match="Worker configured to only run once. A call has already been submitted.",
    ):
        worker.submit(call)

    assert call.future.result() == 1
    assert worker._shutdown_event.is_set()
