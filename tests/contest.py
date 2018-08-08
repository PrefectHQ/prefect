import pytest
from cryptography.fernet import Fernet

from prefect.utilities import tests


@pytest.fixture(autouse=True, scope=session)
def set_config():
    with tests.set_temporary_config("registry.encryption_key", Fernet.generate_key()):
        yield
