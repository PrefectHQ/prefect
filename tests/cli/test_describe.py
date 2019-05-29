import re
from unittest.mock import MagicMock

import click
from click.testing import CliRunner
import requests

import prefect
from prefect.cli.describe import describe
from prefect.utilities.configuration import set_temporary_config


def test_describe_init():
    runner = CliRunner()
    result = runner.invoke(describe)
    assert result.exit_code == 0
    assert (
        "Describe commands that render JSON output of Prefect object metadata."
        in result.output
    )


def test_describe_help():
    runner = CliRunner()
    result = runner.invoke(describe, ["--help"])
    assert result.exit_code == 0
    assert (
        "Describe commands that render JSON output of Prefect object metadata."
        in result.output
    )


def test_describe_flows(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data=dict(flow=[{"name": "flow"}])))
        )
    )
    monkeypatch.setattr("requests.post", post)

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(describe, ["flows", "--name", "flow"])
        assert result.exit_code == 0
        assert "name" in result.output

        query = """
        query {
            flow(where: { _and: { name: { _eq: "flow" }, version: { _eq: null }, project: { name: { _eq: null } } } }, order_by: { name: asc, version: desc }, distinct_on: name) {
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
        assert re.sub(r"[\n\t\s]*", "", post.call_args[1]["json"]["query"]) == re.sub(
            r"[\n\t\s]*", "", query
        )


def test_describe_flows_not_found(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(json=MagicMock(return_value=dict(data=dict(flow=[]))))
    )
    monkeypatch.setattr("requests.post", post)

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(describe, ["flows", "--name", "flow"])
        assert result.exit_code == 0
        assert "flow not found" in result.output


def test_describe_flows_populated(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data=dict(flow=[{"name": "flow"}])))
        )
    )
    monkeypatch.setattr("requests.post", post)

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
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
        assert re.sub(r"[\n\t\s]*", "", post.call_args[1]["json"]["query"]) == re.sub(
            r"[\n\t\s]*", "", query
        )


def test_describe_tasks(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(
                return_value=dict(data=dict(flow=[{"tasks": [{"name": "task"}]}]))
            )
        )
    )
    monkeypatch.setattr("requests.post", post)

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(describe, ["tasks", "--name", "flow"])
        assert result.exit_code == 0
        assert "name" in result.output

        query = """
        query {
            flow(where: { _and: { name: { _eq: "flow" }, version: { _eq: null }, project: { name: { _eq: null } } } }, order_by: { name: asc, version: desc }, distinct_on: name) {
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
        assert re.sub(r"[\n\t\s]*", "", post.call_args[1]["json"]["query"]) == re.sub(
            r"[\n\t\s]*", "", query
        )


def test_describe_tasks_flow_not_found(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(json=MagicMock(return_value=dict(data=dict(flow=[]))))
    )
    monkeypatch.setattr("requests.post", post)

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(describe, ["tasks", "--name", "flow"])
        assert result.exit_code == 0
        assert "flow not found" in result.output


def test_describe_tasks_not_found(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data=dict(flow=[{"tasks": []}])))
        )
    )
    monkeypatch.setattr("requests.post", post)

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(describe, ["tasks", "--name", "flow"])
        assert result.exit_code == 0
        assert "No tasks found for flow flow" in result.output


def test_describe_flow_runs(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(
                return_value=dict(data=dict(flow_run=[{"name": "flow-run"}]))
            )
        )
    )
    monkeypatch.setattr("requests.post", post)

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
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
                duration
                heartbeat
                serialized_state
            }
        }
        """

        assert post.called
        assert re.sub(r"[\n\t\s]*", "", post.call_args[1]["json"]["query"]) == re.sub(
            r"[\n\t\s]*", "", query
        )


def test_describe_flow_runs_not_found(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data=dict(flow_run=[])))
        )
    )
    monkeypatch.setattr("requests.post", post)

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(describe, ["flow-runs", "--name", "flow-run"])
        assert result.exit_code == 0
        assert "flow-run not found" in result.output


def test_describe_flow_runs_populated(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(
                return_value=dict(data=dict(flow_run=[{"name": "flow-run"}]))
            )
        )
    )
    monkeypatch.setattr("requests.post", post)

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
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
                duration
                heartbeat
                serialized_state
            }
        }
        """

        assert post.called
        assert re.sub(r"[\n\t\s]*", "", post.call_args[1]["json"]["query"]) == re.sub(
            r"[\n\t\s]*", "", query
        )
