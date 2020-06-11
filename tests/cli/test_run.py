import json
import os
import re
import tempfile
from unittest.mock import MagicMock

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


def test_run_cloud(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data=dict(flow=[{"id": "flow"}],)))
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    monkeypatch.setattr(
        "prefect.client.Client.create_flow_run", MagicMock(return_value="id")
    )
    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    with set_temporary_config(
        {"cloud.api": "http://api.prefect.io", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(
            run, ["cloud", "--name", "flow", "--project", "project", "--version", "2"]
        )
        assert result.exit_code == 0
        assert "Flow Run" in result.output

        query = """
        query {
            flow(where: { _and: { name: { _eq: "flow" }, version: { _eq: 2 }, project: { name: { _eq: "project" } } } }, order_by: { name: asc, version: desc }, distinct_on: name) {
                id
            }
        }
        """

        assert post.called
        assert post.call_args[1]["json"]["query"].split() == query.split()


def test_run_server(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data=dict(flow=[{"id": "flow"}],)))
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    monkeypatch.setattr(
        "prefect.client.Client.create_flow_run", MagicMock(return_value="id")
    )
    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    with set_temporary_config(
        {"cloud.api": "http://localhost:4200", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(run, ["server", "--name", "flow", "--version", "2"])
        assert result.exit_code == 0
        assert "Flow Run" in result.output

        query = """
        query {
            flow(where: { _and: { name: { _eq: "flow" }, version: { _eq: 2 } } }, order_by: { name: asc, version: desc }, distinct_on: name) {
                id
            }
        }
        """

        assert post.called
        assert post.call_args[1]["json"]["query"].split() == query.split()


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

    monkeypatch.setattr(
        "prefect.client.Client.create_flow_run", MagicMock(return_value="id")
    )
    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    with set_temporary_config(
        {"cloud.api": "http://api.prefect.io", "cloud.auth_token": "secret_token"}
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
                                ],
                                "state": "Success",
                            }
                        ],
                    )
                )
            )
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    monkeypatch.setattr(
        "prefect.client.Client.create_flow_run", MagicMock(return_value="id")
    )
    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    with set_temporary_config(
        {"cloud.api": "http://api.prefect.io", "cloud.auth_token": "secret_token"}
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
        {"cloud.api": "http://api.prefect.io", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(
            run, ["cloud", "--name", "flow", "--project", "project", "--version", "2"]
        )
        assert result.exit_code == 0
        assert "flow not found" in result.output


def test_run_cloud_no_param_file(monkeypatch):
    with set_temporary_config(
        {"cloud.api": "http://api.prefect.io", "cloud.auth_token": "secret_token"}
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
                "--parameters-file",
                "no_file.json",
            ],
        )
        assert result.exit_code == 2
        # note: click changed the output format for errors between 7.0 & 7.1, this test should be agnostic to which click version is used.
        # ensure message ~= Invalid value for "--parameters-file" / "-pf": Path "no_file.json" does not exist
        assert re.search(
            r"Invalid value for [\"']--parameters-file", result.output, re.MULTILINE
        )
        assert re.search(
            r"Path [\"']no_file.json[\"'] does not exist", result.output, re.MULTILINE
        )


def test_run_cloud_param_file(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data=dict(flow=[{"id": "flow"}])))
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    create_flow_run_mock = MagicMock(return_value="id")
    monkeypatch.setattr("prefect.client.Client.create_flow_run", create_flow_run_mock)
    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    with tempfile.TemporaryDirectory() as directory:
        file_path = os.path.join(directory, "file.json")
        with open(file_path, "w") as tmp:
            json.dump({"test": 42}, tmp)

        with set_temporary_config(
            {"cloud.api": "http://api.prefect.io", "cloud.auth_token": "secret_token"}
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
                    "--parameters-file",
                    file_path,
                ],
            )
            assert result.exit_code == 0
            assert "Flow Run" in result.output
            assert create_flow_run_mock.called
            assert create_flow_run_mock.call_args[1]["parameters"] == {"test": 42}


def test_run_cloud_param_string(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data=dict(flow=[{"id": "flow"}])))
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    create_flow_run_mock = MagicMock(return_value="id")
    monkeypatch.setattr("prefect.client.Client.create_flow_run", create_flow_run_mock)
    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    with set_temporary_config(
        {"cloud.api": "http://api.prefect.io", "cloud.auth_token": "secret_token"}
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
                "--parameters-string",
                '{"test": 42}',
            ],
        )
        assert result.exit_code == 0
        assert "Flow Run" in result.output
        assert create_flow_run_mock.called
        assert create_flow_run_mock.call_args[1]["parameters"] == {"test": 42}


def test_run_cloud_run_name(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data=dict(flow=[{"id": "flow"}])))
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    create_flow_run_mock = MagicMock(return_value="id")
    monkeypatch.setattr("prefect.client.Client.create_flow_run", create_flow_run_mock)
    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    with set_temporary_config(
        {"cloud.api": "http://api.prefect.io", "cloud.auth_token": "secret_token"}
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
                "--run-name",
                "NAME",
            ],
        )
        assert result.exit_code == 0
        assert "Flow Run" in result.output
        assert create_flow_run_mock.called
        assert create_flow_run_mock.call_args[1]["run_name"] == "NAME"


def test_run_cloud_param_string_overwrites(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data=dict(flow=[{"id": "flow"}])))
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    create_flow_run_mock = MagicMock(return_value="id")
    monkeypatch.setattr("prefect.client.Client.create_flow_run", create_flow_run_mock)
    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    with tempfile.TemporaryDirectory() as directory:
        file_path = os.path.join(directory, "file.json")
        with open(file_path, "w") as tmp:
            json.dump({"test": 42}, tmp)

        with set_temporary_config(
            {"cloud.api": "http://api.prefect.io", "cloud.auth_token": "secret_token"}
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
                    "--parameters-file",
                    file_path,
                    "--parameters-string",
                    '{"test": 43}',
                ],
            )
            assert result.exit_code == 0
            assert "Flow Run" in result.output
            assert create_flow_run_mock.called
            assert create_flow_run_mock.call_args[1]["parameters"] == {"test": 43}


@pytest.mark.parametrize(
    "api,expected",
    [
        ("https://api.prefect.io", "https://cloud.prefect.io/tslug/flow-run/id"),
        ("https://api-foo.prefect.io", "https://foo.prefect.io/tslug/flow-run/id"),
    ],
)
def test_run_cloud_flow_run_id_link(monkeypatch, api, expected, cloud_api):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data=dict(flow=[{"id": "flow"}])))
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    create_flow_run_mock = MagicMock(return_value="id")
    monkeypatch.setattr("prefect.client.Client.create_flow_run", create_flow_run_mock)
    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    with set_temporary_config({"cloud.api": api, "cloud.auth_token": "secret_token"}):
        runner = CliRunner()
        result = runner.invoke(
            run, ["cloud", "--name", "flow", "--project", "project", "--version", "2",],
        )
        assert result.exit_code == 0
        assert "Flow Run" in result.output
        assert expected in result.output


def test_run_cloud_flow_run_id_no_link(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data=dict(flow=[{"id": "flow"}])))
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    create_flow_run_mock = MagicMock(return_value="id")
    monkeypatch.setattr("prefect.client.Client.create_flow_run", create_flow_run_mock)
    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    with set_temporary_config(
        {"cloud.api": "https://api.foo", "cloud.auth_token": "secret_token"}
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
                "--no-url",
            ],
        )
        assert result.exit_code == 0
        assert "Flow Run ID" in result.output
