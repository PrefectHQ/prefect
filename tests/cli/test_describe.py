import json
from unittest.mock import MagicMock

from click.testing import CliRunner

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
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(
            describe, ["flows", "--name", "flow", "--project", "proj"]
        )
        assert result.exit_code == 0
        assert "name" in result.output

        query = """
        query {
            flow(where: { _and: { name: { _eq: "flow" }, version: { _eq: null }, project: { name: { _eq: "proj" } } } }, order_by: { name: asc, version: desc }, distinct_on: name) {
                name
                version
                created
                description
                parameters
                archived
                storage
                environment
                project {
                    name
                }
            }
        }
        """

        assert post.called
        assert post.call_args[1]["json"]["query"].split() == query.split()


def test_describe_flows_not_found(monkeypatch):
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
        result = runner.invoke(describe, ["flows", "--name", "flow"])
        assert result.exit_code == 0
        assert "flow not found" in result.output


def test_describe_flows_populated(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data=dict(flow=[{"name": "flow"}])))
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

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
                created
                description
                parameters
                archived
                storage
                environment
                project {
                    name
                }
            }
        }
        """

        assert post.called
        assert post.call_args[1]["json"]["query"].split() == query.split()


def test_describe_flows_json_output(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data=dict(flow=[{"name": "flow"}])))
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(
            describe,
            ["flows", "--name", "flow", "--project", "proj", "--output", "json"],
        )
        assert result.exit_code == 0

        assert json.loads(result.output) == {"name": "flow"}


def test_describe_tasks(monkeypatch):
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

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(
            describe, ["tasks", "--name", "flow", "--project", "proj"]
        )
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


def test_describe_tasks_flow_not_found(monkeypatch):
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
        result = runner.invoke(describe, ["tasks", "--name", "flow"])
        assert result.exit_code == 0
        assert "flow not found" in result.output


def test_describe_tasks_not_found(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data=dict(flow=[{"tasks": []}])))
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(describe, ["tasks", "--name", "flow"])
        assert result.exit_code == 0
        assert "No tasks found for flow flow" in result.output


def test_describe_tasks_json_output(monkeypatch):
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

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(
            describe,
            ["tasks", "--name", "flow", "--project", "proj", "--output", "json"],
        )
        assert result.exit_code == 0

        assert json.loads(result.output) == {"name": "task"}


def test_describe_flow_runs(monkeypatch):
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
        assert post.call_args[1]["json"]["query"].split() == query.split()


def test_describe_flow_runs_not_found(monkeypatch):
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
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

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
        assert post.call_args[1]["json"]["query"].split() == query.split()


def test_describe_flow_runs_json_output(monkeypatch):
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

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(
            describe, ["flow-runs", "--name", "flow-run", "--output", "json"]
        )
        assert result.exit_code == 0

        assert json.loads(result.output) == {"name": "flow-run"}
