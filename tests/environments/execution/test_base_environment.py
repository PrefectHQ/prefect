from unittest.mock import MagicMock

import pytest

import prefect
from prefect import Flow
from prefect.environments import Environment
from prefect.environments.storage import Docker, Local
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.graphql import GraphQLResult


def test_create_environment():
    environment = Environment()
    assert environment
    assert environment.labels == set()
    assert environment.on_start is None
    assert environment.on_exit is None
    assert environment.metadata == {}
    assert environment.logger.name == "prefect.Environment"


def test_create_environment_converts_labels_to_set():
    environment = Environment(labels=["a", "b", "a"])
    assert environment
    assert environment.labels == set(["a", "b"])
    assert environment.logger.name == "prefect.Environment"


def test_create_environment_metadata():
    environment = Environment(metadata={"test": "here"})
    assert environment
    assert environment.metadata == {"test": "here"}


def test_create_environment_callbacks():
    def f():
        pass

    environment = Environment(on_start=f, on_exit=f)
    assert environment.on_start is f
    assert environment.on_exit is f


def test_environment_dependencies():
    environment = Environment()
    assert environment.dependencies == []


def test_setup_environment_passes():
    environment = Environment()
    environment.setup(flow=Flow("test", storage=Docker()))
    assert environment


def test_execute_environment_passes():
    environment = Environment()
    environment.execute(flow=Flow("test", storage=Docker()))
    assert environment


def test_serialize_environment():
    environment = Environment()
    env = environment.serialize()
    assert env["type"] == "Environment"


def test_run_flow(monkeypatch, tmpdir):
    environment = Environment()

    flow_runner = MagicMock()
    flow_runner_class = MagicMock(return_value=flow_runner)

    monkeypatch.setattr(
        "prefect.engine.get_default_flow_runner_class",
        MagicMock(return_value=flow_runner_class),
    )

    d = Local(str(tmpdir))
    d.add_flow(Flow("name"))

    gql_return = MagicMock(
        return_value=MagicMock(
            data=MagicMock(
                flow_run=[
                    GraphQLResult(
                        {
                            "flow": GraphQLResult(
                                {"name": "name", "storage": d.serialize()}
                            )
                        }
                    )
                ],
            )
        )
    )
    client = MagicMock()
    client.return_value.graphql = gql_return
    monkeypatch.setattr("prefect.environments.execution.base.Client", client)

    with set_temporary_config({"cloud.auth_token": "test"}), prefect.context(
        {"flow_run_id": "id"}
    ):
        environment.run_flow()

    assert flow_runner_class.call_args[1]["flow"].name == "name"
    assert flow_runner.run.call_args[1]["executor"] is not None


def test_run_flow_no_flow_run_id_in_context(monkeypatch, tmpdir):
    environment = Environment()

    d = Local(str(tmpdir))
    d.add_flow(Flow("name"))

    with set_temporary_config({"cloud.auth_token": "test"}):
        with pytest.raises(ValueError):
            environment.run_flow()
