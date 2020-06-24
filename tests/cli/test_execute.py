from unittest.mock import MagicMock, PropertyMock

from click.testing import CliRunner

import prefect
from prefect.cli.execute import execute
from prefect.utilities.configuration import set_temporary_config


def test_execute_init():
    runner = CliRunner()
    result = runner.invoke(execute)
    assert result.exit_code == 0
    assert "Execute flow environments." in result.output


def test_execute_help():
    runner = CliRunner()
    result = runner.invoke(execute, ["--help"])
    assert result.exit_code == 0
    assert "Execute flow environments." in result.output


def test_execute_cloud_flow_fails_outside_cloud_context():
    runner = CliRunner()
    result = runner.invoke(execute, "cloud-flow")
    assert result.exit_code == 1
    assert "Not currently executing a flow within a Cloud context." in result.output
    assert "Not currently executing a flow within a Cloud context." in str(
        result.exc_info[1]
    )


def test_execute_cloud_flow_not_found(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data=dict(flow_run=[])))
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        with prefect.context({"flow_run_id": "test"}):
            runner = CliRunner()
            result = runner.invoke(execute, "cloud-flow")

    assert result.exit_code == 1
    assert "Flow run test not found" in result.output
    assert result.exc_info[0] == ValueError
    assert "Flow run test not found" in str(result.exc_info[1])


def test_execute_cloud_flow_fails(monkeypatch):
    flow = MagicMock()
    type(flow).storage = PropertyMock(side_effect=SyntaxError("oops"))
    data = MagicMock(data=MagicMock(flow_run=[MagicMock(flow=flow)]))
    client = MagicMock()
    client.return_value.graphql.return_value = data
    monkeypatch.setattr("prefect.cli.execute.Client", client)

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        with prefect.context({"flow_run_id": "test"}):
            runner = CliRunner()
            result = runner.invoke(execute, "cloud-flow")

    assert result.exit_code == 1
    assert "oops" in result.output
    assert result.exc_info[0] == SyntaxError
    assert client.return_value.set_flow_run_state.call_args[1]["flow_run_id"] == "test"
    assert client.return_value.set_flow_run_state.call_args[1]["state"].is_failed()
    assert (
        "Failed to load"
        in client.return_value.set_flow_run_state.call_args[1]["state"].message
    )


def test_execute_cloud_flow_raises_exception():

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(execute, "cloud-flow")
        assert result.exit_code == 1
        assert "Not currently executing a flow within a Cloud context." in result.output
