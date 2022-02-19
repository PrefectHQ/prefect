import pytest

from prefect.blocks.core import (
    BLOCK_REGISTRY,
    Block,
    get_block,
    register_block,
)


@pytest.fixture(autouse=True)
def reset_registered_blockapis(monkeypatch):
    _copy = BLOCK_REGISTRY.copy()
    monkeypatch.setattr("prefect.blocks.core.BLOCK_REGISTRY", _copy)
    yield


async def test_registering_and_getting_blockapis():
    assert get_block("is anyone home") is None

    @register_block("yes i am home")
    class ARealLiveBlock(Block):
        def block_initialization(self):
            pass

    assert get_block("yes i am home") == ARealLiveBlock
