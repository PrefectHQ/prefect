import abc
import json
import warnings
from textwrap import dedent
from typing import Any, Dict, List, Tuple, Type, Union
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from packaging.version import Version
from pydantic import BaseModel, Field, SecretBytes, SecretStr, ValidationError
from pydantic import Secret as PydanticSecret
from pydantic_core import to_json

import prefect
from prefect.blocks.core import Block, InvalidBlockRegistration
from prefect.blocks.system import Secret
from prefect.client.orchestration import PrefectClient
from prefect.exceptions import PrefectHTTPStatusError
from prefect.server import models
from prefect.server.schemas.actions import BlockDocumentCreate
from prefect.server.schemas.core import DEFAULT_BLOCK_SCHEMA_VERSION, BlockDocument
from prefect.testing.utilities import AsyncMock, assert_blocks_equal
from prefect.types import SecretDict
from prefect.utilities.dispatch import lookup_type, register_type


class CoolBlock(Block):
    cool_factor: int


class TestAPICompatibility:
    class MyBlock(Block):
        x: str
        y: int = 1

    @register_type
    class MyRegisteredBlock(Block):
        x: str
        y: int = 1

    @register_type
    class MyOtherRegisteredBlock(Block):
        x: str
        y: int = 1
        z: int = 2

    def test_registration(self):
        assert (
            lookup_type(Block, self.MyRegisteredBlock.__dispatch_key__())
            is self.MyRegisteredBlock
        )

        assert (
            lookup_type(Block, self.MyOtherRegisteredBlock.__dispatch_key__())
            is self.MyOtherRegisteredBlock
        )

        assert lookup_type(Block, self.MyBlock.__dispatch_key__()) is self.MyBlock

    def test_create_api_block_schema(self, block_type_x):
        block_schema = self.MyRegisteredBlock._to_block_schema(
            block_type_id=block_type_x.id
        )
        assert (
            block_schema.checksum
            == "sha256:876ee010b459f79fe6a31f00442a2ba47ee36202968830efda4378544051da64"
        )
        assert block_schema.fields == {
            "title": "MyRegisteredBlock",
            "type": "object",
            "properties": {
                "x": {"title": "X", "type": "string"},
                "y": {"title": "Y", "default": 1, "type": "integer"},
            },
            "block_schema_references": {},
            "block_type_slug": "myregisteredblock",
            "required": ["x"],
            "secret_fields": [],
        }

    def test_create_api_block_with_secret_fields_reflected_in_schema(self):
        class SecretBlockE(Block):
            w: SecretDict
            x: SecretStr
            y: SecretBytes
            z: str

        assert SecretBlockE.model_json_schema()["secret_fields"] == ["w.*", "x", "y"]

        schema = SecretBlockE._to_block_schema(block_type_id=uuid4())
        assert schema.fields["secret_fields"] == ["w.*", "x", "y"]
        assert schema.fields == {
            "block_schema_references": {},
            "block_type_slug": "secretblocke",
            "properties": {
                "w": {"title": "W", "type": "object"},
                "x": {
                    "format": "password",
                    "title": "X",
                    "type": "string",
                    "writeOnly": True,
                },
                "y": {
                    "format": "password",
                    "title": "Y",
                    "type": "string",
                    "writeOnly": True,
                },
                "z": {"title": "Z", "type": "string"},
            },
            "required": ["w", "x", "y", "z"],
            "secret_fields": ["w.*", "x", "y"],
            "title": "SecretBlockE",
            "type": "object",
        }

    def test_create_api_block_with_nested_secret_fields_reflected_in_schema(self):
        class Child(Block):
            a: SecretStr
            b: str
            c: SecretDict

        class Parent(Block):
            a: SecretStr
            b: str
            child: Child

        assert Child.model_json_schema()["secret_fields"] == ["a", "c.*"]
        assert Parent.model_json_schema()["secret_fields"] == [
            "a",
            "child.a",
            "child.c.*",
        ]
        schema = Parent._to_block_schema(block_type_id=uuid4())
        assert schema.fields["secret_fields"] == ["a", "child.a", "child.c.*"]
        assert schema.fields == {
            "block_schema_references": {
                "child": {
                    "block_schema_checksum": "sha256:3e50c75591f4071c7df082d8a7969c57ae97f6a62c2345017e6b64bc13c39cd0",
                    "block_type_slug": "child",
                }
            },
            "block_type_slug": "parent",
            "definitions": {
                "Child": {
                    "block_schema_references": {},
                    "block_type_slug": "child",
                    "properties": {
                        "a": {
                            "format": "password",
                            "title": "A",
                            "type": "string",
                            "writeOnly": True,
                        },
                        "b": {"title": "B", "type": "string"},
                        "c": {"title": "C", "type": "object"},
                    },
                    "required": ["a", "b", "c"],
                    "secret_fields": ["a", "c.*"],
                    "title": "Child",
                    "type": "object",
                }
            },
            "properties": {
                "a": {
                    "format": "password",
                    "title": "A",
                    "type": "string",
                    "writeOnly": True,
                },
                "b": {"title": "B", "type": "string"},
                "child": {"$ref": "#/definitions/Child"},
            },
            "required": ["a", "b", "child"],
            "secret_fields": ["a", "child.a", "child.c.*"],
            "title": "Parent",
            "type": "object",
        }

    def test_create_api_block_with_nested_secret_fields_in_base_model_reflected_in_schema(
        self,
    ):
        class Child(BaseModel):
            a: SecretStr
            b: str
            c: SecretDict

        class Parent(Block):
            a: SecretStr
            b: str
            child: Child

        assert Parent.model_json_schema()["secret_fields"] == [
            "a",
            "child.a",
            "child.c.*",
        ]
        schema = Parent._to_block_schema(block_type_id=uuid4())
        assert schema.fields["secret_fields"] == ["a", "child.a", "child.c.*"]
        assert schema.fields == {
            "title": "Parent",
            "type": "object",
            "properties": {
                "a": {
                    "title": "A",
                    "type": "string",
                    "writeOnly": True,
                    "format": "password",
                },
                "b": {"title": "B", "type": "string"},
                "child": {"$ref": "#/definitions/Child"},
            },
            "required": ["a", "b", "child"],
            "block_type_slug": "parent",
            "secret_fields": ["a", "child.a", "child.c.*"],
            "block_schema_references": {},
            "definitions": {
                "Child": {
                    "title": "Child",
                    "type": "object",
                    "properties": {
                        "a": {
                            "title": "A",
                            "type": "string",
                            "writeOnly": True,
                            "format": "password",
                        },
                        "b": {"title": "B", "type": "string"},
                        "c": {"title": "C", "type": "object"},
                    },
                    "required": ["a", "b", "c"],
                }
            },
        }

    def test_create_api_block_with_nested_union_secret_fields_in_base_model_reflected_in_schema(
        self,
    ):
        class Child(BaseModel):
            a: SecretStr
            b: str
            c: SecretDict

        class Parent(Block):
            a: SecretStr
            b: str
            child: Union[Child, str]

        assert Parent.model_json_schema()["secret_fields"] == [
            "a",
            "child.a",
            "child.c.*",
        ]
        schema = Parent._to_block_schema(block_type_id=uuid4())
        assert schema.fields["secret_fields"] == ["a", "child.a", "child.c.*"]
        assert schema.fields == {
            "title": "Parent",
            "type": "object",
            "properties": {
                "a": {
                    "title": "A",
                    "type": "string",
                    "writeOnly": True,
                    "format": "password",
                },
                "b": {"title": "B", "type": "string"},
                "child": {
                    "title": "Child",
                    "anyOf": [{"$ref": "#/definitions/Child"}, {"type": "string"}],
                },
            },
            "required": ["a", "b", "child"],
            "block_type_slug": "parent",
            "secret_fields": ["a", "child.a", "child.c.*"],
            "block_schema_references": {},
            "definitions": {
                "Child": {
                    "title": "Child",
                    "type": "object",
                    "properties": {
                        "a": {
                            "title": "A",
                            "type": "string",
                            "writeOnly": True,
                            "format": "password",
                        },
                        "b": {"title": "B", "type": "string"},
                        "c": {"title": "C", "type": "object"},
                    },
                    "required": ["a", "b", "c"],
                }
            },
        }

    def test_create_api_block_with_deeply_nested_secret_fields_in_base_model_reflected_in_schema(
        self,
    ):
        class SubChild(BaseModel):
            a: str
            b: SecretDict
            c: SecretBytes

        class Child(BaseModel):
            a: SecretStr
            b: str
            sub_child: SubChild

        class Parent(Block):
            a: SecretStr
            b: str
            child: Child

        assert Parent.model_json_schema()["secret_fields"] == [
            "a",
            "child.a",
            "child.sub_child.b.*",
            "child.sub_child.c",
        ]
        schema = Parent._to_block_schema(block_type_id=uuid4())
        assert schema.fields["secret_fields"] == [
            "a",
            "child.a",
            "child.sub_child.b.*",
            "child.sub_child.c",
        ]
        assert schema.fields == {
            "title": "Parent",
            "type": "object",
            "properties": {
                "a": {
                    "title": "A",
                    "type": "string",
                    "writeOnly": True,
                    "format": "password",
                },
                "b": {"title": "B", "type": "string"},
                "child": {"$ref": "#/definitions/Child"},
            },
            "required": ["a", "b", "child"],
            "block_type_slug": "parent",
            "secret_fields": [
                "a",
                "child.a",
                "child.sub_child.b.*",
                "child.sub_child.c",
            ],
            "block_schema_references": {},
            "definitions": {
                "SubChild": {
                    "title": "SubChild",
                    "type": "object",
                    "properties": {
                        "a": {"title": "A", "type": "string"},
                        "b": {"title": "B", "type": "object"},
                        "c": {
                            "title": "C",
                            "type": "string",
                            "writeOnly": True,
                            "format": "password",
                        },
                    },
                    "required": ["a", "b", "c"],
                },
                "Child": {
                    "title": "Child",
                    "type": "object",
                    "properties": {
                        "a": {
                            "title": "A",
                            "type": "string",
                            "writeOnly": True,
                            "format": "password",
                        },
                        "b": {"title": "B", "type": "string"},
                        "sub_child": {"$ref": "#/definitions/SubChild"},
                    },
                    "required": ["a", "b", "sub_child"],
                },
            },
        }

    def test_create_api_block_with_secret_values_are_obfuscated_by_default(self):
        class SecretBlockA(Block):
            w: SecretDict
            x: SecretStr
            y: SecretBytes
            z: str

        block = SecretBlockA(
            w={
                "Here's my shallow secret": "I don't like olives",
                "deeper secrets": {"Here's my deeper secret": "I've never seen Lost"},
            },
            x="x",
            y=b"y",
            z="z",
        )

        block_type_id = uuid4()
        block_schema_id = uuid4()
        blockdoc = block._to_block_document(
            name="name", block_type_id=block_type_id, block_schema_id=block_schema_id
        )
        assert isinstance(blockdoc.data["w"], SecretDict)
        assert isinstance(blockdoc.data["x"], SecretStr)
        assert isinstance(blockdoc.data["y"], SecretBytes)

        json_blockdoc = blockdoc.model_dump(mode="json")
        assert json_blockdoc["data"] == {
            "w": "********",
            "x": "********",
            "y": "********",
            "z": "z",
        }

        blockdoc_with_secrets = block._to_block_document(
            name="name",
            block_type_id=block_type_id,
            block_schema_id=block_schema_id,
            include_secrets=True,
        )

        json_blockdoc_with_secrets = blockdoc_with_secrets.model_dump(
            context={"include_secrets": True}, mode="json"
        )

        assert json_blockdoc_with_secrets["data"] == {
            "w": {
                "Here's my shallow secret": "I don't like olives",
                "deeper secrets": {"Here's my deeper secret": "I've never seen Lost"},
            },
            "x": "x",
            "y": "y",
            "z": "z",
        }

    def test_create_nested_api_block_with_secret_values_are_obfuscated_by_default(self):
        class Child(Block):
            a: SecretStr
            b: str
            c: SecretDict

        class Parent(Block):
            a: SecretStr
            b: str
            child: Child

        block = Parent(a="a", b="b", child=dict(a="a", b="b", c=dict(secret="value")))
        block_type_id = uuid4()
        block_schema_id = uuid4()
        blockdoc = block._to_block_document(
            name="name", block_type_id=block_type_id, block_schema_id=block_schema_id
        )
        assert isinstance(blockdoc.data["a"], SecretStr)
        assert isinstance(blockdoc.data["child"]["a"], SecretStr)

        json_blockdoc = json.loads(blockdoc.model_dump_json())
        assert json_blockdoc["data"] == {
            "a": "********",
            "b": "b",
            # The child includes the type slug because it is not a block document
            "child": {
                "a": "********",
                "b": "b",
                "c": "********",
                "block_type_slug": "child",
            },
        }

        blockdoc_with_secrets = block._to_block_document(
            name="name",
            block_type_id=block_type_id,
            block_schema_id=block_schema_id,
            include_secrets=True,
        )

        json_blockdoc_with_secrets = blockdoc_with_secrets.model_dump(
            mode="json", context={"include_secrets": True}
        )
        assert json_blockdoc_with_secrets["data"] == {
            "a": "a",
            "b": "b",
            # The child includes the type slug because it is not a block document
            "child": {
                "a": "a",
                "b": "b",
                "c": {"secret": "value"},
                "block_type_slug": "child",
            },
        }

    def test_registering_blocks_with_capabilities(self):
        @register_type
        class IncapableBlock(Block):
            # could use a little confidence
            _block_type_id = uuid4()

        class CanBluff(Block):
            _block_schema_capabilities = ["bluffing"]

            def bluff(self):
                pass

        @register_type
        class CapableBlock(CanBluff, Block):
            # kind of rude to the other Blocks
            _block_type_id = uuid4()
            all_the_answers: str = "42 or something"

        capable_schema = CapableBlock._to_block_schema()
        assert capable_schema.capabilities == ["bluffing"]

        incapable_schema = IncapableBlock._to_block_schema()
        assert incapable_schema.capabilities == []

    def test_create_api_block_schema_only_includes_pydantic_fields(self, block_type_x):
        @register_type
        class MakesALottaAttributes(Block):
            real_field: str
            authentic_field: str

            def block_initialization(self):
                self.evil_fake_field = "evil fake data"

        my_block = MakesALottaAttributes(real_field="hello", authentic_field="marvin")
        block_schema = my_block._to_block_schema(block_type_id=block_type_x.id)
        assert "real_field" in block_schema.fields["properties"].keys()
        assert "authentic_field" in block_schema.fields["properties"].keys()
        assert "evil_fake_field" not in block_schema.fields["properties"].keys()

    def test_create_api_block_schema_with_different_registered_slug(self, block_type_x):
        block_schema = self.MyOtherRegisteredBlock._to_block_schema(
            block_type_id=block_type_x.id
        )
        assert (
            block_schema.checksum
            == "sha256:5f8577df3c90cfe24ebcb553323d54736cd90b9a155f8e724653fe39de9ada6a"
        )
        assert block_schema.fields == {
            "title": "MyOtherRegisteredBlock",
            "type": "object",
            "properties": {
                "x": {"title": "X", "type": "string"},
                "y": {"title": "Y", "default": 1, "type": "integer"},
                "z": {"default": 2, "title": "Z", "type": "integer"},
            },
            "block_type_slug": "myotherregisteredblock",
            "block_schema_references": {},
            "required": ["x"],
            "secret_fields": [],
        }

    def test_create_api_block_with_arguments(self, block_type_x):
        with pytest.raises(ValueError, match="(No name provided)"):
            self.MyRegisteredBlock(x="x")._to_block_document()
        with pytest.raises(ValueError, match="(No block schema ID provided)"):
            self.MyRegisteredBlock(x="x")._to_block_document(name="block")
        assert self.MyRegisteredBlock(x="x")._to_block_document(
            name="block", block_schema_id=uuid4(), block_type_id=block_type_x.id
        )

    def test_to_block_document_anonymous_no_name(self, block_type_x):
        anon_block = self.MyRegisteredBlock(x="x")._to_block_document(
            block_schema_id=uuid4(),
            block_type_id=block_type_x.id,
            is_anonymous=True,
        )
        assert anon_block.is_anonymous is True
        assert anon_block.name is None

    def test_to_block_document_anonymous(self, block_type_x):
        """Test passing different values to the `is_anonymous` argument, in
        combination with different values of the _is_anonymous class fallback"""

        # explicit true
        anon_block = self.MyRegisteredBlock(x="x")._to_block_document(
            block_schema_id=uuid4(),
            block_type_id=block_type_x.id,
            is_anonymous=True,
        )
        assert anon_block.is_anonymous is True

        # explicit false
        anon_block_2 = self.MyRegisteredBlock(x="x")._to_block_document(
            name="block",
            block_schema_id=uuid4(),
            block_type_id=block_type_x.id,
            is_anonymous=False,
        )
        assert anon_block_2.is_anonymous is False

        # none with no fallback
        anon_block_3 = self.MyRegisteredBlock(x="x")._to_block_document(
            name="block",
            block_schema_id=uuid4(),
            block_type_id=block_type_x.id,
            is_anonymous=None,
        )
        assert anon_block_3.is_anonymous is False

        # none with True fallback
        anon_block_4 = self.MyRegisteredBlock(x="x")
        anon_block_4._is_anonymous = True
        doc_4 = anon_block_4._to_block_document(
            block_schema_id=uuid4(),
            block_type_id=block_type_x.id,
            is_anonymous=None,
        )
        assert doc_4.is_anonymous is True

        # False with True fallback
        anon_block_5 = self.MyRegisteredBlock(x="x")
        anon_block_5._is_anonymous = True
        doc_5 = anon_block_5._to_block_document(
            name="block",
            block_schema_id=uuid4(),
            block_type_id=block_type_x.id,
            is_anonymous=False,
        )
        assert doc_5.is_anonymous is False

    def test_to_block_document_anonymous_errors(self, block_type_x):
        """Test passing different values to the `is_anonymous` argument, in
        combination with different values of the _is_anonymous class fallback"""

        # explicit false
        with pytest.raises(
            ValueError,
            match="(No name provided, either as an argument or on the block)",
        ):
            self.MyRegisteredBlock(x="x")._to_block_document(
                block_schema_id=uuid4(),
                block_type_id=block_type_x.id,
                is_anonymous=False,
            )

        # none with no fallback
        with pytest.raises(
            ValueError,
            match="(No name provided, either as an argument or on the block)",
        ):
            self.MyRegisteredBlock(x="x")._to_block_document(
                block_schema_id=uuid4(),
                block_type_id=block_type_x.id,
                is_anonymous=None,
            )

        # none with False fallback
        anon_block_4 = self.MyRegisteredBlock(x="x")
        anon_block_4._is_anonymous = False
        with pytest.raises(
            ValueError,
            match="(No name provided, either as an argument or on the block)",
        ):
            anon_block_4._to_block_document(
                block_schema_id=uuid4(),
                block_type_id=block_type_x.id,
                is_anonymous=None,
            )

    def test_from_block_document(self, block_type_x):
        block_schema_id = uuid4()
        api_block = self.MyRegisteredBlock(x="x")._to_block_document(
            name="block", block_schema_id=block_schema_id, block_type_id=block_type_x.id
        )

        block = Block._from_block_document(api_block)
        assert type(block) == self.MyRegisteredBlock
        assert block.x == "x"
        assert block._block_schema_id == block_schema_id
        assert block._block_document_id == api_block.id
        assert block._block_type_id == block_type_x.id
        assert block._is_anonymous is False
        assert block._block_document_name == "block"

    def test_from_block_document_anonymous(self, block_type_x):
        block_schema_id = uuid4()
        api_block = self.MyRegisteredBlock(x="x")._to_block_document(
            block_schema_id=block_schema_id,
            block_type_id=block_type_x.id,
            is_anonymous=True,
        )

        block = Block._from_block_document(api_block)
        assert type(block) == self.MyRegisteredBlock
        assert block.x == "x"
        assert block._block_schema_id == block_schema_id
        assert block._block_document_id == api_block.id
        assert block._block_type_id == block_type_x.id
        assert block._is_anonymous is True
        assert block._block_document_name is None

    def test_from_block_document_with_unregistered_block(self):
        class BlockyMcBlock(Block):
            fizz: str

        block_schema_id = uuid4()
        block_type_id = uuid4()
        api_block = BlockyMcBlock(fizz="buzz")._to_block_document(
            name="super-important-config",
            block_schema_id=block_schema_id,
            block_type_id=block_type_id,
        )

        block = BlockyMcBlock._from_block_document(api_block)
        assert type(block) == BlockyMcBlock
        assert block.fizz == "buzz"
        assert block._block_schema_id == block_schema_id
        assert block._block_document_id == api_block.id
        assert block._block_type_id == block_type_id

    def test_create_block_document_from_block(self, block_type_x):
        @register_type
        class MakesALottaAttributes(Block):
            real_field: str
            authentic_field: str

            def block_initialization(self):
                self.evil_fake_field = "evil fake data"

        my_block = MakesALottaAttributes(real_field="hello", authentic_field="marvin")
        api_block = my_block._to_block_document(
            name="a-corrupted-api-block",
            block_schema_id=uuid4(),
            block_type_id=block_type_x.id,
        )
        assert "real_field" in api_block.data
        assert "authentic_field" in api_block.data
        assert "evil_fake_field" not in api_block.data

    @pytest.mark.parametrize("block_name", ["a_block", "a.block"])
    async def test_create_block_document_create_invalid_characters(self, block_name):
        """This gets raised on instantiation of BlockDocumentCreate"""

        @register_type
        class ABlock(Block):
            a_field: str

        a_block = ABlock(a_field="my_field")
        with pytest.raises(ValidationError, match="name must only contain"):
            await a_block.save(block_name)

    @pytest.mark.parametrize("block_name", ["a/block", "a\\block"])
    async def test_create_block_document_invalid_characters(self, block_name):
        """
        This gets raised on instantiation of BlockDocument which shares
        INVALID_CHARACTERS with Flow, Deployment, etc.
        """

        @register_type
        class ABlock(Block):
            a_field: str

        a_block = ABlock(a_field="my_field")
        with pytest.raises(ValidationError, match="name"):
            await a_block.save(block_name)

    def test_create_block_schema_from_block_without_capabilities(
        self, test_block: Type[Block], block_type_x
    ):
        block_schema = test_block._to_block_schema(block_type_id=block_type_x.id)

        assert block_schema.checksum == test_block._calculate_schema_checksum()
        assert block_schema.fields == test_block.model_json_schema()
        assert (
            block_schema.capabilities == []
        ), "No capabilities should be defined for this Block and defaults to []"
        assert block_schema.version == DEFAULT_BLOCK_SCHEMA_VERSION

    def test_create_block_schema_from_block_with_capabilities(
        self, test_block: Type[Block], block_type_x
    ):
        block_schema = test_block._to_block_schema(block_type_id=block_type_x.id)

        assert block_schema.checksum == test_block._calculate_schema_checksum()
        assert block_schema.fields == test_block.model_json_schema()
        assert (
            block_schema.capabilities == []
        ), "No capabilities should be defined for this Block and defaults to []"
        assert block_schema.version == DEFAULT_BLOCK_SCHEMA_VERSION

    def test_create_block_schema_with_no_version_specified(
        self, test_block: Type[Block], block_type_x
    ):
        block_schema = test_block._to_block_schema(block_type_id=block_type_x.id)

        assert block_schema.version == DEFAULT_BLOCK_SCHEMA_VERSION

    def test_create_block_schema_with_version_specified(
        self, test_block: Type[Block], block_type_x
    ):
        test_block._block_schema_version = "1.0.0"
        block_schema = test_block._to_block_schema(block_type_id=block_type_x.id)

        assert block_schema.version == "1.0.0"

    async def test_create_block_schema_uses_prefect_version_for_built_in_blocks(self):
        try:
            await Secret.register_type_and_schema()
        except PrefectHTTPStatusError as exc:
            if exc.response.status_code == 403:
                pass
            else:
                raise exc

        block_schema = Secret._to_block_schema()
        assert block_schema.version == Version(prefect.__version__).base_version

    def test_collecting_capabilities(self):
        class CanRun(Block):
            _block_schema_capabilities = ["run"]

        class CanFly(Block):
            _block_schema_capabilities = ["fly"]

        class CanSwim(Block):
            _block_schema_capabilities = ["swim"]

        class Duck(CanSwim, CanFly):
            pass

        class Bird(CanFly):
            pass

        class Crow(Bird, CanRun):
            pass

        class Cat(CanRun):
            pass

        class FlyingCat(Cat, Bird):
            pass

        assert Duck.get_block_capabilities() == {"swim", "fly"}
        assert Bird.get_block_capabilities() == {"fly"}
        assert Cat.get_block_capabilities() == {"run"}
        assert Crow.get_block_capabilities() == {"fly", "run"}
        assert FlyingCat.get_block_capabilities() == {"fly", "run"}

    def test_create_block_schema_from_nested_blocks(self):
        block_schema_id = uuid4()
        block_type_id = uuid4()

        class NestedBlock(Block):
            _block_type_name = "Nested Block"

            _block_schema_id = block_schema_id
            _block_type_id = block_type_id
            x: str

        class ParentBlock(Block):
            y: str
            z: NestedBlock

        block_schema = ParentBlock._to_block_schema(block_type_id=block_type_id)

        assert block_schema.fields == {
            "title": "ParentBlock",
            "type": "object",
            "properties": {
                "y": {"title": "Y", "type": "string"},
                "z": {"$ref": "#/definitions/NestedBlock"},
            },
            "required": ["y", "z"],
            "block_type_slug": "parentblock",
            "block_schema_references": {
                "z": {
                    "block_schema_checksum": "sha256:85dbfce0d5cfb3b77266422b96c5560f4b9de4ad2ecd74946512e954fb54d650",
                    "block_type_slug": "nested-block",
                }
            },
            "secret_fields": [],
            "definitions": {
                "NestedBlock": {
                    "block_schema_references": {},
                    "block_type_slug": "nested-block",
                    "properties": {"x": {"title": "X", "type": "string"}},
                    "required": ["x"],
                    "secret_fields": [],
                    "title": "NestedBlock",
                    "type": "object",
                },
            },
        }

    async def test_block_load(
        self, test_block, block_document, in_memory_prefect_client
    ):
        my_block = await test_block.load(
            block_document.name, client=in_memory_prefect_client
        )

        assert my_block._block_document_name == block_document.name
        assert my_block._block_document_id == block_document.id
        assert my_block._block_type_id == block_document.block_type_id
        assert my_block._block_schema_id == block_document.block_schema_id
        assert my_block.foo == "bar"

    @patch("prefect.blocks.core.load_prefect_collections")
    async def test_block_load_loads_collections(
        self,
        mock_load_prefect_collections,
        test_block,
        block_document: BlockDocument,
        in_memory_prefect_client,
    ):
        await Block.load(
            block_document.block_type.slug + "/" + block_document.name,
            client=in_memory_prefect_client,
        )
        mock_load_prefect_collections.assert_called_once()

    async def test_load_from_block_base_class(self):
        class Custom(Block):
            message: str

        my_custom_block = Custom(message="hello")
        await my_custom_block.save("my-custom-block")

        loaded_block = await Block.load("custom/my-custom-block")
        assert loaded_block.message == "hello"

    async def test_load_nested_block(self, session, in_memory_prefect_client):
        class B(Block):
            _block_schema_type = "abc"

            x: int

        block_type_b = await models.block_types.create_block_type(
            session=session, block_type=B._to_block_type()
        )
        block_schema_b = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=B._to_block_schema(block_type_id=block_type_b.id),
        )

        class C(Block):
            y: int

        block_type_c = await models.block_types.create_block_type(
            session=session, block_type=C._to_block_type()
        )
        block_schema_c = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=C._to_block_schema(block_type_id=block_type_c.id),
        )

        class D(Block):
            b: B
            z: str

        block_type_d = await models.block_types.create_block_type(
            session=session, block_type=D._to_block_type()
        )
        block_schema_d = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=D._to_block_schema(block_type_id=block_type_d.id),
        )

        class E(Block):
            c: C
            d: D

        block_type_e = await models.block_types.create_block_type(
            session=session, block_type=E._to_block_type()
        )
        block_schema_e = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=E._to_block_schema(block_type_id=block_type_e.id),
        )

        await session.commit()

        inner_block_document = await models.block_documents.create_block_document(
            session=session,
            block_document=BlockDocumentCreate(
                name="inner-block-document",
                data=dict(x=1),
                block_schema_id=block_schema_b.id,
                block_type_id=block_schema_b.block_type_id,
            ),
        )

        middle_block_document_1 = await models.block_documents.create_block_document(
            session=session,
            block_document=BlockDocumentCreate(
                name="middle-block-document-1",
                data=dict(y=2),
                block_schema_id=block_schema_c.id,
                block_type_id=block_schema_c.block_type_id,
            ),
        )
        middle_block_document_2 = await models.block_documents.create_block_document(
            session=session,
            block_document=BlockDocumentCreate(
                name="middle-block-document-2",
                data={
                    "b": {"$ref": {"block_document_id": inner_block_document.id}},
                    "z": "ztop",
                },
                block_schema_id=block_schema_d.id,
                block_type_id=block_schema_d.block_type_id,
            ),
        )
        outer_block_document = await models.block_documents.create_block_document(
            session=session,
            block_document=BlockDocumentCreate(
                name="outer-block-document",
                data={
                    "c": {"$ref": {"block_document_id": middle_block_document_1.id}},
                    "d": {"$ref": {"block_document_id": middle_block_document_2.id}},
                },
                block_schema_id=block_schema_e.id,
                block_type_id=block_schema_e.block_type_id,
            ),
        )

        await session.commit()

        block_instance = await E.load(
            "outer-block-document", client=in_memory_prefect_client
        )
        assert isinstance(block_instance, E)
        assert isinstance(block_instance.c, C)
        assert isinstance(block_instance.d, D)

        assert block_instance._block_document_name == outer_block_document.name
        assert block_instance._block_document_id == outer_block_document.id
        assert block_instance._block_type_id == outer_block_document.block_type_id
        assert block_instance._block_schema_id == outer_block_document.block_schema_id
        assert block_instance.c.model_dump() == {
            "y": 2,
            "_block_document_id": middle_block_document_1.id,
            "_block_document_name": "middle-block-document-1",
            "_is_anonymous": False,
            "block_type_slug": "c",
        }
        assert block_instance.d.model_dump() == {
            "b": {
                "x": 1,
                "_block_document_id": inner_block_document.id,
                "_block_document_name": "inner-block-document",
                "_is_anonymous": False,
                "block_type_slug": "b",
            },
            "z": "ztop",
            "_block_document_id": middle_block_document_2.id,
            "_block_document_name": "middle-block-document-2",
            "_is_anonymous": False,
            "block_type_slug": "d",
        }

    async def test_create_block_from_nonexistent_name(self, test_block):
        with pytest.raises(
            ValueError,
            match="Unable to find block document named blocky for block type x",
        ):
            await test_block.load("blocky")

    async def test_save_block_from_flow(self):
        class Test(Block):
            a: str

        @prefect.flow
        def save_block_flow():
            Test(a="foo").save("test")

        save_block_flow()

        block = await Test.load("test")
        assert block.a == "foo"

    async def test_save_protected_block_with_new_block_schema_version(
        self, session, prefect_client: PrefectClient
    ):
        """
        This testcase would fail when block protection was enabled for block type
        updates and block schema creation.
        """
        await models.block_registration.run_block_auto_registration(session=session)
        await session.commit()

        mock_version = (
            uuid4().hex
        )  # represents a version that does not exist on the server

        Secret._block_schema_version = mock_version

        block_document_id = await Secret(value="secret").save("test")

        block_document = await prefect_client.read_block_document(block_document_id)
        assert block_document.block_schema.version == mock_version


