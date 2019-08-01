import sys
from unittest.mock import MagicMock

import click
import pytest
import requests
from click.testing import CliRunner

import prefect
from prefect.cli.get import get
from prefect.utilities.configuration import set_temporary_config


def test_get_init():
    runner = CliRunner()
    result = runner.invoke(get)
    assert result.exit_code == 0
    assert (
        "Get commands that refer to querying Prefect Cloud metadata." in result.output
    )


def test_get_help():
    runner = CliRunner()
    result = runner.invoke(get, ["--help"])
    assert result.exit_code == 0
    assert (
        "Get commands that refer to querying Prefect Cloud metadata." in result.output
    )


@pytest.mark.skipif(
    sys.version_info < (3, 6), reason="3.5 does not preserve dictionary order"
)
def test_get_flows(monkeypatch):
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
        result = runner.invoke(get, ["flows"])
        assert result.exit_code == 0
        assert (
            "NAME" in result.output
            and "VERSION" in result.output
            and "PROJECT NAME" in result.output
            and "AGE" in result.output
        )

        query = """
        query {
            flow(where: { _and: { name: { _eq: null }, version: { _eq: null }, project: { name: { _eq: null } } } }, order_by: { name: asc, version: desc }, distinct_on: name, limit: 10) {
                name
                version
                project {
                    name
                }
                created
            }
        }
        """

        assert post.called
        assert post.call_args[1]["json"]["query"].split() == query.split()


@pytest.mark.skipif(
    sys.version_info < (3, 6), reason="3.5 does not preserve dictionary order"
)
def test_get_flows_populated(monkeypatch):
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
            get,
            [
                "flows",
                "--name",
                "name",
                "--version",
                "2",
                "--project",
                "project",
                "--limit",
                "100",
                "--all-versions",
            ],
        )
        assert result.exit_code == 0

        query = """
        query {
            flow(where: { _and: { name: { _eq: "name" }, version: { _eq: 2 }, project: { name: { _eq: "project" } } } }, order_by: { name: asc, version: desc }, distinct_on: null, limit: 100) {
                name
                version
                project {
                    name
                }
                created
            }
        }
        """

        assert post.called
        assert post.call_args[1]["json"]["query"].split() == query.split()


