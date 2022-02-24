from uuid import uuid4
import pytest

from prefect.blocks.core import (
    BLOCK_REGISTRY,
    Block,
    create_block_from_api_block,
    get_block_spec,
    register_block,
)


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


class TestAPICompatibility:
    class MyBlock(Block):
        x: str
        y: int = 1

    @register_block(version="2.0")
    class MyRegisteredBlock(Block):
        x: str
        y: int = 1

    @register_block("another-block-spec-name", version="3.0")
    class MyOtherRegisteredBlock(Block):
        x: str
        y: int = 1

    @register_block()
    class MyThirdRegisteredBlock(Block):
        _block_spec_name: str = "my-third-registered-block"
        _block_spec_version: str = "4.0"
        x: str

    def test_registration_fills_private_attributes(self):
        assert self.MyBlock._block_spec_name is None
        assert self.MyBlock._block_spec_version is None
        assert self.MyRegisteredBlock._block_spec_name == "MyRegisteredBlock"
        assert self.MyRegisteredBlock._block_spec_version == "2.0"
        assert self.MyOtherRegisteredBlock._block_spec_name == "another-block-spec-name"
        assert self.MyOtherRegisteredBlock._block_spec_version == "3.0"
        assert (
            self.MyThirdRegisteredBlock._block_spec_name == "my-third-registered-block"
        )
        assert self.MyThirdRegisteredBlock._block_spec_version == "4.0"

    def test_registration_names_and_versions(self):
        assert get_block_spec("MyRegisteredBlock", "2.0") is self.MyRegisteredBlock
        assert (
            get_block_spec("another-block-spec-name", "3.0")
            is self.MyOtherRegisteredBlock
        )
        assert (
            get_block_spec("my-third-registered-block", "4.0")
            is self.MyThirdRegisteredBlock
        )

    def test_create_api_block_spec(self):
        block_spec = self.MyRegisteredBlock.to_api_block_spec()
        assert block_spec.name == "MyRegisteredBlock"
        assert block_spec.version == "2.0"
        assert block_spec.type is None
        assert block_spec.fields == {
            "title": "MyRegisteredBlock",
            "type": "object",
            "properties": {
                "x": {"title": "X", "type": "string"},
                "y": {"title": "Y", "default": 1, "type": "integer"},
            },
            "required": ["x"],
        }

    def test_create_api_block_spec_with_different_registered_name(self):
        block_spec = self.MyOtherRegisteredBlock.to_api_block_spec()
        assert block_spec.name == "another-block-spec-name"
        assert block_spec.version == "3.0"
        assert block_spec.type is None
        assert block_spec.fields == {
            "title": "another-block-spec-name",
            "type": "object",
            "properties": {
                "x": {"title": "X", "type": "string"},
                "y": {"title": "Y", "default": 1, "type": "integer"},
            },
            "required": ["x"],
        }

    def test_create_api_block_with_arguments(self):
        with pytest.raises(ValueError, match="(No name provided)"):
            self.MyRegisteredBlock(x="x").to_api_block()
        with pytest.raises(ValueError, match="(No block spec ID provided)"):
            self.MyRegisteredBlock(x="x").to_api_block(name="block")
        assert self.MyRegisteredBlock(x="x").to_api_block(
            name="block", block_spec_id=uuid4()
        )

    def test_create_block_from_api(self):
        block_spec_id = uuid4()
        api_block = self.MyRegisteredBlock(x="x").to_api_block(
            name="block", block_spec_id=block_spec_id
        )

        block = create_block_from_api_block(api_block)
        assert type(block) == self.MyRegisteredBlock
        assert block.x == "x"
        assert block._block_spec_id == block_spec_id
        assert block._block_id == api_block.id
