import pytest

from prefect import utilities
from prefect.environments import storage


def test_default_storage():
    assert storage.get_default_storage_class() is storage.Local


def test_default_storage_responds_to_config():
    with utilities.configuration.set_temporary_config(
        {"flows.defaults.storage.default_class": "prefect.environments.storage.Docker"}
    ):
        assert storage.get_default_storage_class() is storage.Docker


def test_default_storage_ignores_bad_config():
    with utilities.configuration.set_temporary_config(
        {"flows.defaults.storage.default_class": "FOOBAR"}
    ):

        with pytest.warns(UserWarning):
            assert storage.get_default_storage_class() is storage.Local
