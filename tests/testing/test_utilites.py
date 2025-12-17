import gc
import sys
import uuid
import warnings
from unittest.mock import MagicMock

import pytest

from prefect import flow, task
from prefect.client.orchestration import get_client
from prefect.server import schemas
from prefect.settings import (
    PREFECT_API_DATABASE_CONNECTION_URL,
    PREFECT_API_URL,
    PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS,
)
from prefect.testing.utilities import assert_does_not_warn, prefect_test_harness


def _multiprocessing_worker():
    """
    Worker function for multiprocessing test. Must be at module level for pickling.
    """
    import os

    # os._exit() is required here despite the underscore prefix. On Linux with fork(),
    # the child process inherits Prefect's logging/event state. Normal exit (return or
    # sys.exit) triggers Python cleanup that fails with this inherited state, causing
    # exitcode=1. os._exit() bypasses cleanup and is documented for use "in the child
    # process after os.fork()" - which is exactly this scenario.
    os._exit(0)


def test_assert_does_not_warn_no_warning():
    with assert_does_not_warn():
        pass


def test_assert_does_not_warn_does_not_capture_exceptions():
    with pytest.raises(ValueError):
        with assert_does_not_warn():
            raise ValueError()


def test_assert_does_not_warn_raises_assertion_error():
    with pytest.raises(AssertionError, match="Warning was raised"):
        with assert_does_not_warn():
            warnings.warn("Test")


async def test_prefect_test_harness():
    # TODO: This test fails intermittently with a directory error in Windows
    # due to temporary directory differences
    very_specific_name = str(uuid.uuid4())

    @task
    def test_task():
        pass

    @flow(name=very_specific_name)
    def test_flow():
        test_task()
        return "foo"

    existing_db_url = PREFECT_API_DATABASE_CONNECTION_URL.value()
    existing_api_url = PREFECT_API_URL.value()

    with prefect_test_harness():
        async with get_client() as client:
            # should be able to run a flow
            assert test_flow() == "foo"

            # should be able to query for generated data
            flows = await client.read_flows(
                flow_filter=schemas.filters.FlowFilter(
                    name={"any_": [very_specific_name]}
                )
            )
            assert len(flows) == 1
            assert flows[0].name == very_specific_name

            assert PREFECT_API_URL.value() != existing_api_url

    # API URL should be reset
    assert PREFECT_API_URL.value() == existing_api_url

    # database connection should be reset
    assert PREFECT_API_DATABASE_CONNECTION_URL.value() == existing_db_url

    # outside the context, none of the test runs should not persist
    async with get_client() as client:
        flows = await client.read_flows(
            flow_filter=schemas.filters.FlowFilter(name={"any_": [very_specific_name]})
        )
        assert len(flows) == 0


def test_prefect_test_harness_timeout(monkeypatch):
    server = MagicMock()
    monkeypatch.setattr(
        "prefect.testing.utilities.SubprocessASGIServer",
        server,
    )
    server().api_url = "http://localhost:42000"

    with prefect_test_harness():
        server().start.assert_called_once_with(timeout=30)

    server().start.reset_mock()

    with prefect_test_harness(server_startup_timeout=120):
        server().start.assert_called_once_with(timeout=120)

    server().start.reset_mock()

    with prefect_test_harness(server_startup_timeout=None):
        server().start.assert_called_once_with(
            timeout=PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS.value()
        )


@pytest.mark.skipif(sys.platform == "win32", reason="fork() not available on Windows")
def test_multiprocessing_after_test_harness():
    """
    Test that multiprocessing works after using prefect_test_harness.

    Regression test for issue #19112 - on Linux, multiprocessing.Process() would
    deadlock after using the test harness because fork() inherited locked thread
    state from background threads.
    """
    import multiprocessing

    @task
    def test_task():
        return 1

    @flow
    def test_flow():
        return test_task.submit()

    # Use test harness which starts background threads
    with prefect_test_harness():
        test_flow()

    # This should not deadlock
    process = multiprocessing.Process(target=_multiprocessing_worker)
    process.start()
    process.join(timeout=5)

    # Verify process completed successfully
    assert process.exitcode == 0, "Process should complete without deadlock"


def test_prefect_test_harness_multiple_runs():
    """
    Test that running prefect_test_harness multiple times doesn't cause errors.

    Regression test for issue #19342 - running the test harness multiple times
    in the same process would cause FOREIGN KEY constraint failures because the
    EventsWorker singleton persisted stale events across harness sessions.
    """

    @task
    def example_task():
        return "task completed"

    @flow
    def example_flow():
        return example_task()

    # Run the test harness twice - the second run would fail with the bug
    with prefect_test_harness():
        result1 = example_flow()
        assert result1 == "task completed"

    with prefect_test_harness():
        result2 = example_flow()
        assert result2 == "task completed"


@pytest.mark.filterwarnings("error::pytest.PytestUnraisableExceptionWarning")
async def test_prefect_test_harness_async_cleanup():
    """
    Test that prefect_test_harness properly cleans up in async contexts.

    Regression test for issue #19762 - when prefect_test_harness is used in an
    async context, the drain_all() and drain() calls return coroutines that were
    never awaited, causing RuntimeWarning: coroutine 'wait' was never awaited.
    """
    with prefect_test_harness():
        pass
    # Force garbage collection to trigger finalization of any unawaited coroutines
    gc.collect()
