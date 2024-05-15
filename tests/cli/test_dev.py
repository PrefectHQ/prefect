import watchfiles

import prefect
from prefect.testing.cli import invoke_and_assert
from prefect.testing.utilities import AsyncMock, MagicMock


def test_dev_start_runs_all_services(monkeypatch):
    """
    Test that `prefect dev start` runs all services. This test mocks out the
    `run_process` function along with the `watchfiles.arun_process` function
    so the test doesn't actually start any processes; instead, it verifies that
    the command attempts to start all services correctly.
    """

    # Mock run_process for UI and API start
    mock_run_process = AsyncMock()

    # Call task_status.started() if run_process was triggered by an
    # anyio task group `start` call.
    def mock_run_process_call(*args, **kwargs):
        if "task_status" in kwargs:
            kwargs["task_status"].started()

    mock_run_process.side_effect = mock_run_process_call
    monkeypatch.setattr(prefect.cli.dev, "run_process", mock_run_process)

    # mock `os.kill` since we're not actually running the processes
    mock_kill = MagicMock()
    monkeypatch.setattr(prefect.cli.dev.os, "kill", mock_kill)

    # mock watchfiles.awatch
    mock_awatch = MagicMock()

    # mock_awatch needs to return an async generator
    async def async_generator():
        yield None

    mock_awatch.return_value = async_generator()
    monkeypatch.setattr(watchfiles, "awatch", mock_awatch)

    invoke_and_assert(["dev", "start"], expected_code=0)

    # ensure one of the calls to run_process was for the UI server
    mock_run_process.assert_any_call(
        command=["npm", "run", "serve"], stream_output=True
    )

    # ensure run_process was called for the API server by checking that
    # the 'command' passed to one of the calls was an array with "uvicorn" included
    uvicorn_called = False
    for call in mock_run_process.call_args_list:
        if "command" in call.kwargs and "uvicorn" in call.kwargs["command"]:
            uvicorn_called = True
            break

    assert uvicorn_called
