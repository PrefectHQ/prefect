from typing import Optional

import pytest

from prefect.testing.utilities import prefect_test_harness


@pytest.fixture(scope="session")
def test_database_connection_url() -> Optional[str]:
    """
    Provide a test database connection URL fixture.

    This fixture is required by hosted_api_server from prefect.testing.fixtures.
    For the prefect-ray integration tests, we don't need a real database URL
    since tests use an in-process server via prefect_test_harness.
    """
    return None


@pytest.fixture(scope="session", autouse=True)
def prefect_db():
    with prefect_test_harness():
        yield