class TestRegisterBlockTypeAndSchema:
    class NewBlock(Block):
        a: str
        b: str
        c: int

    async def test_register_type_and_schema(self, prefect_client: PrefectClient):
        await self.NewBlock.register_type_and_schema()

        block_type = await prefect_client.read_block_type_by_slug(slug="newblock")
        assert block_type is not None
        assert block_type.name == "NewBlock"

        block_schema = await prefect_client.read_block_schema_by_checksum(
            checksum=self.NewBlock._calculate_schema_checksum()
        )
        assert block_schema is not None
        assert block_schema.fields == self.NewBlock.model_json_schema()

        assert isinstance(self.NewBlock._block_type_id, UUID)
        assert isinstance(self.NewBlock._block_schema_id, UUID)

    async def test_register_idempotent(self, prefect_client: PrefectClient):
        await self.NewBlock.register_type_and_schema()
        await self.NewBlock.register_type_and_schema()

        block_type = await prefect_client.read_block_type_by_slug(slug="newblock")
        assert block_type is not None
        assert block_type.name == "NewBlock"

        block_schema = await prefect_client.read_block_schema_by_checksum(
            checksum=self.NewBlock._calculate_schema_checksum()
        )
        assert block_schema is not None
        assert block_schema.fields == self.NewBlock.model_json_schema()

    async def test_register_existing_block_type_new_block_schema(
        self, prefect_client: PrefectClient
    ):
        # Ignore warning caused by matching key in registry
        warnings.filterwarnings("ignore", category=UserWarning)

        class ImpostorBlock(Block):
            _block_type_name = "NewBlock"
            x: str
            y: str
            z: int

        await ImpostorBlock.register_type_and_schema()

        block_type = await prefect_client.read_block_type_by_slug(slug="newblock")
        assert block_type is not None
        assert block_type.name == "NewBlock"

        await self.NewBlock.register_type_and_schema()

        block_schema = await prefect_client.read_block_schema_by_checksum(
            checksum=self.NewBlock._calculate_schema_checksum()
        )
        assert block_schema is not None
        assert block_schema.fields == self.NewBlock.model_json_schema()

    async def test_register_new_block_schema_when_version_changes(
        self, prefect_client: PrefectClient
    ):
        # Ignore warning caused by matching key in registry
        warnings.filterwarnings("ignore", category=UserWarning)

        await self.NewBlock.register_type_and_schema()

        block_schema = await prefect_client.read_block_schema_by_checksum(
            checksum=self.NewBlock._calculate_schema_checksum()
        )
        assert block_schema is not None
        assert block_schema.fields == self.NewBlock.model_json_schema()
        assert block_schema.version == DEFAULT_BLOCK_SCHEMA_VERSION

        self.NewBlock._block_schema_version = "new_version"

        await self.NewBlock.register_type_and_schema()

        block_schema = await prefect_client.read_block_schema_by_checksum(
            checksum=self.NewBlock._calculate_schema_checksum()
        )
        assert block_schema is not None
        assert block_schema.fields == self.NewBlock.model_json_schema()
        assert block_schema.version == "new_version"

        self.NewBlock._block_schema_version = None

    async def test_register_nested_block(self, prefect_client: PrefectClient):
        class Big(Block):
            id: UUID = Field(default_factory=uuid4)
            size: int

        class Bigger(Block):
            size: int
            contents: Big
            random_other_field: Dict[str, float]

        class Biggest(Block):
            size: int
            contents: Bigger

        await Biggest.register_type_and_schema()

        big_block_type = await prefect_client.read_block_type_by_slug(slug="big")
        assert big_block_type is not None
        big_block_schema = await prefect_client.read_block_schema_by_checksum(
            checksum=Big._calculate_schema_checksum()
        )
        assert big_block_schema is not None

        bigger_block_type = await prefect_client.read_block_type_by_slug(slug="bigger")
        assert bigger_block_type is not None
        bigger_block_schema = await prefect_client.read_block_schema_by_checksum(
            checksum=Bigger._calculate_schema_checksum()
        )
        assert bigger_block_schema is not None

        biggest_block_type = await prefect_client.read_block_type_by_slug(
            slug="biggest"
        )
        assert biggest_block_type is not None
        biggest_block_schema = await prefect_client.read_block_schema_by_checksum(
            checksum=Biggest._calculate_schema_checksum()
        )
        assert biggest_block_schema is not None

    async def test_register_nested_block_union(self, prefect_client: PrefectClient):
        class A(Block):
            a: str

        class B(Block):
            b: str

        class C(Block):
            c: str

        class Umbrella(Block):
            a_b_or_c: Union[A, B, C]

        await Umbrella.register_type_and_schema()

        a_block_type = await prefect_client.read_block_type_by_slug(slug="a")
        assert a_block_type is not None
        b_block_type = await prefect_client.read_block_type_by_slug(slug="b")
        assert b_block_type is not None
        c_block_type = await prefect_client.read_block_type_by_slug(slug="c")
        assert c_block_type is not None
        umbrella_block_type = await prefect_client.read_block_type_by_slug(
            slug="umbrella"
        )
        assert umbrella_block_type is not None

        a_block_schema = await prefect_client.read_block_schema_by_checksum(
            checksum=A._calculate_schema_checksum()
        )
        assert a_block_schema is not None
        b_block_schema = await prefect_client.read_block_schema_by_checksum(
            checksum=B._calculate_schema_checksum()
        )
        assert b_block_schema is not None
        c_block_schema = await prefect_client.read_block_schema_by_checksum(
            checksum=C._calculate_schema_checksum()
        )
        assert c_block_schema is not None
        umbrella_block_schema = await prefect_client.read_block_schema_by_checksum(
            checksum=Umbrella._calculate_schema_checksum()
        )
        assert umbrella_block_schema is not None

    async def test_register_nested_block_list(self, prefect_client: PrefectClient):
        class A(Block):
            a: str

        class B(Block):
            b: str

        class ListCollection(Block):
            a_list: list[A]
            b_list: List[B]

        await ListCollection.register_type_and_schema()

        a_block_type = await prefect_client.read_block_type_by_slug(slug="a")
        assert a_block_type is not None
        b_block_type = await prefect_client.read_block_type_by_slug(slug="b")
        assert b_block_type is not None

        list_collection_block_type = await prefect_client.read_block_type_by_slug(
            slug="listcollection"
        )
        assert list_collection_block_type is not None

        a_block_schema = await prefect_client.read_block_schema_by_checksum(
            checksum=A._calculate_schema_checksum()
        )
        assert a_block_schema is not None
        b_block_schema = await prefect_client.read_block_schema_by_checksum(
            checksum=B._calculate_schema_checksum()
        )
        assert b_block_schema is not None

        list_collection_block_type = await prefect_client.read_block_schema_by_checksum(
            checksum=ListCollection._calculate_schema_checksum()
        )
        assert list_collection_block_type is not None

    async def test_register_nested_block_tuple(self, prefect_client: PrefectClient):
        class A(Block):
            a: str

        class B(Block):
            b: str

        class C(Block):
            c: str

        class TupleCollection(Block):
            a_tuple: tuple[A]
            b_tuple: tuple[B, ...]
            c_tuple: Tuple[C, ...]

        await TupleCollection.register_type_and_schema()

        a_block_type = await prefect_client.read_block_type_by_slug(slug="a")
        assert a_block_type is not None
        b_block_type = await prefect_client.read_block_type_by_slug(slug="b")
        assert b_block_type is not None
        c_block_type = await prefect_client.read_block_type_by_slug(slug="c")
        assert c_block_type is not None

        tuple_collection_block_type = await prefect_client.read_block_type_by_slug(
            slug="tuplecollection"
        )
        assert tuple_collection_block_type is not None

        a_block_schema = await prefect_client.read_block_schema_by_checksum(
            checksum=A._calculate_schema_checksum()
        )
        assert a_block_schema is not None
        b_block_schema = await prefect_client.read_block_schema_by_checksum(
            checksum=B._calculate_schema_checksum()
        )
        assert b_block_schema is not None
        c_block_schema = await prefect_client.read_block_schema_by_checksum(
            checksum=C._calculate_schema_checksum()
        )
        assert c_block_schema is not None

        tuple_collection_block_type = (
            await prefect_client.read_block_schema_by_checksum(
                checksum=TupleCollection._calculate_schema_checksum()
            )
        )
        assert tuple_collection_block_type is not None

    async def test_register_nested_block_dict(self, prefect_client: PrefectClient):
        class A(Block):
            a: str

        class B(Block):
            b: str

        class DictCollection(Block):
            block_dict: dict[A, B]

        await DictCollection.register_type_and_schema()

        a_block_type = await prefect_client.read_block_type_by_slug(slug="a")
        assert a_block_type is not None
        b_block_type = await prefect_client.read_block_type_by_slug(slug="b")
        assert b_block_type is not None

        dict_collection_block_type = await prefect_client.read_block_type_by_slug(
            slug="dictcollection"
        )
        assert dict_collection_block_type is not None

        a_block_schema = await prefect_client.read_block_schema_by_checksum(
            checksum=A._calculate_schema_checksum()
        )
        assert a_block_schema is not None
        b_block_schema = await prefect_client.read_block_schema_by_checksum(
            checksum=B._calculate_schema_checksum()
        )
        assert b_block_schema is not None

        dict_collection_block_type = await prefect_client.read_block_schema_by_checksum(
            checksum=DictCollection._calculate_schema_checksum()
        )
        assert dict_collection_block_type is not None

    async def test_register_nested_block_type_nested(
        self, prefect_client: PrefectClient
    ):
        class A(Block):
            a: str

        class B(Block):
            b: str

        class C(Block):
            c: str

        class Depth(Block):
            depths: List[Union[A, List[Union[B, Tuple[C, ...]]]]]

        await Depth.register_type_and_schema()

        a_block_type = await prefect_client.read_block_type_by_slug(slug="a")
        assert a_block_type is not None
        b_block_type = await prefect_client.read_block_type_by_slug(slug="b")
        assert b_block_type is not None
        c_block_type = await prefect_client.read_block_type_by_slug(slug="c")
        assert c_block_type is not None

        depth_block_type = await prefect_client.read_block_type_by_slug(slug="depth")
        assert depth_block_type is not None

        a_block_schema = await prefect_client.read_block_schema_by_checksum(
            checksum=A._calculate_schema_checksum()
        )
        assert a_block_schema is not None
        b_block_schema = await prefect_client.read_block_schema_by_checksum(
            checksum=B._calculate_schema_checksum()
        )
        assert b_block_schema is not None
        c_block_schema = await prefect_client.read_block_schema_by_checksum(
            checksum=C._calculate_schema_checksum()
        )
        assert c_block_schema is not None

        depth_block_type = await prefect_client.read_block_schema_by_checksum(
            checksum=Depth._calculate_schema_checksum()
        )
        assert depth_block_type is not None

    async def test_register_raises_block_base_class(self):
        with pytest.raises(
            InvalidBlockRegistration,
            match=(
                "`register_type_and_schema` should be called on a Block "
                "subclass and not on the Block class directly."
            ),
        ):
            await Block.register_type_and_schema()

    async def test_register_updates_block_type(self, prefect_client: PrefectClient):
        # Ignore warning caused by matching key in registry
        warnings.filterwarnings("ignore", category=UserWarning)

        class Before(Block):
            _block_type_name = "Test Block"
            _description = "Before"
            message: str

        class After(Block):
            _block_type_name = "Test Block"
            _description = "After"
            message: str

        await Before.register_type_and_schema()

        block_type = await prefect_client.read_block_type_by_slug(slug="test-block")
        assert block_type.description == "Before"

        await After.register_type_and_schema()

        block_type = await prefect_client.read_block_type_by_slug(slug="test-block")
        assert block_type.description == "After"

    async def test_register_wont_update_same_block_type_values(
        self, prefect_client: PrefectClient
    ):
        # Ignore warning caused by matching key in registry
        warnings.filterwarnings("ignore", category=UserWarning)

        class Before(Block):
            _block_type_name = "Test Block"
            _description = "Before"
            message: str

        class After(Block):
            _block_type_name = "Test Block"
            _description = "After"
            message: str

        await Before.register_type_and_schema()

        block_type = await prefect_client.read_block_type_by_slug(slug="test-block")
        assert block_type.description == "Before"

        mock = AsyncMock()
        prefect_client.update_block_type = mock

        await After.register_type_and_schema(client=prefect_client)

        # change to description means we should try and update the block type
        assert mock.call_count == 1

        # confirm the call was mocked, description is the same
        block_type = await prefect_client.read_block_type_by_slug(slug="test-block")
        assert block_type.description == "Before"

        # if the description is the same as what matches the server, don't update
        await Before.register_type_and_schema(client=prefect_client)

        # call count should not have increased
        assert mock.call_count == 1

    async def test_register_fails_on_abc(self, prefect_client):
        class Interface(Block, abc.ABC):
            _block_schema_capabilities = ["do-stuff"]

            @abc.abstractmethod
            def do_stuff(self, thing: str):
                pass

        with pytest.raises(
            InvalidBlockRegistration,
            match=(
                "`register_type_and_schema` should be called on a Block "
                "subclass and not on a Block interface class directly."
            ),
        ):
            await Interface.register_type_and_schema(client=prefect_client)


