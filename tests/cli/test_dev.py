import inspect
from types import NoneType
from typing import Type
import prefect

from prefect.cli.dev import agent_process_entrypoint, start_agent
from prefect.testing.utilities import MagicMock


def test_agent_subprocess_entrypoint_runs_agent_with_valid_params(monkeypatch):
    mock_agent_start = MagicMock()

    monkeypatch.setattr(prefect.cli.dev, "start_agent", mock_agent_start)

    api = "http://127.0.0.1:4200"
    work_queues = ["default"]

    start_agent_signature = inspect.signature(start_agent)
    start_agent_params = start_agent_signature.parameters

    # We are mocking the start_agent function, but agent_process_entrypoint checks
    # the signature of start_agent to extract default values from Typer objects.
    # So, we also need to mock inspect.signature to return the signature of
    # start_agent and not the signature of the mock.
    mock_signature = MagicMock(parameters=start_agent_params)
    monkeypatch.setattr(inspect, "signature", lambda _: mock_signature)

    agent_process_entrypoint(api=api, work_queues=work_queues)

    call_args: dict = mock_agent_start.call_args.kwargs

    # Ensure that types of the call_args match the types of the start_agent.
    # This verifies that defaults are extracted from Typer.Argument and
    # Typer.Option before calling start_agent.
    for param_name, param in start_agent_params.items():
        # arguments using Typer.Argument or Typer.Option are implicitly a union of the
        # declared argument type and NoneType. So, we need to check if the call arg
        # is either the declared type or NoneType.

        arg_type: Type = NoneType
        # check if the type is subscripted
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


def test_agent_subprocess_entrypoint_adds_typer_console(monkeypatch):
    """
    Ensures a Rich console is added to the PrefectTyper's global `app` instance.
    """
    mock_agent_start = MagicMock()
    monkeypatch.setattr(prefect.cli.dev, "start_agent", mock_agent_start)

    # ensure agent_subprocess_entrypoint gets the correct signature
    # and not the signature of the mock
    mock_signature = MagicMock(parameters=inspect.signature(start_agent).parameters)
    monkeypatch.setattr(inspect, "signature", lambda _: mock_signature)

    # mock the `app` instance to ensure it is not None
    mock_app = MagicMock()
    monkeypatch.setattr(prefect.cli.dev, "app", mock_app)

    agent_process_entrypoint()

    # ensure the console was added to the app
    assert mock_app.console is not None
