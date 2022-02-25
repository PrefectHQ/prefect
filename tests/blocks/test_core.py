import pytest

from prefect.blocks.core import BLOCK_REGISTRY, Block, get_block_spec, register_block


@pytest.fixture(autouse=True)
def reset_registered_blocks(monkeypatch):
    _copy = BLOCK_REGISTRY.copy()
    monkeypatch.setattr("prefect.blocks.core.BLOCK_REGISTRY", _copy)
    yield


async def test_registering_and_getting_blocks():
    with pytest.raises(ValueError, match="(No block spec exists)"):
        get_block_spec("is anyone home", "1.0")

    @register_block("yes i am home", version="1.0")
    class ARealLiveBlock(Block):
        def block_initialization(self):
            pass

    assert get_block_spec("yes i am home", "1.0") == ARealLiveBlock

    with pytest.raises(ValueError, match="(No block spec exists)"):
        get_block_spec("is anyone home", "2.0")
