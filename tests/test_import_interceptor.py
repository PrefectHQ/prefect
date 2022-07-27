import pytest


def test_prefect_1_import_warning():
    with pytest.raises(ImportError):
        with pytest.warns(UserWarning, match="Attempted import of 'prefect.Client"):
            from prefect import Client  # noqa
