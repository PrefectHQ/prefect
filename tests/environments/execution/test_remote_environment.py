import tempfile
from os import path
from unittest.mock import MagicMock

import cloudpickle
import pytest

import prefect
from prefect.environments import RemoteEnvironment
from prefect.environments.storage import Docker


def test_create_remote_environment():
    environment = RemoteEnvironment()
    assert environment
    assert environment.executor == prefect.config.engine.executor.default_class
    assert environment.executor_kwargs == {}
    assert environment.labels == set()
    assert environment.on_start is None
    assert environment.on_exit is None
    assert environment.logger.name == "prefect.RemoteEnvironment"


def test_create_remote_environment_populated():
    def f():
        pass

    environment = RemoteEnvironment(
        executor="prefect.engine.executors.DaskExecutor",
        executor_kwargs={"address": "test"},
        labels=["foo", "bar", "good"],
        on_start=f,
        on_exit=f,
    )
    assert environment
    assert environment.executor == "prefect.engine.executors.DaskExecutor"
    assert environment.executor_kwargs == {"address": "test"}
    assert environment.labels == set(["foo", "bar", "good"])
    assert environment.on_start is f
    assert environment.on_exit is f


def test_remote_environment_dependencies():
    environment = RemoteEnvironment()
    assert environment.dependencies == []


def test_environment_execute():
    with tempfile.TemporaryDirectory() as directory:

        @prefect.task
        def add_to_dict():
            with open(path.join(directory, "output"), "w") as tmp:
                tmp.write("success")

        with open(path.join(directory, "flow_env.prefect"), "w+") as env:
            flow = prefect.Flow("test", tasks=[add_to_dict])
            flow_path = path.join(directory, "flow_env.prefect")
            with open(flow_path, "wb") as f:
                cloudpickle.dump(flow, f)

        environment = RemoteEnvironment()
        storage = Docker(registry_url="test")

        environment.execute(storage, flow_path)

        with open(path.join(directory, "output"), "r") as file:
            assert file.read() == "success"


def test_environment_execute_calls_callbacks():
    start_func = MagicMock()
    exit_func = MagicMock()

    with tempfile.TemporaryDirectory() as directory:

        @prefect.task
        def add_to_dict():
            with open(path.join(directory, "output"), "w") as tmp:
                tmp.write("success")

        with open(path.join(directory, "flow_env.prefect"), "w+") as env:
            flow = prefect.Flow("test", tasks=[add_to_dict])
            flow_path = path.join(directory, "flow_env.prefect")
            with open(flow_path, "wb") as f:
                cloudpickle.dump(flow, f)

        environment = RemoteEnvironment(on_start=start_func, on_exit=exit_func)
        storage = Docker(registry_url="test")

        environment.execute(storage, flow_path)

        with open(path.join(directory, "output"), "r") as file:
            assert file.read() == "success"

        assert start_func.called
        assert exit_func.called
