import pytest

pytest.importorskip("boto3")

from prefect.utilities.aws import _CACHE


@pytest.fixture(autouse=True)
def clear_client_cache():
    _CACHE.clear()
