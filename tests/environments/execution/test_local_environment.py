from unittest.mock import MagicMock

import pytest

import prefect
from prefect.environments.execution import LocalEnvironment
from prefect.environments.storage import Docker, Local


class DummyStorage(Local):
    def add_flow(self, flow):
        self.flows[flow.name] = flow
        return flow.name

    def get_flow(self, location):
        return self.flows[location]


def test_create_environment():
    environment = LocalEnvironment()
    assert environment
    assert environment.labels == set()
    assert environment.on_start is None
    assert environment.on_exit is None
    assert environment.logger.name == "prefect.LocalEnvironment"


def test_create_environment_populated():
    def f():
        pass

    environment = LocalEnvironment(labels=["test"], on_start=f, on_exit=f)
    assert environment
    assert environment.labels == set(["test"])
    assert environment.on_start is f
    assert environment.on_exit is f
    assert environment.logger.name == "prefect.LocalEnvironment"


def test_environment_dependencies():
    environment = LocalEnvironment()
    assert environment.dependencies == []


def test_setup_environment_passes():
    environment = LocalEnvironment()
    environment.setup(storage=Docker())
    assert environment


def test_serialize_environment():
    environment = LocalEnvironment()
    env = environment.serialize()
    assert env["type"] == "LocalEnvironment"


def test_environment_execute():
    global_dict = {}

    @prefect.task
    def add_to_dict():
        global_dict["run"] = True

    environment = LocalEnvironment()
    storage = DummyStorage()
    flow = prefect.Flow("test", tasks=[add_to_dict])
    flow_loc = storage.add_flow(flow)

    environment.execute(storage, flow_loc)
    assert global_dict.get("run") is True


def test_environment_execute_with_env_runner():
    class TestStorage(DummyStorage):
        def get_flow(self, *args, **kwargs):
            raise NotImplementedError()

        def get_env_runner(self, flow_loc):
            runner = super().get_flow(flow_loc)
            return lambda env: runner.run()

    global_dict = {}

    @prefect.task
    def add_to_dict():
        global_dict["run"] = True

    environment = LocalEnvironment()
    storage = TestStorage()
    flow = prefect.Flow("test", tasks=[add_to_dict])
    flow_loc = storage.add_flow(flow)

    environment.execute(storage, flow_loc)
    assert global_dict.get("run") is True


def test_environment_execute_with_kwargs():
    global_dict = {}

    @prefect.task
    def add_to_dict(x):
        global_dict["result"] = x

    environment = LocalEnvironment()
    storage = DummyStorage()
    with prefect.Flow("test") as flow:
        x = prefect.Parameter("x")
        add_to_dict(x)

    flow_loc = storage.add_flow(flow)

    environment.execute(storage, flow_loc, x=42)
    assert global_dict.get("result") == 42


def test_environment_execute_with_env_runner_with_kwargs():
    class TestStorage(DummyStorage):
        def get_flow(self, *args, **kwargs):
            raise NotImplementedError()

        def get_env_runner(self, flow_loc):
            runner = super().get_flow(flow_loc)

            def runner_func(env):
                runner.run(x=env.get("x"))

            return runner_func

    global_dict = {}

    @prefect.task
    def add_to_dict(x):
        global_dict["result"] = x

    environment = LocalEnvironment()
    storage = TestStorage()
    with prefect.Flow("test") as flow:
        x = prefect.Parameter("x")
        add_to_dict(x)

    flow_loc = storage.add_flow(flow)
    environment.execute(storage, flow_loc, env=dict(x=42))
    assert global_dict.get("result") == 42


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
    flow_loc = storage.add_flow(flow)

    environment.execute(storage, flow_loc)
    assert global_dict.get("run") is True

    assert start_func.called
    assert exit_func.called
