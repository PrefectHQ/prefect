"""
This file contains tests for the deprecated command `prefect run flow`
This command is replaced by `prefect run` which has tests at `test_run.py`
"""
import json
import os
import re
import tempfile
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner
from prefect.cli.run import run
from prefect.utilities.configuration import set_temporary_config


def test_run_help():
    runner = CliRunner()
    result = runner.invoke(run, ["flow", "--help"])
    assert result.exit_code == 0
    assert "Usage: run flow" in result.output


def test_run_flow(monkeypatch, cloud_api):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data=dict(flow=[{"id": "flow"}])))
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

    runner = CliRunner()
    result = runner.invoke(
        run, ["flow", "--name", "flow", "--project", "project", "--version", "2"]
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


def test_run_flow_watch(monkeypatch, cloud_api):
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

    runner = CliRunner()
    result = runner.invoke(
        run,
        [
            "flow",
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


def test_run_flow_logs(monkeypatch, cloud_api):
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

    runner = CliRunner()
    result = runner.invoke(
        run,
        ["flow", "--name", "flow", "--project", "project", "--version", "2", "--logs"],
    )
    assert result.exit_code == 0
    assert "test_timestamp" in result.output
    assert "test_message" in result.output
    assert "test_level" in result.output
    assert post.called


def test_run_flow_fails(monkeypatch, cloud_api):
    post = MagicMock(
        return_value=MagicMock(json=MagicMock(return_value=dict(data=dict(flow=[]))))
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    runner = CliRunner()
    result = runner.invoke(
        run, ["flow", "--name", "flow", "--project", "project", "--version", "2"]
    )
    assert result.exit_code == 0
    assert "flow not found" in result.output


def test_run_flow_no_param_file(monkeypatch, cloud_api):
    runner = CliRunner()
    result = runner.invoke(
        run,
        [
            "flow",
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


def test_run_flow_param_file(monkeypatch, cloud_api):
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

        runner = CliRunner()
        result = runner.invoke(
            run,
            [
                "flow",
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


def test_run_flow_no_labels_provided(monkeypatch, cloud_api):
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

    runner = CliRunner()
    result = runner.invoke(
        run,
        [
            "flow",
            "--name",
            "flow",
            "--project",
            "project",
        ],
    )
    assert result.exit_code == 0
    assert "Flow Run" in result.output
    assert create_flow_run_mock.called
    assert create_flow_run_mock.call_args[1]["labels"] is None


def test_run_flow_param_string(monkeypatch, cloud_api):
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

    runner = CliRunner()
    result = runner.invoke(
        run,
        [
            "flow",
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


def test_run_flow_context_string(monkeypatch, cloud_api):
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

    runner = CliRunner()
    result = runner.invoke(
        run,
        [
            "flow",
            "--name",
            "flow",
            "--project",
            "project",
            "--version",
            "2",
            "--context",
            '{"test": 42}',
        ],
    )
    assert result.exit_code == 0
    assert "Flow Run" in result.output
    assert create_flow_run_mock.called
    assert create_flow_run_mock.call_args[1]["context"] == {"test": 42}


def test_run_flow_run_name(monkeypatch, cloud_api):
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

    runner = CliRunner()
    result = runner.invoke(
        run,
        [
            "flow",
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


def test_run_flow_param_string_overwrites(monkeypatch, cloud_api):
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

        runner = CliRunner()
        result = runner.invoke(
            run,
            [
                "flow",
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
def test_run_flow_flow_run_id_link(monkeypatch, api, expected, cloud_api):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(
                return_value=dict(
                    data=dict(flow=[{"id": "flow"}], tenant=[{"id": "id"}])
                )
            )
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
            run, ["flow", "--name", "flow", "--project", "project", "--version", "2"]
        )
        assert result.exit_code == 0
        assert "Flow Run" in result.output
        assert expected in result.output


def test_run_flow_flow_run_id_no_link(monkeypatch, cloud_api):
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

    runner = CliRunner()
    result = runner.invoke(
        run,
        [
            "flow",
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


def test_run_flow_using_id(monkeypatch, cloud_api):
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

    runner = CliRunner()
    result = runner.invoke(
        run,
        ["flow", "--id", "id"],
    )
    assert result.exit_code == 0
    assert "Flow Run" in result.output
    assert create_flow_run_mock.called


def test_run_flow_labels(monkeypatch, cloud_api):
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

    runner = CliRunner()
    result = runner.invoke(
        run,
        [
            "flow",
            "--name",
            "flow",
            "--project",
            "project",
            "--label",
            "label1",
            "--label",
            "label2",
        ],
    )
    assert result.exit_code == 0
    assert "Flow Run" in result.output
    assert create_flow_run_mock.called


def test_run_flow_using_version_group_id(monkeypatch, cloud_api):
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

    runner = CliRunner()
    result = runner.invoke(
        run,
        ["flow", "--version-group-id", "v_id"],
    )
    assert result.exit_code == 0
    assert "Flow Run" in result.output
    assert create_flow_run_mock.called


def test_run_flow_no_id_or_name_and_project():
    runner = CliRunner()
    result = runner.invoke(
        run,
        [
            "flow",
        ],
    )
    assert (
        "A flow ID, version group ID, or a combination of flow name and project must be provided."
        in result.output
    )


def test_run_flow_no_id_or_name_and_project():
    runner = CliRunner()
    result = runner.invoke(
        run,
        [
            "flow",
            "--id",
            "id",
            "--name",
            "flow",
            "--project",
            "project",
        ],
    )
    assert (
        "Only one of flow ID, version group ID, or a name/project combination can be provided."
        in result.output
    )
