import pytest

from prefect.environments import storage
from prefect import utilities


def test_default_storage():
    assert storage.get_default_storage_class() is storage.Docker


def test_default_storage_responds_to_config():
    with utilities.configuration.set_temporary_config(
        {"flows.defaults.storage.default_class": "prefect.environments.storage.Memory"}
    ):
        assert storage.get_default_storage_class() is storage.Memory


def test_default_storage_ignores_bad_config():
    with utilities.configuration.set_temporary_config(
        {"flows.defaults.storage.default_class": "FOOBAR"}
    ):

        with pytest.warns(UserWarning):
            assert storage.get_default_storage_class() is storage.Docker