class TestSaveBlock:
    @pytest.fixture
    def NewBlock(self):
        # Ignore warning caused by matching key in registry due to block fixture
        warnings.filterwarnings("ignore", category=UserWarning)

        class NewBlock(Block):
            a: str
            b: str

        return NewBlock

    @pytest.fixture
    def InnerBlock(self):
        class InnerBlock(Block):
            size: int

        return InnerBlock

    @pytest.fixture
    def OuterBlock(self, InnerBlock):
        class OuterBlock(Block):
            size: int
            contents: InnerBlock

        return OuterBlock

    async def test_save_block(self, NewBlock):
        new_block = NewBlock(a="foo", b="bar")
        new_block_name = "my-block"
        await new_block.save(new_block_name)

        assert new_block._block_document_name == new_block_name
        assert new_block._block_document_id is not None
        assert not new_block._is_anonymous

        loaded_new_block = await new_block.load(new_block_name)

        assert loaded_new_block._block_document_name == new_block_name
        assert loaded_new_block._block_document_id == new_block._block_document_id
        assert not loaded_new_block._is_anonymous

        assert loaded_new_block._block_type_name == new_block._block_type_name
        assert loaded_new_block._block_type_id == new_block._block_type_id

        assert loaded_new_block == new_block

    async def test_save_block_with_name_inferred_from_loaded_document(self, NewBlock):
        new_block = NewBlock(a="foo", b="bar")

        with pytest.raises(
            ValueError,
            match="You're attempting to save a block document without a name.",
        ):
            await new_block.save()

        await new_block.save("new-block")

        new_python_instance = await NewBlock.load("new-block")
        new_python_instance.a = "baz"
        await new_python_instance.save(overwrite=True)

        loaded_new_block = await NewBlock.load("new-block")
        assert loaded_new_block.a == "baz"
        assert loaded_new_block.b == "bar"

    async def test_save_anonymous_block(self, NewBlock):
        new_anon_block = NewBlock(a="foo", b="bar")
        await new_anon_block._save(is_anonymous=True)

        assert new_anon_block._block_document_name is not None
        assert new_anon_block._block_document_id is not None
        assert new_anon_block._is_anonymous

        loaded_new_anon_block = await NewBlock.load(new_anon_block._block_document_name)

        assert (
            loaded_new_anon_block._block_document_name
            == new_anon_block._block_document_name
        )
        assert (
            loaded_new_anon_block._block_document_id
            == new_anon_block._block_document_id
        )
        assert loaded_new_anon_block._is_anonymous

        assert loaded_new_anon_block._block_type_name == new_anon_block._block_type_name
        assert loaded_new_anon_block._block_type_id == new_anon_block._block_type_id

        assert loaded_new_anon_block == new_anon_block

    async def test_save_anonymous_block_more_than_once_creates_two_blocks(
        self, NewBlock
    ):
        new_anon_block = NewBlock(a="foo", b="bar")
        first_id = await new_anon_block._save(is_anonymous=True)
        second_id = await new_anon_block._save(is_anonymous=True)
        assert first_id != second_id

    async def test_save_throws_on_mismatched_kwargs(self, NewBlock):
        new_block = NewBlock(a="foo", b="bar")
        with pytest.raises(
            ValueError,
            match="You're attempting to save a block document without a name.",
        ):
            await new_block._save()

    async def test_save_nested_blocks(self):
        block_name = "biggest-block-in-all-the-land"

        class Big(Block):
            id: UUID = Field(default_factory=uuid4)
            size: int

        class Bigger(Block):
            size: int
            contents: Big
            random_other_field: Dict[str, float]

        class Biggest(Block):
            size: int
            contents: Bigger

        new_big_block = Big(size=1)
        await new_big_block.save("big-block")

        loaded_big_block = await Big.load("big-block")
        assert loaded_big_block == new_big_block

        new_bigger_block = Bigger(
            size=10, random_other_field={}, contents=new_big_block
        )
        await new_bigger_block.save("bigger-block")

        loaded_bigger_block = await Bigger.load("bigger-block")
        assert loaded_bigger_block == new_bigger_block

        new_biggest_block = Biggest(
            size=100,
            contents=new_bigger_block,
        )

        await new_biggest_block.save(block_name)

        loaded_biggest_block = await Biggest.load(block_name)
        assert loaded_biggest_block == new_biggest_block

    async def test_save_named_block_nested_in_anonymous_block(
        self, InnerBlock, OuterBlock
    ):
        named_inner_block = InnerBlock(size=1)
        await named_inner_block.save("the-inside-block")

        anonymous_outer_block = OuterBlock(size=10, contents=named_inner_block)
        await anonymous_outer_block._save(is_anonymous=True)

        assert anonymous_outer_block._block_document_name is not None
        assert anonymous_outer_block._is_anonymous

        loaded_anonymous_outer_block = await OuterBlock.load(
            anonymous_outer_block._block_document_name
        )
        assert loaded_anonymous_outer_block == anonymous_outer_block

    async def test_save_anonymous_block_nested_in_named_block(
        self, InnerBlock, OuterBlock
    ):
        anonymous_inner_block = InnerBlock(size=1)
        await anonymous_inner_block._save(is_anonymous=True)

        assert anonymous_inner_block._block_document_name is not None
        assert anonymous_inner_block._is_anonymous

        named_outer_block = OuterBlock(size=10, contents=anonymous_inner_block)
        await named_outer_block.save("the-outer-block")

        loaded_anonymous_outer_block = await OuterBlock.load("the-outer-block")
        assert loaded_anonymous_outer_block == named_outer_block

    async def test_save_nested_block_without_references(self, InnerBlock, OuterBlock):
        new_inner_block = InnerBlock(size=1)
        new_outer_block = OuterBlock(size=10, contents=new_inner_block)
        await new_outer_block.save("outer-block-no-references")

        loaded_outer_block = await OuterBlock.load("outer-block-no-references")
        assert_blocks_equal(loaded_outer_block, new_outer_block)
        assert isinstance(loaded_outer_block.contents, InnerBlock)
        assert_blocks_equal(loaded_outer_block.contents, new_inner_block)
        assert loaded_outer_block.contents._block_document_id is None
        assert loaded_outer_block.contents._block_document_name is None

    async def test_save_and_load_block_with_secrets_includes_secret_data(
        self, prefect_client: PrefectClient
    ):
        class SecretBlockB(Block):
            w: SecretDict
            x: SecretStr
            y: SecretBytes
            z: str

        block = SecretBlockB(w=dict(secret="value"), x="x", y=b"y", z="z")
        await block.save("secret-block")

        # read from API without secrets
        api_block = await prefect_client.read_block_document(
            block._block_document_id, include_secrets=False
        )
        assert api_block.data == {
            "w": {"secret": "********"},
            "x": "********",
            "y": "********",
            "z": "z",
        }

        # read from API with secrets
        api_block = await prefect_client.read_block_document(
            block._block_document_id, include_secrets=True
        )
        assert api_block.data == {
            "w": {"secret": "value"},
            "x": "x",
            "y": "y",
            "z": "z",
        }

        # load block with secrets
        api_block = await SecretBlockB.load("secret-block")
        assert api_block.w.get_secret_value() == {"secret": "value"}
        assert api_block.x.get_secret_value() == "x"
        assert api_block.y.get_secret_value() == b"y"
        assert api_block.z == "z"

    async def test_save_and_load_nested_block_with_secrets_hardcoded_child(
        self, prefect_client: PrefectClient
    ):
        class Child(Block):
            a: SecretStr
            b: str
            c: SecretDict

        class Parent(Block):
            a: SecretStr
            b: str
            child: Child

        block = Parent(a="a", b="b", child=dict(a="a", b="b", c=dict(secret="value")))
        await block.save("secret-block")

        # read from API without secrets
        api_block = await prefect_client.read_block_document(
            block._block_document_id, include_secrets=False
        )
        assert api_block.data == {
            "a": "********",
            "b": "b",
            "child": {
                "a": "********",
                "b": "b",
                "c": {"secret": "********"},
                "block_type_slug": "child",
            },
        }

        # read from API with secrets
        api_block = await prefect_client.read_block_document(
            block._block_document_id, include_secrets=True
        )
        assert api_block.data == {
            "a": "a",
            "b": "b",
            "child": {
                "a": "a",
                "b": "b",
                "c": {"secret": "value"},
                "block_type_slug": "child",
            },
        }

        # load block with secrets
        api_block = await Parent.load("secret-block")
        assert api_block.a.get_secret_value() == "a"
        assert api_block.b == "b"
        assert api_block.child.a.get_secret_value() == "a"
        assert api_block.child.b == "b"
        assert api_block.child.c.get_secret_value() == {"secret": "value"}

    async def test_save_and_load_nested_block_with_secrets_saved_child(
        self, prefect_client: PrefectClient
    ):
        class Child(Block):
            a: SecretStr
            b: str
            c: SecretDict

        class Parent(Block):
            a: SecretStr
            b: str
            child: Child

        child = Child(a="a", b="b", c=dict(secret="value"))
        await child.save("child-block")
        block = Parent(a="a", b="b", child=child)
        await block.save("parent-block")

        # read from API without secrets
        api_block = await prefect_client.read_block_document(
            block._block_document_id, include_secrets=False
        )
        assert api_block.data == {
            "a": "********",
            "b": "b",
            "child": {
                "a": "********",
                "b": "b",
                "c": {"secret": "********"},
            },
        }

        # read from API with secrets
        api_block = await prefect_client.read_block_document(
            block._block_document_id, include_secrets=True
        )
        assert api_block.data == {
            "a": "a",
            "b": "b",
            "child": {"a": "a", "b": "b", "c": {"secret": "value"}},
        }

        # load block with secrets
        api_block = await Parent.load("parent-block")
        assert api_block.a.get_secret_value() == "a"
        assert api_block.b == "b"
        assert api_block.child.a.get_secret_value() == "a"
        assert api_block.child.b == "b"
        assert api_block.child.c.get_secret_value() == {"secret": "value"}

    async def test_save_block_with_overwrite(self, InnerBlock):
        inner_block = InnerBlock(size=1)
        await inner_block.save("my-inner-block")

        inner_block.size = 2
        await inner_block.save("my-inner-block", overwrite=True)

        loaded_inner_block = await InnerBlock.load("my-inner-block")
        loaded_inner_block.size = 2
        assert loaded_inner_block == inner_block

    async def test_save_block_without_overwrite_raises(self, InnerBlock):
        inner_block = InnerBlock(size=1)
        await inner_block.save("my-inner-block")

        inner_block.size = 2

        with pytest.raises(
            ValueError,
            match=(
                "You are attempting to save values with a name that is already in "
                "use for this block type"
            ),
        ):
            await inner_block.save("my-inner-block")

        loaded_inner_block = await InnerBlock.load("my-inner-block")
        loaded_inner_block.size = 1

    async def test_update_from_loaded_block(self, InnerBlock):
        inner_block = InnerBlock(size=1)
        await inner_block.save("my-inner-block")

        loaded_inner_block = await InnerBlock.load("my-inner-block")
        loaded_inner_block.size = 2
        await loaded_inner_block.save("my-inner-block", overwrite=True)

        loaded_inner_block_after_update = await InnerBlock.load("my-inner-block")
        assert loaded_inner_block == loaded_inner_block_after_update

    async def test_update_from_in_memory_block(self, InnerBlock):
        inner_block = InnerBlock(size=1)
        await inner_block.save("my-inner-block")

        updated_inner_block = InnerBlock(size=2)
        await updated_inner_block.save("my-inner-block", overwrite=True)

        loaded_inner_block = await InnerBlock.load("my-inner-block")
        loaded_inner_block.size = 2

        assert loaded_inner_block == updated_inner_block

    async def test_update_block_with_secrets(self):
        class HasSomethingToHide(Block):
            something_to_hide: SecretStr

        shifty_block = HasSomethingToHide(something_to_hide="a surprise birthday party")
        await shifty_block.save("my-shifty-block")

        updated_shifty_block = HasSomethingToHide(
            something_to_hide="a birthday present"
        )
        await updated_shifty_block.save("my-shifty-block", overwrite=True)

        loaded_shifty_block = await HasSomethingToHide.load("my-shifty-block")
        assert (
            loaded_shifty_block.something_to_hide.get_secret_value()
            == "a birthday present"
        )

    async def test_update_block_with_secret_dict(self):
        class HasSomethingToHide(Block):
            something_to_hide: SecretDict

        shifty_block = HasSomethingToHide(
            something_to_hide={
                "what I'm hiding": "a surprise birthday party",
            }
        )
        await shifty_block.save("my-shifty-block")

        updated_shifty_block = HasSomethingToHide(
            something_to_hide={"what I'm hiding": "a birthday present"}
        )
        await updated_shifty_block.save("my-shifty-block", overwrite=True)

        loaded_shifty_block = await HasSomethingToHide.load("my-shifty-block")
        assert loaded_shifty_block.something_to_hide.get_secret_value() == {
            "what I'm hiding": "a birthday present"
        }

    async def test_block_with_alias(self):
        class AliasBlock(Block):
            type: str
            schema_: str = Field(alias="schema")
            real_name: str = Field(alias="an_alias")
            threads: int = 4

        alias_block = AliasBlock(
            type="snowflake", schema="a_schema", an_alias="my_real_name", threads=8
        )
        await alias_block.save(name="my-aliased-block")

        loaded_alias_block = await AliasBlock.load("my-aliased-block")
        assert loaded_alias_block.type == "snowflake"
        assert loaded_alias_block.schema_ == "a_schema"
        assert loaded_alias_block.real_name == "my_real_name"
        assert loaded_alias_block.threads == 8


