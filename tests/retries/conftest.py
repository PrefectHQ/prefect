from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_sleep(monkeypatch: pytest.MonkeyPatch):
    """
    Mocks the `time.sleep` function.
    """
    mock_sleep = MagicMock()
    monkeypatch.setattr("time.sleep", mock_sleep)
    return mock_sleep


@pytest.fixture
def mock_async_sleep(monkeypatch: pytest.MonkeyPatch):
    """
    Mocks the `asyncio.sleep` function.
    """
    mock_sleep = AsyncMock()
    monkeypatch.setattr("asyncio.sleep", mock_sleep)
    return mock_sleep
