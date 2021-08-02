import pytest

from prefect.orion.utilities.database import get_session_factory

import pytest


@pytest.fixture
async def database_session(database_engine):
    OrionSession = get_session_factory(database_engine)
    yield OrionSession()
