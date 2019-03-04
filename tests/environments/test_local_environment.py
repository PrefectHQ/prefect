import tempfile
from unittest.mock import MagicMock

import pytest
from cryptography.fernet import Fernet, InvalidToken

import prefect
from prefect import Flow, Parameter, Task
from prefect.environments import LocalEnvironment
from prefect.utilities.environments import from_file


def error_flow():
    @prefect.task
    def error_task():
        1 / 0

    with Flow("error flow") as flow:
        error_task()

    return flow


#################################
##### LocalEnvironment Tests
#################################


class TestLocalEnvironment:
    def test_create_local_environment(self):
        env = LocalEnvironment()
        assert env

    def test_local_environment_generates_encryption_key(self):
        env = LocalEnvironment()
        assert env.encryption_key is not None

    def test_local_environment_stores_encryption_key(self):
        key = Fernet.generate_key()
        env = LocalEnvironment(encryption_key=key)
        assert env.encryption_key == key

    def test_local_environment_validates_encryption_key(self):
        with pytest.raises(ValueError) as exc:
            LocalEnvironment(encryption_key="hi")
        assert "Invalid encryption key" in str(exc)

    def test_serialize_flow(self):
        assert isinstance(LocalEnvironment().serialize_flow_to_bytes(Flow()), bytes)

    def test_deserialize_flow(self):
        f = Flow()
        f.add_task(Task())
        f.add_task(Parameter("x"))

        env = LocalEnvironment()
        serialized = env.serialize_flow_to_bytes(f)
        deserialized = env.deserialize_flow_from_bytes(serialized)

        assert isinstance(deserialized, Flow)
        assert len(deserialized.tasks) == 2
        assert {p.name for p in deserialized.parameters()} == {"x"}

    def test_deserialize_flow_fails_if_not_same_environment(self):
        serialized = LocalEnvironment().serialize_flow_to_bytes(Flow())
        with pytest.raises(InvalidToken):
            LocalEnvironment().deserialize_flow_from_bytes(serialized)

    def test_deserialize_flow_succeeds_with_same_key(self):
        key = Fernet.generate_key()
        serialized = LocalEnvironment(encryption_key=key).serialize_flow_to_bytes(
            Flow()
        )
        deserialized = LocalEnvironment(encryption_key=key).deserialize_flow_from_bytes(
            serialized
        )
        assert len(deserialized.tasks) == 0

    def test_build_local_environment(self):
        env = LocalEnvironment()
        new_env = env.build(Flow())
        assert isinstance(new_env, LocalEnvironment)
        assert env.serialized_flow is None
        assert new_env.serialized_flow is not None

    def test_run(self):
        env = LocalEnvironment()
        state = env.build(error_flow()).run()
        assert state.is_failed()

    def test_run_uses_default_flow_runner(self, monkeypatch):
        x = MagicMock()
        monkeypatch.setattr("prefect.engine.flow_runner.FlowRunner", x)

        env = LocalEnvironment()
        built_env = env.build(prefect.Flow())
        with prefect.utilities.configuration.set_temporary_config(
            {"engine.flow_runner.default_class": "prefect.engine.x"}
        ):

            with pytest.warns(UserWarning):
                built_env.run()
        assert x.call_count == 1

    def test_run_without_build(self):
        env = LocalEnvironment()

        with pytest.raises(ValueError) as exc:
            env.run()
        assert "No serialized flow found!" in str(exc)

    def test_to_and_from_file(self):
        env = LocalEnvironment().build(error_flow())
        with tempfile.NamedTemporaryFile() as tmp:
            env.to_file(tmp.name)
            new_env = from_file(tmp.name)

        assert isinstance(new_env, LocalEnvironment)
        assert new_env.encryption_key == env.encryption_key
        assert new_env.serialized_flow == env.serialized_flow

    def test_serialize(self):
        env = LocalEnvironment().build(error_flow())
        s = env.serialize()
        assert isinstance(s, dict)