class TestToBlockType:
    def test_to_block_type_from_block(self, test_block: Type[Block]):
        block_type = test_block._to_block_type()

        assert block_type.name == test_block.__name__
        assert str(block_type.logo_url) == str(test_block._logo_url)
        assert str(block_type.documentation_url) == str(test_block._documentation_url)

    def test_to_block_type_override_block_type_name(self):
        class Pyramid(Block):
            _block_type_name = "PYRAMID!"

            height: float
            width: float
            length: float
            base_type: str

        block_type = Pyramid._to_block_type()

        assert block_type.name == "PYRAMID!"

    def test_to_block_type_with_description_from_docstring(self):
        class Cube(Block):
            "Has 8 faces."

            face_length_inches: float

        block_type = Cube._to_block_type()

        assert block_type.description == "Has 8 faces."

    def test_to_block_type_with_description_override(self):
        class Cube(Block):
            "Has 8 faces."

            _description = "Don't trust that docstring."

            face_length_inches: float

        assert Cube._to_block_type().description == "Don't trust that docstring."

    def test_to_block_type_with_description_and_example_docstring(self):
        class Cube(Block):
            """
            Has 8 faces.

            Example:
                Calculate volume:
                ```python
                from prefect_geometry import Cube

                my_cube = Cube.load("rubix")

                my_cube.calculate_area()
                ```
            """

            face_length_inches: float

            def calculate_area(self):
                return self.face_length_inches**3

        block_type = Cube._to_block_type()

        assert block_type.description == "Has 8 faces."
        assert block_type.code_example == dedent(
            """\
            Calculate volume:
            ```python
            from prefect_geometry import Cube

            my_cube = Cube.load("rubix")

            my_cube.calculate_area()
            ```"""
        )

    def test_to_block_type_with_description_and_examples_docstring(self):
        class Cube(Block):
            """
            Has 8 faces.

            Examples:
                Load block:
                ```python
                from prefect_geometry import Cube

                my_cube = Cube.load("rubix")
                ```

                Calculate volume:
                ```python
                my_cube.calculate_area()
                ```
            """

            face_length_inches: float

            def calculate_area(self):
                return self.face_length_inches**3

        block_type = Cube._to_block_type()

        assert block_type.description == "Has 8 faces."
        assert block_type.code_example == dedent(
            """\
            Load block:
            ```python
            from prefect_geometry import Cube

            my_cube = Cube.load("rubix")
            ```

            Calculate volume:
            ```python
            my_cube.calculate_area()
            ```"""
        )

    def test_to_block_type_with_example_override(self):
        class Cube(Block):
            """
            Has 8 faces.

            Example:
                Calculate volume:
                ```python
                my_cube = Cube.load("rubix")
                ```
            """

            _code_example = """\
            Don't trust that docstring. Here's how you really do it:
            ```python
            from prefect_geometry import Cube

            my_cube = Cube.load("rubix")

            my_cube.calculate_area()
            ```
            """

            face_length_inches: float

            def calculate_area(self):
                return self.face_length_inches**3

        block_type = Cube._to_block_type()

        assert block_type.description == "Has 8 faces."
        assert block_type.code_example == dedent(
            """\
            Don't trust that docstring. Here's how you really do it:
            ```python
            from prefect_geometry import Cube

            my_cube = Cube.load("rubix")

            my_cube.calculate_area()
            ```
            """
        )

    def test_to_block_type_with_slug_override(self):
        class TwentySidedDie(Block):
            _block_type_slug = "20-sided-die"
            color: str

        assert TwentySidedDie._to_block_type().slug == "20-sided-die"


