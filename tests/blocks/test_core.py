from uuid import uuid4

import pytest

from prefect.blocks.core import BLOCK_REGISTRY, Block, get_block_class, register_block


@pytest.fixture(autouse=True)
def reset_registered_blocks(monkeypatch):
    _copy = BLOCK_REGISTRY.copy()
    monkeypatch.setattr("prefect.blocks.core.BLOCK_REGISTRY", _copy)
    yield


class TestAPICompatibility:
    class MyBlock(Block):
        x: str
        y: int = 1

    @register_block
    class MyRegisteredBlock(Block):
        x: str
        y: int = 1

    @register_block
    class MyOtherRegisteredBlock(Block):
        x: str
        y: int = 1
        z: int = 2

    def test_registration_checksums(self):
        assert (
            get_block_class(
                "sha256:b45dd7c45c4935967b3685e6b0d87a27baeb26b1b7aa69c85886724ddd8c246f"
            )
            is self.MyRegisteredBlock
        )

        assert (
            get_block_class(
                "sha256:719dd945f13a4aea50709ce65f93eee6f6511c5f560e89cdd0193ae1993536a8"
            )
            is self.MyOtherRegisteredBlock
        )

        with pytest.raises(ValueError, match="(No block schema exists)"):
            get_block_class(self.MyBlock.calculate_schema_checksum())

    def test_create_api_block_schema(self, block_type_x):
        block_schema = self.MyRegisteredBlock.to_block_schema(
            block_type_id=block_type_x.id
        )
        assert block_schema.type is None
        assert (
            block_schema.checksum
            == "sha256:b45dd7c45c4935967b3685e6b0d87a27baeb26b1b7aa69c85886724ddd8c246f"
        )
        assert block_schema.fields == {
            "title": "MyRegisteredBlock",
            "type": "object",
            "properties": {
                "x": {"title": "X", "type": "string"},
                "y": {"title": "Y", "default": 1, "type": "integer"},
            },
            "required": ["x"],
        }

    def test_create_api_block_schema_only_includes_pydantic_fields(self, block_type_x):
        @register_block
        class MakesALottaAttributes(Block):
            real_field: str
            authentic_field: str

            def block_initialization(self):
                self.evil_fake_field = "evil fake data"

        my_block = MakesALottaAttributes(real_field="hello", authentic_field="marvin")
        block_schema = my_block.to_block_schema(block_type_id=block_type_x.id)
        assert "real_field" in block_schema.fields["properties"].keys()
        assert "authentic_field" in block_schema.fields["properties"].keys()
        assert "evil_fake_field" not in block_schema.fields["properties"].keys()

    def test_create_api_block_schema_with_different_registered_name(self, block_type_x):
        block_schema = self.MyOtherRegisteredBlock.to_block_schema(
            block_type_id=block_type_x.id
        )
        assert (
            block_schema.checksum
            == "sha256:719dd945f13a4aea50709ce65f93eee6f6511c5f560e89cdd0193ae1993536a8"
        )
        assert block_schema.type is None
        assert block_schema.fields == {
            "title": "MyOtherRegisteredBlock",
            "type": "object",
            "properties": {
                "x": {"title": "X", "type": "string"},
                "y": {"title": "Y", "default": 1, "type": "integer"},
                "z": {"default": 2, "title": "Z", "type": "integer"},
            },
            "required": ["x"],
        }

    def test_create_api_block_with_arguments(self, block_type_x):
        with pytest.raises(ValueError, match="(No name provided)"):
            self.MyRegisteredBlock(x="x").to_block_document()
        with pytest.raises(ValueError, match="(No block schema ID provided)"):
            self.MyRegisteredBlock(x="x").to_block_document(name="block")
        assert self.MyRegisteredBlock(x="x").to_block_document(
            name="block", block_schema_id=uuid4(), block_type_id=block_type_x.id
        )

    def test_from_block_document(self, block_type_x):
        block_schema_id = uuid4()
        api_block = self.MyRegisteredBlock(x="x").to_block_document(
            name="block", block_schema_id=block_schema_id, block_type_id=block_type_x.id
        )

        block = Block.from_block_document(api_block)
        assert type(block) == self.MyRegisteredBlock
        assert block.x == "x"
        assert block._block_schema_id == block_schema_id
        assert block._block_document_id == api_block.id
        assert block._block_type_id == block_type_x.id

    def test_create_block_document_from_block(self, block_type_x):
        @register_block
        class MakesALottaAttributes(Block):
            real_field: str
            authentic_field: str

            def block_initialization(self):
                self.evil_fake_field = "evil fake data"

        my_block = MakesALottaAttributes(real_field="hello", authentic_field="marvin")
        api_block = my_block.to_block_document(
            name="a corrupted api block",
            block_schema_id=uuid4(),
            block_type_id=block_type_x.id,
        )
        assert "real_field" in api_block.data
        assert "authentic_field" in api_block.data
        assert "evil_fake_field" not in api_block.data