@pytest.mark.skipif(
    sys.version_info < (3, 6), reason="3.5 does not preserve dictionary order"
)
def test_get_projects(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(json=MagicMock(return_value=dict(data=dict(project=[]))))
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(get, ["projects"])
        assert result.exit_code == 0
        assert (
            "NAME" in result.output
            and "FLOW COUNT" in result.output
            and "AGE" in result.output
            and "DESCRIPTION" in result.output
        )

        query = """
        query {
            project(where: { _and: { name: { _eq: null } } }, order_by: { name: asc }) {
                name
                created
                description
                flows_aggregate(distinct_on: name) {
                    aggregate {
                        count
                    }
                }
            }
        }
        """

        assert post.called
        assert post.call_args[1]["json"]["query"].split() == query.split()


@pytest.mark.skipif(
    sys.version_info < (3, 6), reason="3.5 does not preserve dictionary order"
)
def test_get_projects_populated(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(json=MagicMock(return_value=dict(data=dict(project=[]))))
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(get, ["projects", "--name", "name"])
        assert result.exit_code == 0

        query = """
        query {
            project(where: { _and: { name: { _eq: "name" } } }, order_by: { name: asc }) {
                name
                created
                description
                flows_aggregate(distinct_on: name) {
                    aggregate {
                        count
                    }
                }
            }
        }
        """

        assert post.called
        assert post.call_args[1]["json"]["query"].split() == query.split()


@pytest.mark.skipif(
    sys.version_info < (3, 6), reason="3.5 does not preserve dictionary order"
)
def test_get_flow_runs(monkeypatch):
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
        result = runner.invoke(get, ["flow-runs"])
        assert result.exit_code == 0
        assert (
            "NAME" in result.output
            and "FLOW NAME" in result.output
            and "STATE" in result.output
            and "AGE" in result.output
            and "START TIME" in result.output
            and "DURATION" in result.output
        )

        query = """
        query {
            flow_run(where: { flow: { _and: { name: { _eq: null }, project: { name: { _eq: null } } } } }, limit: 10, order_by: { created: desc }) {
                flow {
                    name
                }
                created
                state
                name
                duration
                start_time
            }
        }
        """

        assert post.called
        assert post.call_args[1]["json"]["query"].split() == query.split()


@pytest.mark.skipif(
    sys.version_info < (3, 6), reason="3.5 does not preserve dictionary order"
)
def test_get_flow_runs_populated(monkeypatch):
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
        result = runner.invoke(
            get,
            [
                "flow-runs",
                "--limit",
                "100",
                "--flow",
                "flow",
                "--project",
                "project",
                "--started",
            ],
        )
        assert result.exit_code == 0

        query = """
        query {
            flow_run(where: { _and: { flow: { _and: { name: { _eq: "flow" }, project: { name: { _eq: "project" } } } }, start_time: { _is_null: false } } }, limit: 100, order_by: { start_time: desc }) {
                flow {
                    name
                }
                created
                state
                name
                duration
                start_time
            }
        }
        """

        assert post.called
        assert post.call_args[1]["json"]["query"].split() == query.split()


@pytest.mark.skipif(
    sys.version_info < (3, 6), reason="3.5 does not preserve dictionary order"
)
def test_get_tasks(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(json=MagicMock(return_value=dict(data=dict(task=[]))))
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(get, ["tasks"])
        assert result.exit_code == 0
        assert (
            "NAME" in result.output
            and "FLOW NAME" in result.output
            and "FLOW VERSION" in result.output
            and "AGE" in result.output
            and "MAPPED" in result.output
            and "TYPE" in result.output
        )

        query = """
        query {
            task(where: { _and: { name: { _eq: null }, flow: { name: { _eq: null }, project: { name: { _eq: null } }, version: { _eq: null } } } }, limit: 10, order_by: { created: desc }) {
                name
                created
                flow {
                    name
                    version
                }
                mapped
                type
            }
        }
        """

        assert post.called
        assert post.call_args[1]["json"]["query"].split() == query.split()


@pytest.mark.skipif(
    sys.version_info < (3, 6), reason="3.5 does not preserve dictionary order"
)
def test_get_tasks_populated(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(json=MagicMock(return_value=dict(data=dict(task=[]))))
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(
            get,
            [
                "tasks",
                "--name",
                "task",
                "--flow-name",
                "flow",
                "--flow-version",
                "2",
                "--project",
                "project",
                "--limit",
                "100",
            ],
        )
        assert result.exit_code == 0

        query = """
        query {
            task(where: { _and: { name: { _eq: "task" }, flow: { name: { _eq: "flow" }, project: { name: { _eq: "project" } }, version: { _eq: 2 } } } }, limit: 100, order_by: { created: desc }) {
                name
                created
                flow {
                    name
                    version
                }
                mapped
                type
            }
        }
        """

        assert post.called
        assert post.call_args[1]["json"]["query"].split() == query.split()


@pytest.mark.skipif(
    sys.version_info < (3, 6), reason="3.5 does not preserve dictionary order"
)
def test_get_logs(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(
                return_value=dict(
                    data=dict(
                        flow_run=[
                            dict(
                                logs=[
                                    {
                                        "timestamp": "timestamp",
                                        "level": "level",
                                        "message": "message",
                                    }
                                ]
                            )
                        ]
                    )
                )
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
        result = runner.invoke(get, ["logs", "--name", "flow_run"])
        assert result.exit_code == 0
        assert (
            "TIMESTAMP" in result.output
            and "LEVEL" in result.output
            and "MESSAGE" in result.output
            and "level" in result.output
        )

        query = """
        query {
            flow_run(where: { name: { _eq: "flow_run" } }, order_by: { start_time: desc }) {
                logs(order_by: { timestamp: asc }) {
                    timestamp
                    message
                    level
                }
                start_time
            }
        }
        """

        assert post.called
        assert post.call_args[1]["json"]["query"].split() == query.split()


@pytest.mark.skipif(
    sys.version_info < (3, 6), reason="3.5 does not preserve dictionary order"
)
def test_get_logs_info(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(
                return_value=dict(data=dict(flow_run=[dict(logs=[{"info": "OUTPUT"}])]))
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
        result = runner.invoke(get, ["logs", "--name", "flow_run", "--info"])
        assert result.exit_code == 0
        assert "OUTPUT" in result.output

        query = """
        query {
            flow_run(where: { name: { _eq: "flow_run" } }, order_by: { start_time: desc }) {
                logs(order_by: { timestamp: asc }) {
                    timestamp
                    info
                }
                start_time
            }
        }
        """

        assert post.called
        assert post.call_args[1]["json"]["query"].split() == query.split()


def test_get_logs_fails(monkeypatch):
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
        result = runner.invoke(get, ["logs", "--name", "flow_run"])
        assert result.exit_code == 0
        assert "flow_run not found" in result.output