class TestGetDescription:
    def test_no_description_configured(self):
        class A(Block):
            message: str

        assert A.get_description() is None

    def test_description_from_docstring(self, caplog):
        class A(Block):
            """
            A block, verily

            Heading:
                This extra stuff shouldn't show up in the description
            """

            message: str

        assert A.get_description() == "A block, verily"
        assert len(caplog.records) == 0

    def test_description_override(self):
        class A(Block):
            """I won't show up in this block's description"""

            _description = "But I will"

            message: str

        assert A.get_description() == "But I will"

    def test_no_griffe_logs(self, caplog, capsys, recwarn):
        """
        Ensures there are no extraneous output printed/warned.
        """

        class A(Block):
            """
            Without disable logger, this spawns griffe warnings.

            Args:
                string (str): This should spawn a warning
            """

        A()
        assert caplog.record_tuples == []

        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

        assert len(recwarn) == 0

        # to be extra sure that we are printing anything
        # we shouldn't be
        print("Sanity check!")
        captured = capsys.readouterr()
        assert captured.out == "Sanity check!\n"

        warnings.warn("Sanity check two!")
        assert len(recwarn) == 1


class NoCodeExample(Block):
    _block_type_name = "No code Example"

    message: str


class TestGetCodeExample:
    def test_no_code_example_configured(self):
        assert NoCodeExample.get_code_example() == dedent(
            """\
        ```python
        from test_core import NoCodeExample

        no_code_example_block = NoCodeExample.load("BLOCK_NAME")
        ```"""
        )

    def test_code_example_from_docstring_example_heading(self, caplog):
        class A(Block):
            """
            I won't show up in the code example

            Example:
                Here's how you do it:
                ```python
                from somewhere import A

                a_block = A.load("a block")

                a_block.send_message()
                ```
            """

            message: str

            def send_message(self):
                print(self.message)

        assert A.get_code_example() == dedent(
            """\
            Here's how you do it:
            ```python
            from somewhere import A

            a_block = A.load("a block")

            a_block.send_message()
            ```"""
        )
        assert len(caplog.records) == 0

    def test_code_example_from_docstring_examples_heading(self):
        class A(Block):
            """
            I won't show up in the code example

            Example:
                Here's how you do it:
                ```python
                from somewhere import A

                a_block = A.load("a block")

                a_block.send_message()
                ```

                Here's something extra:
                ```python
                print(42)
                ```
            """

            message: str

            def send_message(self):
                print(self.message)

        assert A.get_code_example() == dedent(
            """\
            Here's how you do it:
            ```python
            from somewhere import A

            a_block = A.load("a block")

            a_block.send_message()
            ```

            Here's something extra:
            ```python
            print(42)
            ```"""
        )

    def test_code_example_override(self):
        class A(Block):
            """
            I won't show up in the code example

            Example:
                ```python
                print(42)
                ```
            """

            _code_example = """\
                Here's the real example:

                ```python
                print("I am overriding the example in the docstring")
                ```"""

            message: str

            def send_message(self):
                print(self.message)

        assert A.get_code_example() == dedent(
            """\
                Here's the real example:

                ```python
                print("I am overriding the example in the docstring")
                ```"""
        )


