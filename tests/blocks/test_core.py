from textwrap import dedent
from typing import Dict, Optional, Type, Union
from uuid import UUID, uuid4

import pytest
from pydantic import Field

from prefect.blocks.core import BLOCK_REGISTRY, Block, get_block_class, register_block
from prefect.client import OrionClient
from prefect.orion import models
from prefect.orion.schemas.actions import BlockDocumentCreate


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
            get_block_class(self.MyRegisteredBlock._calculate_schema_checksum())
            is self.MyRegisteredBlock
        )

        assert (
            get_block_class(self.MyOtherRegisteredBlock._calculate_schema_checksum())
            is self.MyOtherRegisteredBlock
        )

        with pytest.raises(ValueError, match="(No block schema exists)"):
            get_block_class(self.MyBlock._calculate_schema_checksum())

    def test_create_api_block_schema(self, block_type_x):
        block_schema = self.MyRegisteredBlock._to_block_schema(
            block_type_id=block_type_x.id
        )
        assert (
            block_schema.checksum
            == "sha256:295c039674c2d9e8c697063e0a5c188a21cf5f564b94ed71b13ebfabdbb27ac3"
        )
        assert block_schema.fields == {
            "title": "MyRegisteredBlock",
            "type": "object",
            "properties": {
                "x": {"title": "X", "type": "string"},
                "y": {"title": "Y", "default": 1, "type": "integer"},
            },
            "block_schema_references": {},
            "block_type_name": "MyRegisteredBlock",
            "required": ["x"],
        }

    def test_registering_blocks_with_capabilities(self):
        @register_block
        class IncapableBlock(Block):
            # could use a little confidence
            _block_type_id = uuid4()

        @register_block
        class CapableBlock(Block):
            # kind of rude to the other Blocks
            _block_schema_capabilities = ["bluffing"]
            _block_type_id = uuid4()
            all_the_answers: str = "42 or something"

        capable_schema = CapableBlock._to_block_schema()
        assert capable_schema.capabilities == ["bluffing"]

        incapable_schema = IncapableBlock._to_block_schema()
        assert incapable_schema.capabilities == []

    def test_create_api_block_schema_only_includes_pydantic_fields(self, block_type_x):
        @register_block
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

    def test_create_api_block_schema_with_different_registered_name(self, block_type_x):
        block_schema = self.MyOtherRegisteredBlock._to_block_schema(
            block_type_id=block_type_x.id
        )
        assert (
            block_schema.checksum
            == "sha256:0ee40e3d110beef563d12af1e5b234d042237cffa3b344917f574b653d2a3b89"
        )
        assert block_schema.fields == {
            "title": "MyOtherRegisteredBlock",
            "type": "object",
            "properties": {
                "x": {"title": "X", "type": "string"},
                "y": {"title": "Y", "default": 1, "type": "integer"},
                "z": {"default": 2, "title": "Z", "type": "integer"},
            },
            "block_type_name": "MyOtherRegisteredBlock",
            "block_schema_references": {},
            "required": ["x"],
        }

    def test_block_classes_with_same_fields_but_different_comments_same_checksum(self):
        class A(Block):
            "This is A block"
            x: str = Field(..., description="This is x field")
            y: str
            z: str

        class B(Block):
            "This is B block"
            x: str
            y: str
            z: str

        # Rename so that two classes have same name
        B.__name__ = "A"

        assert A._calculate_schema_checksum() == B._calculate_schema_checksum()

    def test_create_api_block_with_arguments(self, block_type_x):
        with pytest.raises(ValueError, match="(No name provided)"):
            self.MyRegisteredBlock(x="x")._to_block_document()
        with pytest.raises(ValueError, match="(No block schema ID provided)"):
            self.MyRegisteredBlock(x="x")._to_block_document(name="block")
        assert self.MyRegisteredBlock(x="x")._to_block_document(
            name="block", block_schema_id=uuid4(), block_type_id=block_type_x.id
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

    def test_from_block_document_with_unregistered_block(self):
        class BlockyMcBlock(Block):
            fizz: str

        block_schema_id = uuid4()
        block_type_id = uuid4()
        api_block = BlockyMcBlock(fizz="buzz")._to_block_document(
            name="super important config",
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
        @register_block
        class MakesALottaAttributes(Block):
            real_field: str
            authentic_field: str

            def block_initialization(self):
                self.evil_fake_field = "evil fake data"

        my_block = MakesALottaAttributes(real_field="hello", authentic_field="marvin")
        api_block = my_block._to_block_document(
            name="a corrupted api block",
            block_schema_id=uuid4(),
            block_type_id=block_type_x.id,
        )
        assert "real_field" in api_block.data
        assert "authentic_field" in api_block.data
        assert "evil_fake_field" not in api_block.data

    def test_create_block_schema_from_block_without_capabilities(
        self, test_block: Type[Block], block_type_x
    ):
        block_schema = test_block._to_block_schema(block_type_id=block_type_x.id)

        assert block_schema.checksum == test_block._calculate_schema_checksum()
        assert block_schema.fields == test_block.schema()
        assert (
            block_schema.capabilities == []
        ), "No capabilities should be defined for this Block and defaults to []"

    def test_create_block_schema_from_block_with_capabilities(
        self, test_block: Type[Block], block_type_x
    ):
        block_schema = test_block._to_block_schema(block_type_id=block_type_x.id)

        assert block_schema.checksum == test_block._calculate_schema_checksum()
        assert block_schema.fields == test_block.schema()
        assert (
            block_schema.capabilities == []
        ), "No capabilities should be defined for this Block and defaults to []"

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
            "block_type_name": "ParentBlock",
            "block_schema_references": {
                "z": {
                    "block_schema_checksum": "sha256:1cb4f9a642f5f230f9ad221f0bbade2496aea3effd607bae27210fa056c96fc5",
                    "block_type_name": "Nested Block",
                }
            },
            "definitions": {
                "NestedBlock": {
                    "block_schema_references": {},
                    "block_type_name": "Nested Block",
                    "properties": {"x": {"title": "X", "type": "string"}},
                    "required": ["x"],
                    "title": "NestedBlock",
                    "type": "object",
                },
            },
        }

    async def test_block_load(self, test_block, block_document):
        my_block = await test_block.load(block_document.name)

        assert my_block._block_document_name == block_document.name
        assert my_block._block_document_id == block_document.id
        assert my_block._block_type_id == block_document.block_type_id
        assert my_block._block_schema_id == block_document.block_schema_id
        assert my_block.foo == "bar"

    async def test_load_nested_block(self, session):
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
                name="inner_block_document",
                data=dict(x=1),
                block_schema_id=block_schema_b.id,
                block_type_id=block_schema_b.block_type_id,
            ),
        )

        middle_block_document_1 = await models.block_documents.create_block_document(
            session=session,
            block_document=BlockDocumentCreate(
                name="middle_block_document_1",
                data=dict(y=2),
                block_schema_id=block_schema_c.id,
                block_type_id=block_schema_c.block_type_id,
            ),
        )
        middle_block_document_2 = await models.block_documents.create_block_document(
            session=session,
            block_document=BlockDocumentCreate(
                name="middle_block_document_2",
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
                name="outer_block_document",
                data={
                    "c": {"$ref": {"block_document_id": middle_block_document_1.id}},
                    "d": {"$ref": {"block_document_id": middle_block_document_2.id}},
                },
                block_schema_id=block_schema_e.id,
                block_type_id=block_schema_e.block_type_id,
            ),
        )

        await session.commit()

        block_instance = await E.load("outer_block_document")

        assert block_instance._block_document_name == outer_block_document.name
        assert block_instance._block_document_id == outer_block_document.id
        assert block_instance._block_type_id == outer_block_document.block_type_id
        assert block_instance._block_schema_id == outer_block_document.block_schema_id
        assert block_instance.c.dict() == {
            "y": 2,
            "_block_document_id": middle_block_document_1.id,
            "_block_document_name": "middle_block_document_1",
        }
        assert block_instance.d.dict() == {
            "b": {
                "x": 1,
                "_block_document_id": inner_block_document.id,
                "_block_document_name": "inner_block_document",
            },
            "z": "ztop",
            "_block_document_id": middle_block_document_2.id,
            "_block_document_name": "middle_block_document_2",
        }

    async def test_create_block_from_nonexistent_name(self, test_block):
        with pytest.raises(
            ValueError,
            match="Unable to find block document named blocky for block type x",
        ):
            await test_block.load("blocky")


