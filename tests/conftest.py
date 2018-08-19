import pytest
from cryptography.fernet import Fernet

import prefect
from prefect.utilities import tests


@pytest.fixture(autouse=True, scope="session")
def set_config():
    """
    Creates a registry encryption key for testing
    """
    with tests.set_temporary_config("registry.encryption_key", Fernet.generate_key()):
        yield


@pytest.fixture(autouse=True)
def clear_registry():
    """
    Clear the flow registry after every test
    """
    yield
    prefect.core.registry.REGISTRY.clear()
