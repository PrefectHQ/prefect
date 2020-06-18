# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import asyncio
import inspect

import pytest

import prefect
import prefect_server
from prefect.engine.state import Running, Submitted, Success
from prefect_server import api, cli, config
from prefect_server.database import hasura, models
import sqlalchemy as sa

from .fixtures.database_fixtures import *


def pytest_collection_modifyitems(session, config, items):
    """
    Modify tests prior to execution
    """
    for item in items:
        # automatically add @pytest.mark.asyncio to async tests
        if isinstance(item, pytest.Function) and inspect.iscoroutinefunction(
            item.function
        ):
            item.add_marker(pytest.mark.asyncio)


# redefine the event loop to support module-scoped fixtures
# https://github.com/pytest-dev/pytest-asyncio/issues/68
@pytest.yield_fixture(scope="session")
def event_loop(request):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
