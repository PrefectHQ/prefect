import pytest

import prefect
from prefect.environments.execution import LocalEnvironment
from prefect.environments.storage import Docker, Memory


def test_create_environment():
    environment = LocalEnvironment()
    assert environment


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
    storage = Memory()
    flow = prefect.Flow("test", tasks=[add_to_dict])
    flow_loc = storage.add_flow(flow)

    environment.execute(storage, flow_loc)
    assert global_dict.get("run") is True


def test_environment_execute_with_env_runner():
    class TestStorage(Memory):
        def get_runner(self, *args, **kwargs):
            raise NotImplementedError()

        def get_env_runner(self, flow_loc):
            runner = super().get_runner(flow_loc)
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
