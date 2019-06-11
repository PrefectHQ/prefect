from unittest.mock import MagicMock

import click
from click.testing import CliRunner
import requests

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


def test_execute_cloud_flow_fails():
    runner = CliRunner()
    result = runner.invoke(execute, "cloud-flow")
    assert result.exit_code == 1
    assert "Not currently executing a flow within a cloud context." in result.output


def test_execute_cloud_flow_not_found(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data=dict(flow_run=[])))
        )
    )
    monkeypatch.setattr("requests.post", post)

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        with prefect.context({"flow_run_id": "test"}):
            runner = CliRunner()
            result = runner.invoke(execute, "cloud-flow")

    assert result.exit_code == 1
    assert result.exc_info[0] == ValueError
    assert "Flow run test not found" in str(result.exc_info[1])