class TestRegisterBlock:
    class NewBlock(Block):
        a: str
        b: str
        c: int

    async def test_register_block(self, orion_client: OrionClient):
        await self.NewBlock.register_type_and_schema()

        block_type = await orion_client.read_block_type_by_name(name="NewBlock")
        assert block_type is not None
        assert block_type.name == "NewBlock"

        block_schema = await orion_client.read_block_schema_by_checksum(
            checksum=self.NewBlock._calculate_schema_checksum()
        )
        assert block_schema is not None
        assert block_schema.fields == self.NewBlock.schema()

        assert isinstance(self.NewBlock._block_type_id, UUID)
        assert isinstance(self.NewBlock._block_schema_id, UUID)

    async def test_register_idempotent(self, orion_client: OrionClient):
        await self.NewBlock.register_type_and_schema()
        await self.NewBlock.register_type_and_schema()

        block_type = await orion_client.read_block_type_by_name(name="NewBlock")
        assert block_type is not None
        assert block_type.name == "NewBlock"

        block_schema = await orion_client.read_block_schema_by_checksum(
            checksum=self.NewBlock._calculate_schema_checksum()
        )
        assert block_schema is not None
        assert block_schema.fields == self.NewBlock.schema()

    async def test_register_existing_block_type_new_block_schema(
        self, orion_client: OrionClient
    ):
        class ImpostorBlock(Block):
            _block_type_name = "NewBlock"
            x: str
            y: str
            z: int

        await ImpostorBlock.register_type_and_schema()

        block_type = await orion_client.read_block_type_by_name(name="NewBlock")
        assert block_type is not None
        assert block_type.name == "NewBlock"

        await self.NewBlock.register_type_and_schema()

        block_schema = await orion_client.read_block_schema_by_checksum(
            checksum=self.NewBlock._calculate_schema_checksum()
        )
        assert block_schema is not None
        assert block_schema.fields == self.NewBlock.schema()

    async def test_register_nested_block(self, orion_client: OrionClient):
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

        big_block_type = await orion_client.read_block_type_by_name(name="Big")
        assert big_block_type is not None
        big_block_schema = await orion_client.read_block_schema_by_checksum(
            checksum=Big._calculate_schema_checksum()
        )
        assert big_block_schema is not None

        bigger_block_type = await orion_client.read_block_type_by_name(name="Bigger")
        assert bigger_block_type is not None
        bigger_block_schema = await orion_client.read_block_schema_by_checksum(
            checksum=Bigger._calculate_schema_checksum()
        )
        assert bigger_block_schema is not None

        biggest_block_type = await orion_client.read_block_type_by_name(name="Biggest")
        assert biggest_block_type is not None
        biggest_block_schema = await orion_client.read_block_schema_by_checksum(
            checksum=Biggest._calculate_schema_checksum()
        )
        assert biggest_block_schema is not None

    async def test_register_nested_block_union(self, orion_client: OrionClient):
        class A(Block):
            a: str

        class B(Block):
            b: str

        class C(Block):
            c: str

        class Umbrella(Block):
            a_b_or_c: Union[A, B, C]

        await Umbrella.register_type_and_schema()

        a_block_type = await orion_client.read_block_type_by_name(name="A")
        assert a_block_type is not None
        b_block_type = await orion_client.read_block_type_by_name(name="B")
        assert b_block_type is not None
        c_block_type = await orion_client.read_block_type_by_name(name="C")
        assert c_block_type is not None
        umbrella_block_type = await orion_client.read_block_type_by_name(
            name="Umbrella"
        )
        assert umbrella_block_type is not None

        a_block_schema = await orion_client.read_block_schema_by_checksum(
            checksum=A._calculate_schema_checksum()
        )
        assert a_block_schema is not None
        b_block_schema = await orion_client.read_block_schema_by_checksum(
            checksum=B._calculate_schema_checksum()
        )
        assert b_block_schema is not None
        c_block_schema = await orion_client.read_block_schema_by_checksum(
            checksum=C._calculate_schema_checksum()
        )
        assert c_block_schema is not None
        umbrella_block_schema = await orion_client.read_block_schema_by_checksum(
            checksum=Umbrella._calculate_schema_checksum()
        )
        assert umbrella_block_schema is not None

    async def test_register_raises_block_base_class(self):
        with pytest.raises(
            ValueError,
            match="`register_type_and_schema` should be called on a Block "
            "class and not on the Block class directly.",
        ):
            await Block.register_type_and_schema()


