import pytest

from prefect.settings import PREFECT_ASYNC_FETCH_STATE_RESULT, temporary_settings
from prefect.testing.utilities import prefect_test_harness


@pytest.fixture(scope="session", autouse=True)
def prefect_db():
    """
    Sets up test harness for temporary DB during test runs.
    """
    with prefect_test_harness():
        yield


@pytest.fixture(autouse=True)
def fetch_state_result():
    with temporary_settings(updates={PREFECT_ASYNC_FETCH_STATE_RESULT: True}):
        yield
