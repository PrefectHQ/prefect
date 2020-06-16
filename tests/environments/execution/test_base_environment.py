import tempfile
from unittest.mock import MagicMock

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


def test_run_flow(monkeypatch):
    environment = Environment()

    flow_runner = MagicMock()
    monkeypatch.setattr(
        "prefect.engine.get_default_flow_runner_class",
        MagicMock(return_value=flow_runner),
    )

    executor = MagicMock()
    monkeypatch.setattr(
        "prefect.engine.get_default_executor_class", MagicMock(return_value=executor),
    )

    with tempfile.TemporaryDirectory() as directory:
        d = Local(directory)
        d.add_flow(Flow("name"))

        gql_return = MagicMock(
            return_value=MagicMock(
                data=MagicMock(
                    flow_run=[
                        GraphQLResult(
                            {
                                "flow": GraphQLResult(
                                    {"name": "name", "storage": d.serialize(),}
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

        with set_temporary_config({"cloud.auth_token": "test"}):
            environment.run_flow()

        assert flow_runner.call_args[1]["flow"].name == "name"
        assert executor.call_args == None
