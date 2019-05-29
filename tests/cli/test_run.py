from unittest.mock import MagicMock

import click
from click.testing import CliRunner
import requests

import prefect
from prefect.cli.run import run
from prefect.utilities.configuration import set_temporary_config


def test_run_init():
    runner = CliRunner()
    result = runner.invoke(run)
    assert result.exit_code == 0
    assert "Run Prefect flows." in result.output


def test_run_help():
    runner = CliRunner()
    result = runner.invoke(run, ["--help"])
    assert result.exit_code == 0
    assert "Run Prefect flows." in result.output


def test_run_local():
    runner = CliRunner()
    result = runner.invoke(run, ["local"])
    assert result.exit_code == 0


def test_run_docker():
    runner = CliRunner()
    result = runner.invoke(run, ["docker"])
    assert result.exit_code == 0


def test_run_cloud(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data=dict(flow=[{"id": "flow"}])))
        )
    )
    monkeypatch.setattr("requests.post", post)

    create_flow_run = MagicMock(resurn_value="id")
    monkeypatch.setattr(
        "prefect.client.Client.create_flow_run", MagicMock(return_value=create_flow_run)
    )

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(
            run, ["cloud", "--name", "flow", "--project", "project", "--version", "2"]
        )
        assert result.exit_code == 0
        assert "Flow Run ID" in result.output

        query = """
        query {
            flow(where: { _and: { name: { _eq: "flow" }, version: { _eq: 2 }, project: { name: { _eq: "project" } } } }, order_by: { name: asc, version: desc }, distinct_on: name) {
                id
            }
        }
        """

        assert post.called
        assert sorted(post.call_args[1]["json"]["query"].split()) == sorted(
            query.split()
        )


def test_run_cloud_fails(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(json=MagicMock(return_value=dict(data=dict(flow=[]))))
    )
    monkeypatch.setattr("requests.post", post)

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(
            run, ["cloud", "--name", "flow", "--project", "project", "--version", "2"]
        )
        assert result.exit_code == 0
        assert "flow not found" in result.output
