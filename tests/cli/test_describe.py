import json
import yaml
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from prefect.cli.describe import describe
from prefect.utilities.configuration import set_temporary_config


def test_describe_init():
    runner = CliRunner()
    result = runner.invoke(describe)
    assert result.exit_code == 0
    assert "Output information about different Prefect objects." in result.output


def test_describe_help():
    runner = CliRunner()
    result = runner.invoke(describe, ["--help"])
    assert result.exit_code == 0
    assert "Output information about different Prefect objects." in result.output


def test_describe_flows(monkeypatch, cloud_api):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data=dict(flow=[{"name": "flow"}])))
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    runner = CliRunner()
    result = runner.invoke(describe, ["flows", "--name", "flow", "--project", "proj"])
    assert result.exit_code == 0
    assert "name" in result.output

    query = """
    query {
        flow(where: { _and: { name: { _eq: "flow" }, version: { _eq: null }, project: { name: { _eq: "proj" } } } }, order_by: { name: asc, version: desc }, distinct_on: name) {
            name
            version
            project {
                name
            }
            created
            description
            parameters
            archived
            storage
            environment
        }
    }
    """

    assert post.called
    assert post.call_args[1]["json"]["query"].split() == query.split()


def test_describe_flows_not_found(monkeypatch, cloud_api):
    post = MagicMock(
        return_value=MagicMock(json=MagicMock(return_value=dict(data=dict(flow=[]))))
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    runner = CliRunner()
    result = runner.invoke(describe, ["flows", "--name", "flow"])
    assert result.exit_code == 0
    assert "flow not found" in result.output


def test_describe_flows_populated(monkeypatch, cloud_api):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data=dict(flow=[{"name": "flow"}])))
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    runner = CliRunner()
    result = runner.invoke(
        describe,
        ["flows", "--name", "flow", "--version", "2", "--project", "project"],
    )
    assert result.exit_code == 0

    query = """
    query {
        flow(where: { _and: { name: { _eq: "flow" }, version: { _eq: 2 }, project: { name: { _eq: "project" } } } }, order_by: { name: asc, version: desc }, distinct_on: name) {
            name
            version
            project {
                name
            }
            created
            description
            parameters
            archived
            storage
            environment
        }
    }
    """

    assert post.called
    assert post.call_args[1]["json"]["query"].split() == query.split()


@pytest.mark.parametrize("output", ["json", "yaml"])
def test_describe_flows_output(monkeypatch, output, cloud_api):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data=dict(flow=[{"name": "flow"}])))
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    runner = CliRunner()
    result = runner.invoke(
        describe,
        ["flows", "--name", "flow", "--project", "proj", "--output", output],
    )
    assert result.exit_code == 0

    if output == "json":
        res = json.loads(result.output)
    elif output == "yaml":
        res = yaml.safe_load(result.output)
    assert res == {"name": "flow"}


def test_describe_tasks(monkeypatch, cloud_api):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(
                return_value=dict(data=dict(flow=[{"tasks": [{"name": "task"}]}]))
            )
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    runner = CliRunner()
    result = runner.invoke(describe, ["tasks", "--name", "flow", "--project", "proj"])
    assert result.exit_code == 0
    assert "name" in result.output

    query = """
    query {
        flow(where: { _and: { name: { _eq: "flow" }, version: { _eq: null }, project: { name: { _eq: "proj" } } } }, order_by: { name: asc, version: desc }, distinct_on: name) {
            tasks {
                name
                created
                slug
                description
                type
                max_retries
                retry_delay
                mapped
            }
        }
    }
    """

    assert post.called
    assert post.call_args[1]["json"]["query"].split() == query.split()


def test_describe_tasks_flow_not_found(monkeypatch, cloud_api):
    post = MagicMock(
        return_value=MagicMock(json=MagicMock(return_value=dict(data=dict(flow=[]))))
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    runner = CliRunner()
    result = runner.invoke(describe, ["tasks", "--name", "flow"])
    assert result.exit_code == 0
    assert "flow not found" in result.output


def test_describe_tasks_not_found(monkeypatch, cloud_api):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data=dict(flow=[{"tasks": []}])))
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    runner = CliRunner()
    result = runner.invoke(describe, ["tasks", "--name", "flow"])
    assert result.exit_code == 0
    assert "No tasks found for flow flow" in result.output


@pytest.mark.parametrize("output", ["json", "yaml"])
def test_describe_tasks_output(monkeypatch, output, cloud_api):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(
                return_value=dict(data=dict(flow=[{"tasks": [{"name": "task"}]}]))
            )
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    runner = CliRunner()
    result = runner.invoke(
        describe,
        ["tasks", "--name", "flow", "--project", "proj", "--output", output],
    )
    assert result.exit_code == 0

    if output == "json":
        res = json.loads(result.output)
    elif output == "yaml":
        res = yaml.safe_load(result.output)
    assert res == [{"name": "task"}]


def test_describe_flow_runs(monkeypatch, cloud_api):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(
                return_value=dict(data=dict(flow_run=[{"name": "flow-run"}]))
            )
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    runner = CliRunner()
    result = runner.invoke(describe, ["flow-runs", "--name", "flow-run"])
    assert result.exit_code == 0
    assert "name" in result.output

    query = """
    query {
        flow_run(where: { _and: { name: { _eq: "flow-run" }, flow: { name: { _eq: null } } } }) {
            name
            flow {
                name
            }
            created
            parameters
            auto_scheduled
            scheduled_start_time
            start_time
            end_time
            serialized_state
        }
    }
    """

    assert post.called
    assert post.call_args[1]["json"]["query"].split() == query.split()


def test_describe_flow_runs_not_found(monkeypatch, cloud_api):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data=dict(flow_run=[])))
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    runner = CliRunner()
    result = runner.invoke(describe, ["flow-runs", "--name", "flow-run"])
    assert result.exit_code == 0
    assert "flow-run not found" in result.output


def test_describe_flow_runs_populated(monkeypatch, cloud_api):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(
                return_value=dict(data=dict(flow_run=[{"name": "flow-run"}]))
            )
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    runner = CliRunner()
    result = runner.invoke(
        describe, ["flow-runs", "--name", "flow-run", "--flow-name", "flow"]
    )
    assert result.exit_code == 0

    query = """
    query {
        flow_run(where: { _and: { name: { _eq: "flow-run" }, flow: { name: { _eq: "flow" } } } }) {
            name
            flow {
                name
            }
            created
            parameters
            auto_scheduled
            scheduled_start_time
            start_time
            end_time
            serialized_state
        }
    }
    """

    assert post.called
    assert post.call_args[1]["json"]["query"].split() == query.split()


@pytest.mark.parametrize("output", ["json", "yaml"])
def test_describe_flow_runs_output(monkeypatch, output, cloud_api):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(
                return_value=dict(data=dict(flow_run=[{"name": "flow-run"}]))
            )
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    runner = CliRunner()
    result = runner.invoke(
        describe, ["flow-runs", "--name", "flow-run", "--output", output]
    )
    assert result.exit_code == 0

    if output == "json":
        res = json.loads(result.output)
    elif output == "yaml":
        res = yaml.safe_load(result.output)
    assert res == {"name": "flow-run"}