class TestSyncCompatible:
    async def test_block_in_flow_sync_test_sync_flow(self):
        await CoolBlock(cool_factor=1000000).save("blk")

        @prefect.flow
        def my_flow():
            loaded_block = CoolBlock.load("blk")
            return loaded_block.cool_factor

        result = my_flow()
        assert result == 1000000

    async def test_block_in_flow_async_test_sync_flow(self):
        await CoolBlock(cool_factor=1000000).save("blk")

        @prefect.flow
        def my_flow():
            loaded_block = CoolBlock.load("blk")
            return loaded_block.cool_factor

        result = my_flow()
        assert result == 1000000

    async def test_block_in_flow_async_test_async_flow(self):
        await CoolBlock(cool_factor=1000000).save("blk")

        @prefect.flow
        async def my_flow():
            loaded_block = await CoolBlock.load("blk")
            return loaded_block.cool_factor

        result = await my_flow()
        assert result == 1000000

    async def test_block_in_task_sync_test_sync_flow(self):
        await CoolBlock(cool_factor=1000000).save("blk")

        @prefect.task
        def my_task():
            loaded_block = CoolBlock.load("blk")
            return loaded_block.cool_factor

        @prefect.flow()
        def my_flow():
            return my_task()

        result = my_flow()
        assert result == 1000000

    async def test_block_in_task_async_test_sync_task(self):
        await CoolBlock(cool_factor=1000000).save("blk")

        @prefect.task
        def my_task():
            loaded_block = CoolBlock.load("blk")
            return loaded_block.cool_factor

        @prefect.flow()
        def my_flow():
            return my_task()

        result = my_flow()
        assert result == 1000000

    async def test_block_in_task_async_test_async_task(self):
        await CoolBlock(cool_factor=1000000).save("blk")

        @prefect.task
        async def my_task():
            loaded_block = await CoolBlock.load("blk")
            return loaded_block.cool_factor

        @prefect.flow()
        async def my_flow():
            return await my_task()

        result = await my_flow()
        assert result == 1000000


