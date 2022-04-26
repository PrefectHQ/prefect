from uuid import uuid4

import pytest

from prefect.blocks.core import (
    BLOCK_REGISTRY,
    Block,
    create_block_from_block_document,
    get_block_class,
    register_block,
)


@pytest.fixture(autouse=True)
def reset_registered_blocks(monkeypatch):
    _copy = BLOCK_REGISTRY.copy()
    monkeypatch.setattr("prefect.blocks.core.BLOCK_REGISTRY", _copy)
    yield


async def test_registering_and_getting_blocks():
    with pytest.raises(ValueError, match="(No block schema exists)"):
        get_block_class("is anyone home", "1.0")

    @register_block("yes i am home", version="1.0")
    class ARealLiveBlock(Block):
        def block_initialization(self):
            pass

    assert get_block_class("yes i am home", "1.0") == ARealLiveBlock

    with pytest.raises(ValueError, match="(No block schema exists)"):
        get_block_class("is anyone home", "2.0")


class TestInvalidRegistration:
    async def test_everything_missing(self):
        class MyBlock(Block):
            pass

        with pytest.raises(
            ValueError, match="(No _block_schema_name set and no name provided)"
        ):
            register_block()(MyBlock)

    async def test_missing_name(self):
        class MyBlock(Block):
            pass

        with pytest.raises(
            ValueError, match="(No _block_schema_name set and no name provided)"
        ):
            register_block(version="1.0")(MyBlock)

    async def test_missing_version_pass_name(self):
        class MyBlock(Block):
            pass

        with pytest.raises(
            ValueError, match="(No _block_schema_version set and no version provided)"
        ):
            register_block(name="my-block")(MyBlock)

    async def test_missing_version_default_name(self):
        class MyBlock(Block):
            _block_schema_name = "my-block"
            pass

        with pytest.raises(
            ValueError, match="(No _block_schema_version set and no version provided)"
        ):
            register_block()(MyBlock)


class TestAPICompatibility:
    class MyBlock(Block):
        x: str
        y: int = 1

    @register_block("My Registered Block", version="2.0")
    class MyRegisteredBlock(Block):
        x: str
        y: int = 1

    @register_block()
    class MyOtherRegisteredBlock(Block):
        _block_schema_name: str = "my-other-registered-block"
        _block_schema_version: str = "3.0"
        x: str
        y: int = 1

    def test_registration_fills_private_attributes(self):
        assert self.MyBlock._block_schema_name is None
        assert self.MyBlock._block_schema_version is None
        assert self.MyRegisteredBlock._block_schema_name == "My Registered Block"
        assert self.MyRegisteredBlock._block_schema_version == "2.0"
        assert (
            self.MyOtherRegisteredBlock._block_schema_name
            == "my-other-registered-block"
        )
        assert self.MyOtherRegisteredBlock._block_schema_version == "3.0"

    def test_registration_names_and_versions(self):
        assert get_block_class("My Registered Block", "2.0") is self.MyRegisteredBlock

        assert (
            get_block_class("my-other-registered-block", "3.0")
            is self.MyOtherRegisteredBlock
        )

    def test_create_api_block_schema(self):
        block_schema = self.MyRegisteredBlock.to_block_schema()
        assert block_schema.name == "My Registered Block"
        assert block_schema.version == "2.0"
        assert block_schema.type is None
        assert block_schema.fields == {
            "title": "My Registered Block",
            "type": "object",
            "properties": {
                "x": {"title": "X", "type": "string"},
                "y": {"title": "Y", "default": 1, "type": "integer"},
            },
            "required": ["x"],
        }

    def test_create_api_block_schema_only_includes_pydantic_fields(self):
        @register_block("just a name", version="1000000.0")
        class MakesALottaAttributes(Block):
            real_field: str
            authentic_field: str

            def block_initialization(self):
                self.evil_fake_field = "evil fake data"

        my_block = MakesALottaAttributes(real_field="hello", authentic_field="marvin")
        block_schema = my_block.to_block_schema()
        assert "real_field" in block_schema.fields["properties"].keys()
        assert "authentic_field" in block_schema.fields["properties"].keys()
        assert "evil_fake_field" not in block_schema.fields["properties"].keys()

    def test_create_api_block_schema_with_different_registered_name(self):
        block_schema = self.MyOtherRegisteredBlock.to_block_schema()
        assert block_schema.name == "my-other-registered-block"
        assert block_schema.version == "3.0"
        assert block_schema.type is None
        assert block_schema.fields == {
            "title": "my-other-registered-block",
            "type": "object",
            "properties": {
                "x": {"title": "X", "type": "string"},
                "y": {"title": "Y", "default": 1, "type": "integer"},
            },
            "required": ["x"],
        }

    def test_create_api_block_with_arguments(self):
        with pytest.raises(ValueError, match="(No name provided)"):
            self.MyRegisteredBlock(x="x").to_block_document()
        with pytest.raises(ValueError, match="(No block schema ID provided)"):
            self.MyRegisteredBlock(x="x").to_block_document(name="block")
        assert self.MyRegisteredBlock(x="x").to_block_document(
            name="block", block_schema_id=uuid4()
        )

    def test_create_block_from_block_document(self):
        block_schema_id = uuid4()
        api_block = self.MyRegisteredBlock(x="x").to_block_document(
            name="block", block_schema_id=block_schema_id
        )

        block = create_block_from_block_document(api_block)
        assert type(block) == self.MyRegisteredBlock
        assert block.x == "x"
        assert block._block_schema_id == block_schema_id
        assert block._block_document_id == api_block.id

    def test_create_block_document_from_block(self):
        @register_block("just a name", version="1000000.0")
        class MakesALottaAttributes(Block):
            real_field: str
            authentic_field: str

            def block_initialization(self):
                self.evil_fake_field = "evil fake data"

        my_block = MakesALottaAttributes(real_field="hello", authentic_field="marvin")
        api_block = my_block.to_block_document(
            name="a corrupted api block", block_schema_id=uuid4()
        )
        assert "real_field" in api_block.data
        assert "authentic_field" in api_block.data
        assert "evil_fake_field" not in api_block.data
