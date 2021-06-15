from unittest.mock import MagicMock

import prefect
from prefect import Flow
from prefect.executors import LocalDaskExecutor
from prefect.environments.execution import LocalEnvironment
from prefect.storage import Docker, Local
from prefect.utilities.configuration import set_temporary_config


class DummyStorage(Local):
    def add_flow(self, flow):
        self.flows[flow.name] = flow
        return flow.name

    def get_flow(self, flow_name):
        return self.flows[flow_name]


def test_create_environment():
    with set_temporary_config(
        {"engine.executor.default_class": "prefect.executors.LocalDaskExecutor"}
    ):
        environment = LocalEnvironment()

    assert isinstance(environment.executor, LocalDaskExecutor)
    assert environment.labels == set()
    assert environment.on_start is None
    assert environment.on_exit is None
    assert environment.metadata == {}
    assert environment.logger.name == "prefect.LocalEnvironment"


def test_create_environment_populated():
    def f():
        pass

    executor = LocalDaskExecutor()
    environment = LocalEnvironment(
        executor=executor,
        labels=["test"],
        on_start=f,
        on_exit=f,
        metadata={"test": "here"},
    )
    assert environment.executor is executor
    assert environment.labels == set(["test"])
    assert environment.on_start is f
    assert environment.on_exit is f
    assert environment.metadata == {"test": "here"}
    assert environment.logger.name == "prefect.LocalEnvironment"


def test_environment_dependencies():
    environment = LocalEnvironment()
    assert environment.dependencies == []


def test_setup_environment_passes():
    environment = LocalEnvironment()
    environment.setup(flow=Flow("test", storage=Docker()))


def test_serialize_environment():
    environment = LocalEnvironment()
    env = environment.serialize()
    assert env["type"] == "LocalEnvironment"


def test_environment_execute():
    class MyExecutor(LocalDaskExecutor):
        submit_called = False

        def submit(self, *args, **kwargs):
            self.submit_called = True
            return super().submit(*args, **kwargs)

    global_dict = {}

    @prefect.task
    def add_to_dict():
        global_dict["run"] = True

    executor = MyExecutor()
    environment = LocalEnvironment(executor=executor)
    storage = DummyStorage()
    flow = prefect.Flow(
        "test", tasks=[add_to_dict], environment=environment, storage=storage
    )

    storage.add_flow(flow)
    environment.execute(flow=flow)

    assert global_dict.get("run") is True
    assert executor.submit_called


def test_environment_execute_calls_callbacks():
    start_func = MagicMock()
    exit_func = MagicMock()

    global_dict = {}

    @prefect.task
    def add_to_dict():
        global_dict["run"] = True

    environment = LocalEnvironment(on_start=start_func, on_exit=exit_func)
    storage = DummyStorage()
    flow = prefect.Flow("test", tasks=[add_to_dict])
    storage.add_flow(flow)
    flow.storage = storage

    environment.execute(flow)
    assert global_dict.get("run") is True

    assert start_func.called
    assert exit_func.called