class TestSaveBlock:
    class NewBlock(Block):
        a: str
        b: str
        c: int

    async def test_save_block(self):
        new_block = self.NewBlock(a="foo", b="bar", c=1)
        new_block_name = "my-block"
        await new_block.save(new_block_name)

        assert new_block._block_document_name == new_block_name
        assert new_block._block_document_id is not None

        loaded_new_block = await new_block.load(new_block_name)

        assert loaded_new_block._block_document_name == new_block_name
        assert loaded_new_block._block_document_id == new_block._block_document_id

        assert loaded_new_block._block_type_name == new_block._block_type_name
        assert loaded_new_block._block_type_id == new_block._block_type_id

        assert loaded_new_block == new_block

    async def test_save_nested_block(self):
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


class TestToBlockType:
    def test_to_block_type_from_block(self, test_block: Type[Block]):
        block_type = test_block._to_block_type()

        assert block_type.name == test_block.__name__
        assert block_type.logo_url == test_block._logo_url
        assert block_type.documentation_url == test_block._documentation_url

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


class TestGetDescription:
    def test_no_description_configured(self):
        class A(Block):
            message: str

        assert A.get_description() == None

    def test_description_from_docstring(self):
        class A(Block):
            """
            A block, verily

            Heading:
                This extra stuff shouldn't show up in the description
            """

            message: str

        assert A.get_description() == "A block, verily"

    def test_description_override(self):
        class A(Block):
            """I won't show up in this block's description"""

            _description = "But I will"

            message: str

        assert A.get_description() == "But I will"


class TestGetCodeExample:
    def test_no_code_example_configured(self):
        class A(Block):
            message: str

        assert A.get_code_example() == None

    def test_code_example_from_docstring_example_heading(self):
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
