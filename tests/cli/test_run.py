import sys
from unittest.mock import MagicMock

import click
import pytest
import requests
from click.testing import CliRunner

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


@pytest.mark.skipif(
    sys.version_info < (3, 6), reason="3.5 does not preserve dictionary order"
)
def test_run_cloud(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data=dict(flow=[{"id": "flow"}])))
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

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
        assert post.call_args[1]["json"]["query"].split() == query.split()


@pytest.mark.skipif(
    sys.version_info < (3, 6), reason="3.5 does not preserve dictionary order"
)
def test_run_cloud_watch(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(
                return_value=dict(
                    data=dict(
                        flow=[{"id": "flow"}],
                        flow_run_by_pk=dict(
                            states=[
                                {"state": "Running", "timestamp": None},
                                {"state": "Success", "timestamp": None},
                            ]
                        ),
                    )
                )
            )
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    create_flow_run = MagicMock(resurn_value="id")
    monkeypatch.setattr(
        "prefect.client.Client.create_flow_run", MagicMock(return_value=create_flow_run)
    )

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(
            run,
            [
                "cloud",
                "--name",
                "flow",
                "--project",
                "project",
                "--version",
                "2",
                "--watch",
            ],
        )
        assert result.exit_code == 0
        assert "Running" in result.output
        assert "Success" in result.output
        assert post.called


@pytest.mark.skipif(
    sys.version_info < (3, 6), reason="3.5 does not preserve dictionary order"
)
def test_run_cloud_logs(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(
                return_value=dict(
                    data=dict(
                        flow=[{"id": "flow"}],
                        flow_run=[
                            {
                                "logs": [
                                    {
                                        "timestamp": "test_timestamp",
                                        "message": "test_message",
                                        "level": "test_level",
                                    }
                                ]
                            }
                        ],
                        flow_run_by_pk=dict(state="Success"),
                    )
                )
            )
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    create_flow_run = MagicMock(resurn_value="id")
    monkeypatch.setattr(
        "prefect.client.Client.create_flow_run", MagicMock(return_value=create_flow_run)
    )

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(
            run,
            [
                "cloud",
                "--name",
                "flow",
                "--project",
                "project",
                "--version",
                "2",
                "--logs",
            ],
        )
        assert result.exit_code == 0
        assert "test_timestamp" in result.output
        assert "test_message" in result.output
        assert "test_level" in result.output
        assert post.called


def test_run_cloud_fails(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(json=MagicMock(return_value=dict(data=dict(flow=[]))))
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(
            run, ["cloud", "--name", "flow", "--project", "project", "--version", "2"]
        )
        assert result.exit_code == 0
        assert "flow not found" in result.output