# Define types for `TestTypeDispatch`


class BaseBlock(Block):
    base: int = 0


class ParentModel(BaseModel):
    block: BaseBlock


class AChildBlock(BaseBlock):
    a: int = 1


class BChildBlock(BaseBlock):
    b: int = 2


class TestTypeDispatch:
    def test_block_type_slug_is_included_in_dict(self):
        assert "block_type_slug" in AChildBlock().model_dump()

    def test_block_type_slug_respects_exclude(self):
        assert "block_type_slug" not in AChildBlock().model_dump(
            exclude={"block_type_slug"}
        )

    def test_block_type_slug_respects_include(self):
        assert "block_type_slug" not in AChildBlock().model_dump(include={"a"})

    async def test_block_type_slug_excluded_from_document(self, prefect_client):
        await AChildBlock.register_type_and_schema(client=prefect_client)
        document = AChildBlock()._to_block_document(name="foo")
        assert "block_type_slug" not in document.data

    def test_base_parse_works_for_base_instance(self):
        block = BaseBlock.model_validate(BaseBlock().model_dump())
        assert type(block) == BaseBlock

        block = BaseBlock.model_validate(BaseBlock().model_dump())
        assert type(block) == BaseBlock

    def test_base_parse_creates_child_instance_from_dict(self):
        block = BaseBlock.model_validate(AChildBlock().model_dump())
        assert type(block) == AChildBlock

        block = BaseBlock.model_validate(BChildBlock().model_dump())
        assert type(block) == BChildBlock

    def test_base_parse_creates_child_instance_from_json(self):
        block = BaseBlock.model_validate_json(AChildBlock().model_dump_json())
        assert type(block) == AChildBlock

        block = BaseBlock.model_validate_json(BChildBlock().model_dump_json())
        assert type(block) == BChildBlock

    def test_base_parse_retains_default_attributes(self):
        block = BaseBlock.model_validate(AChildBlock().model_dump())
        assert block.base == 0
        assert block.a == 1

    def test_base_parse_retains_set_child_attributes(self):
        block = BaseBlock.model_validate(BChildBlock(b=3).model_dump())
        assert block.base == 0
        assert block.b == 3

    def test_base_parse_retains_set_base_attributes(self):
        block = BaseBlock.model_validate(BChildBlock(base=1).model_dump())
        assert block.base == 1
        assert block.b == 2

    def test_base_field_creates_child_instance_from_object(self):
        model = ParentModel(block=AChildBlock())
        assert type(model.block) == AChildBlock

        model = ParentModel(block=BChildBlock())
        assert type(model.block) == BChildBlock

    def test_base_field_creates_child_instance_from_dict(self):
        model = ParentModel(block=AChildBlock().model_dump())
        assert type(model.block) == AChildBlock

        model = ParentModel(block=BChildBlock().model_dump())
        assert type(model.block) == BChildBlock

    def test_created_block_has_pydantic_attributes(self):
        block = BaseBlock.model_validate(AChildBlock().model_dump())
        assert block.model_fields_set

    def test_created_block_can_be_copied(self):
        block = BaseBlock.model_validate(AChildBlock().model_dump())
        block_copy = block.model_copy()
        assert block == block_copy

    async def test_created_block_can_be_saved(self):
        block = BaseBlock.model_validate(AChildBlock().model_dump())
        assert await block.save("test")

    async def test_created_block_can_be_saved_then_loaded(self):
        block = BaseBlock.model_validate(AChildBlock().model_dump())
        await block.save("test")
        new_block = await block.load("test")
        assert_blocks_equal(block, new_block)
        assert new_block.model_fields_set

    def test_created_block_fields_set(self):
        expected = {"base", "block_type_slug", "a"}

        block = BaseBlock.model_validate(AChildBlock().model_dump())
        assert block.model_fields_set == expected
        assert block.a == 1

        block = BaseBlock.model_validate(AChildBlock(a=2).model_dump())
        assert block.model_fields_set == expected
        assert block.a == 2

        block = block.model_copy()
        assert block.model_fields_set == expected
        assert block.a == 2

    def test_base_field_creates_child_instance_with_union(self):
        class UnionParentModel(BaseModel):
            block: Union[AChildBlock, BChildBlock]

        model = UnionParentModel(block=AChildBlock(a=3).model_dump())
        assert type(model.block) == AChildBlock

        # Assignment with a copy works still
        model.block = model.block.model_copy()
        assert type(model.block) == AChildBlock
        assert model.block

        model = UnionParentModel(block=BChildBlock(b=4).model_dump())
        assert type(model.block) == BChildBlock

    def test_base_field_creates_child_instance_with_assignment_validation(self):
        class AssignmentParentModel(BaseModel, validate_assignment=True):
            block: BaseBlock

        model = AssignmentParentModel(block=AChildBlock(a=3).model_dump())
        assert type(model.block) == AChildBlock
        assert model.block.a == 3

        model.block = model.block.model_copy()
        assert type(model.block) == AChildBlock
        assert model.block.a == 3

        model.block = BChildBlock(b=4).model_dump()
        assert type(model.block) == BChildBlock
        assert model.block.b == 4


