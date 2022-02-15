import pytest

from prefect.blocks.core import (
    BLOCK_API_REGISTRY,
    get_blockapi,
    register_blockapi,
    BlockAPI,
)


@pytest.fixture(autouse=True)
def reset_registered_blockapis(monkeypatch):
    _copy = BLOCK_API_REGISTRY.copy()
    monkeypatch.setattr("prefect.blocks.core.BLOCK_API_REGISTRY", _copy)
    yield


async def test_registering_and_getting_blockapis():
    assert get_blockapi("is anyone home") is None

    @register_blockapi("yes i am home")
    class ARealLiveBlockAPI(BlockAPI):
        def block_initialization(self):
            pass

    assert get_blockapi("yes i am home") == ARealLiveBlockAPI
