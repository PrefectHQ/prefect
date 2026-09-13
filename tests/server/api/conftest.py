from collections.abc import Iterator
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI

from prefect.server.logs.storage import LogStorage, get_log_storage


@pytest.fixture
def log_storage(app: FastAPI) -> Iterator[AsyncMock]:
    storage = AsyncMock(spec=LogStorage)
    app.api_app.dependency_overrides[get_log_storage] = lambda: storage
    yield storage
    app.api_app.dependency_overrides.pop(get_log_storage, None)