class TestBlockSchemaMigration:
    async def test_schema_mismatch_with_validation_raises(self):
        class A(Block):
            _block_type_name = "a"
            _block_type_slug = "a"
            x: int = 1

        a = A()

        await a.save("test")

        with pytest.warns(UserWarning, match="matches existing registered type 'A'"):

            class A_Alias(Block):
                _block_type_name = "a"
                _block_type_slug = "a"
                x: int = 1
                y: int

        with pytest.raises(
            RuntimeError, match="try loading again with `validate=False`"
        ):
            await A_Alias.load("test")

    async def test_add_field_to_schema_partial_load_with_skip_validation(self):
        class A(Block):
            x: int = 1

        a = A()

        await a.save("test")

        with pytest.warns(UserWarning, match="matches existing registered type 'A'"):

            class A_Alias(Block):
                _block_type_name = "a"
                _block_type_slug = "a"
                x: int = 1
                y: int

        with pytest.warns(UserWarning, match="Could not fully load"):
            a = await A_Alias.load("test", validate=False)

        assert a.x == 1
        assert a.y is None

    async def test_rm_field_from_schema_loads_with_validation(self):
        class Foo(Block):
            _block_type_name = "foo"
            _block_type_slug = "foo"
            x: int = 1
            y: int = 2

        foo = Foo()

        await foo.save("xy")

        with pytest.warns(UserWarning, match="matches existing registered type 'Foo'"):

            class Foo_Alias(Block):
                _block_type_name = "foo"
                _block_type_slug = "foo"
                x: int = 1

        foo_alias = await Foo_Alias.load("xy")

        assert foo_alias.x == 1

        # TODO: This should raise an AttributeError, but it doesn't
        # because `Config.extra = "allow"`
        # with pytest.raises(AttributeError):
        #     foo_alias.y

    async def test_load_with_skip_validation_keeps_metadata(self):
        class Bar(Block):
            x: int = 1

        bar = Bar()

        await bar.save("test")

        bar_new = await Bar.load("test", validate=False)

        assert bar.model_dump() == bar_new.model_dump()

    async def test_save_new_schema_with_overwrite(self, prefect_client):
        class Baz(Block):
            _block_type_name = "baz"
            _block_type_slug = "baz"
            x: int = 1

        baz = Baz()

        await baz.save("test")

        block_document = await prefect_client.read_block_document_by_name(
            name="test", block_type_slug="baz"
        )
        old_schema_id = block_document.block_schema_id

        with pytest.warns(UserWarning, match="matches existing registered type 'Baz'"):

            class Baz_Alias(Block):
                _block_type_name = "baz"
                _block_type_slug = "baz"
                x: int = 1
                y: int = 2

        baz_alias = await Baz_Alias.load("test", validate=False)

        await baz_alias.save("test", overwrite=True)

        baz_alias_RELOADED = await Baz_Alias.load("test")

        assert baz_alias_RELOADED.x == 1
        assert baz_alias_RELOADED.y == 2

        new_schema_id = baz_alias._block_schema_id

        # new local schema ID should be different because field added
        assert old_schema_id != new_schema_id

        updated_schema = await prefect_client.read_block_document_by_name(
            name="test", block_type_slug="baz"
        )
        updated_schema_id = updated_schema.block_schema_id

        # new local schema ID should now be saved to Prefect
        assert updated_schema_id == new_schema_id


class TestDeleteBlock:
    @pytest.fixture
    def NewBlock(self):
        # Ignore warning caused by matching key in registry due to block fixture
        warnings.filterwarnings("ignore", category=UserWarning)

        class NewBlock(Block):
            a: str
            b: str
            _block_type_slug = "new-block"

        return NewBlock

    async def test_delete_block(self, NewBlock):
        new_block = NewBlock(a="foo", b="bar")
        new_block_name = "my-block"
        await new_block.save(new_block_name)

        loaded_new_block = await new_block.load(new_block_name)
        assert loaded_new_block._block_document_name == new_block_name

        await NewBlock.delete(new_block_name)

        with pytest.raises(ValueError) as exception:
            await new_block.load(new_block_name)
            assert (
                f"Unable to find block document named {new_block_name}"
                in exception.value
            )

    async def test_delete_block_from_base_block(self, NewBlock):
        new_block = NewBlock(a="foo", b="bar")
        new_block_name = "my-block"

        await new_block.save(new_block_name)

        loaded_new_block = await new_block.load(new_block_name)
        assert loaded_new_block._block_document_name == new_block_name

        await Block.delete(f"{new_block._block_type_slug}/{new_block_name}")

        with pytest.raises(ValueError) as exception:
            await new_block.load(new_block_name)
            assert (
                f"Unable to find block document named {new_block_name}"
                in exception.value
            )


class NestedFunModel(BaseModel):
    loser: str = "drake"
    nested_secret_str: SecretStr
    nested_secret_bytes: SecretBytes
    nested_secret_int: PydanticSecret[int]
    all_my_enemies_secrets: List[SecretStr]


class FunSecretModel(Block):
    winner: str = "kendrick"
    secret_str: SecretStr
    secret_str_manual: PydanticSecret[str]
    secret_bytes: SecretBytes
    secret_bytes_manual: PydanticSecret[bytes]
    secret_int: PydanticSecret[int]
    nested_model: NestedFunModel
    normal_dictionary: Dict[str, Union[str, Dict[str, Any]]]
    secret_dict: SecretDict


class TestDumpSecrets:
    @pytest.fixture
    def secret_data(self) -> bytes:
        return to_json(
            {
                "winner": "kendrick",
                "secret_str": "back to back? i like that record",
                "secret_str_manual": "ima get back to that for the record",
                "secret_bytes": b"dudes be byting my style",
                "secret_bytes_manual": b"sneak dissing",
                "secret_int": 31415,
                "nested_model": {
                    "loser": "drake",
                    "nested_secret_str": "call me a bird the way im nesting",
                    "nested_secret_bytes": b"nesting like a bird",
                    "nested_secret_int": 54321,
                    "all_my_enemies_secrets": [
                        "culture vulture",
                        "not really a secret",
                        "but still",
                        "you know",
                    ],
                },
                "normal_dictionary": {
                    "keys": "do not",
                    "matter": "at all",
                    "because": {
                        "they": "are not",
                        "typed": "on the model",
                        "so": ["they", "can be", "anything"],
                    },
                },
                "secret_dict": {"shoooOOOooo!": "bih! bih! bih! bih!"},
            }
        )

    def test_dump_obscured_secrets(self, secret_data):
        block = FunSecretModel.model_validate_json(secret_data)
        assert block.model_dump() == {
            "block_type_slug": "funsecretmodel",
            "winner": "kendrick",
            "secret_str": SecretStr("back to back? i like that record"),
            "secret_str_manual": PydanticSecret[str](
                "ima get back to that for the record"
            ),
            "secret_bytes": SecretBytes(b"dudes be byting my style"),
            "secret_bytes_manual": PydanticSecret[bytes](b"sneak dissing"),
            "secret_int": PydanticSecret[int](31415),
            "nested_model": {
                "loser": "drake",
                "nested_secret_str": SecretStr("call me a bird the way im nesting"),
                "nested_secret_bytes": SecretBytes(b"nesting like a bird"),
                "nested_secret_int": PydanticSecret[int](54321),
                "all_my_enemies_secrets": [
                    SecretStr("culture vulture"),
                    SecretStr("not really a secret"),
                    SecretStr("but still"),
                    SecretStr("you know"),
                ],
            },
            "normal_dictionary": {
                "keys": "do not",
                "matter": "at all",
                "because": {
                    "they": "are not",
                    "typed": "on the model",
                    "so": ["they", "can be", "anything"],
                },
            },
            "secret_dict": SecretDict({"shoooOOOooo!": "bih! bih! bih! bih!"}),
        }

    def test_dump_obscured_secrets_mode_json(self, secret_data):
        block = FunSecretModel.model_validate_json(secret_data)
        assert block.model_dump(mode="json") == {
            "block_type_slug": "funsecretmodel",
            "winner": "kendrick",
            "secret_str": "**********",
            "secret_str_manual": "**********",
            "secret_bytes": "**********",
            "secret_bytes_manual": "**********",
            "secret_int": "**********",
            "nested_model": {
                "loser": "drake",
                "nested_secret_str": "**********",
                "nested_secret_bytes": "**********",
                "nested_secret_int": "**********",
                "all_my_enemies_secrets": [
                    "**********",
                    "**********",
                    "**********",
                    "**********",
                ],
            },
            "normal_dictionary": {
                "keys": "do not",
                "matter": "at all",
                "because": {
                    "they": "are not",
                    "typed": "on the model",
                    "so": ["they", "can be", "anything"],
                },
            },
            # historically this was: {"key": "**********", ...}
            "secret_dict": "**********",
        }

    def test_dump_python_secrets(self, secret_data):
        block = FunSecretModel.model_validate_json(secret_data)
        assert block.model_dump(context={"include_secrets": True}) == {
            "block_type_slug": "funsecretmodel",
            "winner": "kendrick",
            "secret_str": "back to back? i like that record",
            "secret_str_manual": "ima get back to that for the record",
            "secret_bytes": b"dudes be byting my style",
            "secret_bytes_manual": b"sneak dissing",
            "secret_int": 31415,
            "nested_model": {
                "loser": "drake",
                "nested_secret_str": "call me a bird the way im nesting",
                "nested_secret_bytes": b"nesting like a bird",
                "nested_secret_int": 54321,
                "all_my_enemies_secrets": [
                    "culture vulture",
                    "not really a secret",
                    "but still",
                    "you know",
                ],
            },
            "normal_dictionary": {
                "keys": "do not",
                "matter": "at all",
                "because": {
                    "they": "are not",
                    "typed": "on the model",
                    "so": ["they", "can be", "anything"],
                },
            },
            "secret_dict": {"shoooOOOooo!": "bih! bih! bih! bih!"},
        }

    def test_dump_jsonable_secrets(self, secret_data):
        block = FunSecretModel.model_validate_json(secret_data)
        assert block.model_dump(context={"include_secrets": True}, mode="json") == {
            "block_type_slug": "funsecretmodel",
            "winner": "kendrick",
            "secret_str": "back to back? i like that record",
            "secret_str_manual": "ima get back to that for the record",
            "secret_bytes": "dudes be byting my style",
            "secret_bytes_manual": "sneak dissing",
            "secret_int": 31415,
            "nested_model": {
                "loser": "drake",
                "nested_secret_str": "call me a bird the way im nesting",
                "nested_secret_bytes": "nesting like a bird",
                "nested_secret_int": 54321,
                "all_my_enemies_secrets": [
                    "culture vulture",
                    "not really a secret",
                    "but still",
                    "you know",
                ],
            },
            "normal_dictionary": {
                "keys": "do not",
                "matter": "at all",
                "because": {
                    "they": "are not",
                    "typed": "on the model",
                    "so": ["they", "can be", "anything"],
                },
            },
            "secret_dict": {"shoooOOOooo!": "bih! bih! bih! bih!"},
        }

    def test_dump_json_secrets(self, secret_data):
        block = FunSecretModel.model_validate_json(secret_data)
        assert (
            block.model_dump_json(context={"include_secrets": True})
            == to_json(
                {
                    "winner": "kendrick",
                    "secret_str": "back to back? i like that record",
                    "secret_str_manual": "ima get back to that for the record",
                    "secret_bytes": "dudes be byting my style",
                    "secret_bytes_manual": "sneak dissing",
                    "secret_int": 31415,
                    "nested_model": {
                        "loser": "drake",
                        "nested_secret_str": "call me a bird the way im nesting",
                        "nested_secret_bytes": "nesting like a bird",
                        "nested_secret_int": 54321,
                        "all_my_enemies_secrets": [
                            "culture vulture",
                            "not really a secret",
                            "but still",
                            "you know",
                        ],
                    },
                    "normal_dictionary": {
                        "keys": "do not",
                        "matter": "at all",
                        "because": {
                            "they": "are not",
                            "typed": "on the model",
                            "so": ["they", "can be", "anything"],
                        },
                    },
                    "secret_dict": {"shoooOOOooo!": "bih! bih! bih! bih!"},
                    "block_type_slug": "funsecretmodel",
                }
            ).decode()
        )
