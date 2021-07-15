import pytest
import inspect

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

        # if the item is in a deprecated subdirectory, mark it as deprecated
        if "deprecated/" in str(item.fspath):
            item.add_marker(pytest.mark.deprecated)
