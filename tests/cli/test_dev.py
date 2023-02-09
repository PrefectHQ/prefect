import inspect

import watchfiles
from typer import Option

import prefect
from prefect.cli.dev import agent_process_entrypoint, start_agent
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

    # Mock watchfiles.arun_process for agent start
    mock_arun_process = AsyncMock()
    monkeypatch.setattr(watchfiles, "arun_process", mock_arun_process)

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

    # check that arun_process was called for the agent
    mock_arun_process.assert_called_once()

    # ensure one of the calls to run_process was for the UI server
    mock_run_process.assert_any_call(
        command=["npm", "run", "serve"], stream_output=True
    )

    # ensure run_process was called for the API server by checking that
    # the 'command' passed to one of the calls was an array with "uvicorn"
    # as the first element
    uvicorn_called = False
    for call in mock_run_process.call_args_list:
        if "command" in call.kwargs and call.kwargs["command"][0] == "uvicorn":
            uvicorn_called = True
            break

    assert uvicorn_called


def test_agent_subprocess_entrypoint_runs_agent_with_valid_params(monkeypatch):
    mock_agent_start = MagicMock()
    monkeypatch.setattr(prefect.cli.dev, "start_agent", mock_agent_start)

    api = "http://127.0.0.1:4200"
    work_queues = ["default"]

    start_agent_signature = inspect.signature(start_agent)
    start_agent_params = start_agent_signature.parameters
    mock_agent_start.__signature__ = start_agent_signature

    agent_process_entrypoint(api=api, work_queues=work_queues)

    # Get the call's kwargs from the mock
    call_args = mock_agent_start.call_args[1]

    # Ensure that types of the call_args match the types of the start_agent.
    # This verifies that defaults are extracted from Typer.Argument and
    # Typer.Option before calling start_agent.
    for param_name, param in start_agent_params.items():
        # arguments using Typer.Argument or Typer.Option are implicitly a union of the
        # declared argument type and NoneType. So, we need to check if the call arg
        # is either the declared type or NoneType.

        # check if the type is subscripted, because we can't use isinstance
        # on subscripted types
        if hasattr(param.annotation, "__origin__"):
            # if so, use subscripted type
            arg_type = param.annotation.__origin__
        else:
            # otherwise, use the type
            arg_type = param.annotation

        assert (
            isinstance(call_args[param_name], arg_type) or call_args[param_name] is None
        )

    # Ensure that the call args we passed to agent_process_entrypoint are
    # passed to start_agent and not accidentally overwritten by default values.
    assert call_args["api"] == api
    assert call_args["work_queues"] == work_queues


# ensures that the default values for the agent start function are extracted
# correctly in cases where some of them are Typer.OptionInfo or Typer.ArgumentInfo
# and others are normal Python defaults
def test_mixed_parameter_default_types(monkeypatch):
    mock_agent_start = MagicMock()
    monkeypatch.setattr(prefect.cli.dev, "start_agent", mock_agent_start)

    # mock the signature of start_agent to have a mix of Typer.OptionInfo
    # and normal Python defaults
    start_agent_signature = inspect.Signature(
        parameters=[
            inspect.Parameter(  # Typer.OptionInfo
                name="api",
                kind=inspect.Parameter.KEYWORD_ONLY,
                default=Option(
                    None,
                    "--api",
                    help="The URL of the Prefect API server",
                ),
            ),
            inspect.Parameter(  # normal Python default
                name="work_queues",
                kind=inspect.Parameter.KEYWORD_ONLY,
                default=["default"],
            ),
        ]
    )
    mock_agent_start.__signature__ = start_agent_signature

    agent_process_entrypoint()

    # if we get this far without errors, it means the entrypoint function
    # successfully extracted the mixed default arguments
    mock_agent_start.assert_called_once()


def test_agent_subprocess_entrypoint_adds_typer_console(monkeypatch):
    """
    Ensures a Rich console is added to the PrefectTyper's global `app` instance.
    """
    start_agent_signature = inspect.signature(start_agent)

    mock_agent_start = MagicMock()
    mock_agent_start.__signature__ = start_agent_signature
    monkeypatch.setattr(prefect.cli.dev, "start_agent", mock_agent_start)

    mock_app = MagicMock()
    monkeypatch.setattr(prefect.cli.dev, "app", mock_app)

    agent_process_entrypoint()

    # ensure the console was added to the app
    assert mock_app.console is not None
