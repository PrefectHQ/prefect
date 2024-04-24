import pytest

from prefect.settings import PREFECT_ASYNC_FETCH_STATE_RESULT, temporary_settings


@pytest.fixture(autouse=True)
def fetch_state_result():
    with temporary_settings(updates={PREFECT_ASYNC_FETCH_STATE_RESULT: True}):
        yield
