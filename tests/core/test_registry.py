import subprocess
import tempfile

import pytest
from cryptography.fernet import Fernet

import prefect
from prefect import Flow
from prefect.core import registry
from prefect.utilities.tests import set_temporary_config


@pytest.fixture()
def flow():
    return Flow(name="name", project="project", version="version")


@pytest.fixture(autouse=True)
def clear_data():
    registry.REGISTRY.clear()


@pytest.fixture(autouse=True, scope="module")
def set_encryption_key():
    with set_temporary_config(
        "registry.encryption_key", Fernet.generate_key().decode()
    ):
        yield


class TestRegistry:
    def test_register_flow(self, flow):
        assert flow.id not in registry.REGISTRY
        registry.register_flow(flow)
        assert registry.REGISTRY[flow.id] is flow

    def test_register_flow_warning_on_duplicate(self, flow):
        assert prefect.config.registry.warn_on_duplicate_registration
        registry.register_flow(flow)
        with pytest.warns(UserWarning):
            registry.register_flow(flow)

    def load_flow(self, flow):
        with pytest.raises(ValueError):
            registry.load_flow(None)
        registry.register_flow(flow)
        assert registry.load_flow(flow.id) is flow

    def test_serialize_registry(self, flow):
        registry.register_flow(flow)
        serialized = registry.serialize_registry()
        assert len(serialized) > 100

    def test_load_serialized_registry(self, flow):
        registry.register_flow(flow)
        serialized = registry.serialize_registry()
        registry.REGISTRY.clear()

        registry.load_serialized_registry(serialized)
        assert registry.REGISTRY
        new_flow = registry.load_flow(flow.id)

        # not working because reference tasks don't match
        assert new_flow == flow

    def test_serialize_and_load_serialized_registry_warns_about_encryption(self, flow):
        key = prefect.config.registry.encryption_key
        prefect.config.registry.encryption_key = ""
        try:
            assert not prefect.config.registry.encryption_key
            registry.register_flow(flow)

            with pytest.warns(UserWarning):
                serialized = registry.serialize_registry()
            with pytest.warns(UserWarning):
                registry.load_serialized_registry(serialized)
        finally:
            prefect.config.registry.encryption_key = key

    def test_automatic_registration(self):
        flow = Flow(name="hello", register=True)
        assert (flow.id) in registry.REGISTRY

    def test_load_registry_on_startup(self):
        """
        Registers two flows and writes the registry to a file; tests that Prefect
        automatically deserializes that registry if the appropriate config is set via env var.
        """

        cmd = 'python -c "import prefect; print(len(prefect.core.registry.REGISTRY))"'
        assert subprocess.check_output(cmd, shell=True).strip() == b"0"

        with tempfile.NamedTemporaryFile() as tmp:
            registry.register_flow(Flow("flow1"))
            registry.register_flow(Flow("flow2"))

            with open(tmp.name, "wb") as f:
                serialized = registry.serialize_registry()
                f.write(serialized)

            env = [
                "PREFECT__REGISTRY__LOAD_ON_STARTUP={}".format(tmp.name),
                "PREFECT__REGISTRY__ENCRYPTION_KEY={}".format(
                    prefect.config.registry.encryption_key
                ),
            ]
            result = subprocess.check_output(" ".join(env + [cmd]), shell=True)
            assert result.strip() == b"2"
