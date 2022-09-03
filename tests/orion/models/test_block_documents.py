import string
from typing import List
from uuid import uuid4

import pytest
import sqlalchemy as sa
from pydantic import SecretBytes, SecretStr

from prefect.blocks.core import Block
from prefect.orion import models, schemas
from prefect.orion.schemas.actions import BlockDocumentCreate
from prefect.orion.utilities.names import obfuscate_string


def long_string(s: str):
    return string.ascii_letters + s


X = long_string("x")
Y = long_string("y")
Z = long_string("z")


@pytest.fixture
async def block_schemas(session):
    class CanRun(Block):
        _block_schema_capabilities = ["run"]

        def run(self):
            pass

    class CanFly(Block):
        _block_schema_capabilities = ["fly"]

        def fly(self):
            pass

    class CanSwim(Block):
        _block_schema_capabilities = ["swim"]

        def swim(self):
            pass

    class A(Block):
        pass

    block_type_a = await models.block_types.create_block_type(
        session=session, block_type=A._to_block_type()
    )
    block_schema_a = await models.block_schemas.create_block_schema(
        session=session, block_schema=A._to_block_schema(block_type_id=block_type_a.id)
    )

    class B(CanFly, Block):

        x: int

    block_type_b = await models.block_types.create_block_type(
        session=session, block_type=B._to_block_type()
    )
    block_schema_b = await models.block_schemas.create_block_schema(
        session=session, block_schema=B._to_block_schema(block_type_id=block_type_b.id)
    )

    class C(CanRun, Block):
        y: int

    block_type_c = await models.block_types.create_block_type(
        session=session, block_type=C._to_block_type()
    )
    block_schema_c = await models.block_schemas.create_block_schema(
        session=session, block_schema=C._to_block_schema(block_type_id=block_type_c.id)
    )

    class D(CanFly, CanSwim, Block):
        b: B
        z: str

    block_type_d = await models.block_types.create_block_type(
        session=session, block_type=D._to_block_type()
    )
    block_schema_d = await models.block_schemas.create_block_schema(
        session=session, block_schema=D._to_block_schema(block_type_id=block_type_d.id)
    )

    class E(Block):
        c: C
        d: D

    block_type_e = await models.block_types.create_block_type(
        session=session, block_type=E._to_block_type()
    )
    block_schema_e = await models.block_schemas.create_block_schema(
        session=session, block_schema=E._to_block_schema(block_type_id=block_type_e.id)
    )

    await session.commit()

    return (
        block_schema_a,
        block_schema_b,
        block_schema_c,
        block_schema_d,
        block_schema_e,
    )


class TestCreateBlockDocument:
    async def test_create_block_document(self, session, block_schemas):
        result = await models.block_documents.create_block_document(
            session=session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="x",
                data=dict(y=1),
                block_schema_id=block_schemas[0].id,
                block_type_id=block_schemas[0].block_type_id,
            ),
        )
        await session.commit()

        assert result.name == "x"
        assert result.data == dict(y=1)
        assert result.block_schema_id == block_schemas[0].id
        assert result.block_schema.checksum == block_schemas[0].checksum
        assert result.is_anonymous is False

        db_block_document = await models.block_documents.read_block_document_by_id(
            session=session, block_document_id=result.id
        )
        assert db_block_document.id == result.id

    async def test_create_anonymous_block_document(self, session, block_schemas):
        result = await models.block_documents.create_block_document(
            session=session,
            block_document=schemas.actions.BlockDocumentCreate(
                data=dict(y=1),
                block_schema_id=block_schemas[0].id,
                block_type_id=block_schemas[0].block_type_id,
                is_anonymous=True,
            ),
        )
        await session.commit()

        assert result.name.startswith("anonymous-")
        assert result.data == dict(y=1)
        assert result.block_schema_id == block_schemas[0].id
        assert result.block_schema.checksum == block_schemas[0].checksum
        assert result.is_anonymous is True

        db_block_document = await models.block_documents.read_block_document_by_id(
            session=session, block_document_id=result.id
        )
        assert db_block_document.id == result.id
        assert db_block_document.name.startswith("anonymous-")

    async def test_create_anonymous_block_document_with_name(
        self, session, block_schemas
    ):
        result = await models.block_documents.create_block_document(
            session=session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="anon-123",
                data=dict(y=1),
                block_schema_id=block_schemas[0].id,
                block_type_id=block_schemas[0].block_type_id,
                is_anonymous=True,
            ),
        )
        await session.commit()

        assert result.name == "anon-123"
        assert result.data == dict(y=1)
        assert result.block_schema_id == block_schemas[0].id
        assert result.block_schema.checksum == block_schemas[0].checksum
        assert result.is_anonymous is True

        db_block_document = await models.block_documents.read_block_document_by_id(
            session=session, block_document_id=result.id
        )
        assert db_block_document.id == result.id
        assert db_block_document.name == "anon-123"

    async def test_create_block_document_errors_if_no_name_provided(
        self, session, block_schemas
    ):
        with pytest.raises(
            ValueError, match="(Names must be provided for block documents.)"
        ):
            schemas.actions.BlockDocumentCreate(
                data=dict(y=1),
                block_schema_id=block_schemas[0].id,
                block_type_id=block_schemas[0].block_type_id,
            )

    async def test_anonymous_blocks_get_random_names(self, session, block_schemas):
        block_document = schemas.actions.BlockDocumentCreate(
            data=dict(y=1),
            block_schema_id=block_schemas[0].id,
            block_type_id=block_schemas[0].block_type_id,
            is_anonymous=True,
        )
        result_1 = await models.block_documents.create_block_document(
            session=session, block_document=block_document
        )

        result_2 = await models.block_documents.create_block_document(
            session=session, block_document=block_document
        )

        assert result_1.name != result_2.name

    @pytest.mark.parametrize("is_anonymous", [False, True])
    async def test_named_blocks_have_unique_names(
        self, session, block_schemas, db, is_anonymous
    ):
        block_document = schemas.actions.BlockDocumentCreate(
            name="test-block",
            data=dict(y=1),
            block_schema_id=block_schemas[0].id,
            block_type_id=block_schemas[0].block_type_id,
            is_anonymous=is_anonymous,
        )

        before_count = await session.execute(
            sa.select(sa.func.count()).select_from(db.BlockDocument)
        )
        await models.block_documents.create_block_document(
            session=session, block_document=block_document
        )

        await session.commit()
        with pytest.raises(sa.exc.IntegrityError):
            await models.block_documents.create_block_document(
                session=session, block_document=block_document
            )
        await session.rollback()

        after_count = await session.execute(
            sa.select(sa.func.count()).select_from(db.BlockDocument)
        )

        # only one block created
        assert after_count.scalar() == before_count.scalar() + 1

    async def test_create_nested_block_document(self, session, block_schemas):
        nested_block_document = await models.block_documents.create_block_document(
            session=session,
            block_document=BlockDocumentCreate(
                name="x",
                data=dict(y=1),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
            ),
        )

        result = await models.block_documents.create_block_document(
            session=session,
            block_document=BlockDocumentCreate(
                name="z",
                data={
                    "a": 1,
                    "x": {"$ref": {"block_document_id": nested_block_document.id}},
                },
                block_schema_id=block_schemas[3].id,
                block_type_id=block_schemas[3].block_type_id,
            ),
        )

        assert result.name == "z"
        assert result.data == {
            "a": 1,
            "x": {"y": 1},
        }
        assert result.block_document_references == {
            "x": {
                "block_document": {
                    "id": nested_block_document.id,
                    "name": nested_block_document.name,
                    "block_type": nested_block_document.block_type,
                    "is_anonymous": False,
                    "block_document_references": {},
                }
            }
        }

        db_block_document = await models.block_documents.read_block_document_by_id(
            session, block_document_id=result.id
        )
        assert db_block_document.data == {
            "a": 1,
            "x": {"y": 1},
        }
        assert db_block_document.block_document_references == {
            "x": {
                "block_document": {
                    "id": nested_block_document.id,
                    "name": nested_block_document.name,
                    "block_type": nested_block_document.block_type,
                    "is_anonymous": False,
                    "block_document_references": {},
                }
            }
        }

    async def test_create_multiply_nested_block_document(self, session, block_schemas):
        inner_block_document = await models.block_documents.create_block_document(
            session=session,
            block_document=BlockDocumentCreate(
                name="inner-block-document",
                data=dict(x=1),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
            ),
        )

        middle_block_document_1 = await models.block_documents.create_block_document(
            session=session,
            block_document=BlockDocumentCreate(
                name="middle-block-document-1",
                data=dict(y=2),
                block_schema_id=block_schemas[2].id,
                block_type_id=block_schemas[2].block_type_id,
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
                block_schema_id=block_schemas[3].id,
                block_type_id=block_schemas[3].block_type_id,
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
                block_schema_id=block_schemas[4].id,
                block_type_id=block_schemas[4].block_type_id,
            ),
        )

        assert outer_block_document.data == {
            "c": {"y": 2},
            "d": {
                "b": {"x": 1},
                "z": "ztop",
            },
        }
        assert outer_block_document.block_document_references == {
            "c": {
                "block_document": {
                    "id": middle_block_document_1.id,
                    "name": middle_block_document_1.name,
                    "block_type": middle_block_document_1.block_type,
                    "is_anonymous": False,
                    "block_document_references": {},
                },
            },
            "d": {
                "block_document": {
                    "id": middle_block_document_2.id,
                    "name": middle_block_document_2.name,
                    "block_type": middle_block_document_2.block_type,
                    "is_anonymous": False,
                    "block_document_references": {
                        "b": {
                            "block_document": {
                                "id": inner_block_document.id,
                                "name": inner_block_document.name,
                                "block_type": inner_block_document.block_type,
                                "is_anonymous": False,
                                "block_document_references": {},
                            }
                        }
                    },
                }
            },
        }

        db_outer_block_document = (
            await models.block_documents.read_block_document_by_id(
                session, block_document_id=outer_block_document.id
            )
        )
        assert db_outer_block_document.data == {
            "c": {"y": 2},
            "d": {
                "b": {"x": 1},
                "z": "ztop",
            },
        }
        assert db_outer_block_document.block_document_references == {
            "c": {
                "block_document": {
                    "id": middle_block_document_1.id,
                    "name": middle_block_document_1.name,
                    "block_type": middle_block_document_1.block_type,
                    "is_anonymous": False,
                    "block_document_references": {},
                },
            },
            "d": {
                "block_document": {
                    "id": middle_block_document_2.id,
                    "name": middle_block_document_2.name,
                    "block_type": middle_block_document_2.block_type,
                    "is_anonymous": False,
                    "block_document_references": {
                        "b": {
                            "block_document": {
                                "id": inner_block_document.id,
                                "name": inner_block_document.name,
                                "block_type": inner_block_document.block_type,
                                "is_anonymous": False,
                                "block_document_references": {},
                            }
                        }
                    },
                }
            },
        }

        db_middle_block_document_2 = (
            await models.block_documents.read_block_document_by_id(
                session, block_document_id=middle_block_document_2.id
            )
        )
        assert db_middle_block_document_2.data == {
            "b": {"x": 1},
            "z": "ztop",
        }
        assert db_middle_block_document_2.block_document_references == {
            "b": {
                "block_document": {
                    "id": inner_block_document.id,
                    "name": inner_block_document.name,
                    "block_type": inner_block_document.block_type,
                    "is_anonymous": False,
                    "block_document_references": {},
                }
            }
        }

    async def test_create_block_with_same_name_as_existing_block(
        self, session, block_schemas
    ):
        assert await models.block_documents.create_block_document(
            session=session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="x",
                data=dict(),
                block_schema_id=block_schemas[0].id,
                block_type_id=block_schemas[0].block_type_id,
            ),
        )

        with pytest.raises(sa.exc.IntegrityError):
            await models.block_documents.create_block_document(
                session=session,
                block_document=schemas.actions.BlockDocumentCreate(
                    name="x",
                    data=dict(),
                    block_schema_id=block_schemas[0].id,
                    block_type_id=block_schemas[0].block_type_id,
                ),
            )

    async def test_create_block_with_same_name_as_existing_block_but_different_block_type(
        self, session, block_schemas
    ):
        assert await models.block_documents.create_block_document(
            session=session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="x",
                data=dict(),
                block_schema_id=block_schemas[0].id,
                block_type_id=block_schemas[0].block_type_id,
            ),
        )

        assert await models.block_documents.create_block_document(
            session=session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="x",
                data=dict(),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
            ),
        )

    async def test_create_anonymous_block_with_same_data_as_existing_block_but_different_block_type(
        self, session, block_schemas
    ):
        result1 = await models.block_documents.create_block_document(
            session=session,
            block_document=schemas.actions.BlockDocumentCreate(
                data=dict(),
                block_schema_id=block_schemas[0].id,
                block_type_id=block_schemas[0].block_type_id,
                is_anonymous=True,
            ),
        )

        result2 = await models.block_documents.create_block_document(
            session=session,
            block_document=schemas.actions.BlockDocumentCreate(
                data=dict(),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
                is_anonymous=True,
            ),
        )
        assert result1.id != result2.id
        assert result1.name != result2.name

    async def test_create_block_with_faulty_block_document_reference(
        self, session, block_schemas
    ):
        with pytest.raises(sa.exc.IntegrityError):
            await models.block_documents.create_block_document(
                session=session,
                block_document=BlockDocumentCreate(
                    name="z",
                    data={"a": 1, "b": {"$ref": {"block_document_id": uuid4()}}},
                    block_schema_id=block_schemas[3].id,
                    block_type_id=block_schemas[3].block_type_id,
                ),
            )

    async def test_create_block_with_missing_block_document_reference_id(
        self, session, block_schemas
    ):
        with pytest.raises(
            ValueError,
            match="Received block reference without a block_document_id in key b",
        ):
            await models.block_documents.create_block_document(
                session=session,
                block_document=BlockDocumentCreate(
                    name="z",
                    data={"a": 1, "b": {"$ref": {}}},
                    block_schema_id=block_schemas[3].id,
                    block_type_id=block_schemas[3].block_type_id,
                ),
            )


class TestReadBlockDocument:
    async def test_read_block_by_id(self, session, block_schemas):
        block = await models.block_documents.create_block_document(
            session=session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="x",
                data=dict(),
                block_schema_id=block_schemas[0].id,
                block_type_id=block_schemas[0].block_type_id,
            ),
        )

        result = await models.block_documents.read_block_document_by_id(
            session=session, block_document_id=block.id
        )
        assert result.id == block.id
        assert result.name == block.name
        assert result.block_schema_id == block_schemas[0].id
        assert result.block_type_id == block_schemas[0].block_type_id

    async def test_read_block_with_nesting(self, session, block_schemas):
        inner_block_document = await models.block_documents.create_block_document(
            session=session,
            block_document=BlockDocumentCreate(
                name="inner-block-document",
                data=dict(x=1),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
            ),
        )

        outer_block_document = await models.block_documents.create_block_document(
            session=session,
            block_document=BlockDocumentCreate(
                name="outer-block-document",
                data={
                    "b": {"$ref": {"block_document_id": inner_block_document.id}},
                    "z": "ztop",
                },
                block_schema_id=block_schemas[3].id,
                block_type_id=block_schemas[3].block_type_id,
            ),
        )

        result = await models.block_documents.read_block_document_by_id(
            session, block_document_id=outer_block_document.id
        )
        assert result.id == outer_block_document.id
        assert result.name == outer_block_document.name
        assert result.block_schema_id == block_schemas[3].id
        assert result.block_type_id == block_schemas[3].block_type_id
        assert result.data == {
            "b": {"x": 1},
            "z": "ztop",
        }
        assert result.block_document_references == {
            "b": {
                "block_document": {
                    "id": inner_block_document.id,
                    "name": inner_block_document.name,
                    "block_type": inner_block_document.block_type,
                    "is_anonymous": False,
                    "block_document_references": {},
                }
            }
        }

    async def test_read_block_by_id_doesnt_exist(self, session):
        assert not await models.block_documents.read_block_document_by_id(
            session=session, block_document_id=uuid4()
        )

    async def test_read_block_by_name(self, session, block_schemas):
        block = await models.block_documents.create_block_document(
            session=session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="x",
                data=dict(),
                block_schema_id=block_schemas[0].id,
                block_type_id=block_schemas[0].block_type_id,
            ),
        )

        result = await models.block_documents.read_block_document_by_name(
            session=session,
            name=block.name,
            block_type_slug=block_schemas[0].block_type.slug,
        )
        assert result.id == block.id
        assert result.name == block.name
        assert result.block_schema_id == block_schemas[0].id

    async def test_read_block_with_nesting_by_name(self, session, block_schemas):
        inner_block_document = await models.block_documents.create_block_document(
            session=session,
            block_document=BlockDocumentCreate(
                name="inner-block-document",
                data=dict(x=1),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
            ),
        )

        outer_block_document = await models.block_documents.create_block_document(
            session=session,
            block_document=BlockDocumentCreate(
                name="outer-block-document",
                data={
                    "b": {"$ref": {"block_document_id": inner_block_document.id}},
                    "z": "ztop",
                },
                block_schema_id=block_schemas[3].id,
                block_type_id=block_schemas[3].block_type_id,
            ),
        )

        result = await models.block_documents.read_block_document_by_name(
            session,
            block_type_slug=block_schemas[3].block_type.slug,
            name=outer_block_document.name,
        )
        assert result.id == outer_block_document.id
        assert result.name == outer_block_document.name
        assert result.block_schema_id == block_schemas[3].id
        assert result.block_type_id == block_schemas[3].block_type_id
        assert result.data == {
            "b": {"x": 1},
            "z": "ztop",
        }
        assert result.block_document_references == {
            "b": {
                "block_document": {
                    "id": inner_block_document.id,
                    "name": inner_block_document.name,
                    "block_type": inner_block_document.block_type,
                    "is_anonymous": False,
                    "block_document_references": {},
                }
            }
        }

    async def test_read_block_by_slug_doesnt_exist(self, session):
        assert not await models.block_documents.read_block_document_by_name(
            session=session, name="x", block_type_slug="not-here"
        )


class TestReadBlockDocuments:
    @pytest.fixture(autouse=True)
    async def block_documents(self, session, block_schemas):

        block_documents = []
        block_documents.append(
            await models.block_documents.create_block_document(
                session=session,
                block_document=schemas.actions.BlockDocumentCreate(
                    block_schema_id=block_schemas[0].id,
                    name="block-1",
                    block_type_id=block_schemas[0].block_type_id,
                ),
            )
        )
        block_documents.append(
            await models.block_documents.create_block_document(
                session=session,
                block_document=schemas.actions.BlockDocumentCreate(
                    block_schema_id=block_schemas[1].id,
                    name="block-2",
                    block_type_id=block_schemas[1].block_type_id,
                    data={"x": 1},
                ),
            )
        )
        block_documents.append(
            await models.block_documents.create_block_document(
                session=session,
                block_document=schemas.actions.BlockDocumentCreate(
                    block_schema_id=block_schemas[2].id,
                    name="block-3",
                    block_type_id=block_schemas[2].block_type_id,
                    data={"y": 2},
                ),
            )
        )
        block_documents.append(
            await models.block_documents.create_block_document(
                session=session,
                block_document=schemas.actions.BlockDocumentCreate(
                    block_schema_id=block_schemas[1].id,
                    name="block-4",
                    block_type_id=block_schemas[1].block_type_id,
                ),
            )
        )
        block_documents.append(
            await models.block_documents.create_block_document(
                session=session,
                block_document=schemas.actions.BlockDocumentCreate(
                    block_schema_id=block_schemas[2].id,
                    name="block-5",
                    block_type_id=block_schemas[2].block_type_id,
                ),
            )
        )
        block_documents.append(
            await models.block_documents.create_block_document(
                session=session,
                block_document=schemas.actions.BlockDocumentCreate(
                    block_schema_id=block_schemas[2].id,
                    block_type_id=block_schemas[2].block_type_id,
                    is_anonymous=True,
                ),
            )
        )

        block_documents.append(
            await models.block_documents.create_block_document(
                session=session,
                block_document=schemas.actions.BlockDocumentCreate(
                    name="nested-block-1",
                    block_schema_id=block_schemas[3].id,
                    block_type_id=block_schemas[3].block_type_id,
                    data={
                        "b": {"$ref": {"block_document_id": block_documents[1].id}},
                        "z": "index",
                    },
                ),
            )
        )

        block_documents.append(
            await models.block_documents.create_block_document(
                session=session,
                block_document=schemas.actions.BlockDocumentCreate(
                    name="nested-block-2",
                    block_schema_id=block_schemas[4].id,
                    block_type_id=block_schemas[4].block_type_id,
                    data={
                        "c": {"$ref": {"block_document_id": block_documents[2].id}},
                        "d": {"$ref": {"block_document_id": block_documents[5].id}},
                    },
                ),
            )
        )

        await session.commit()
        return sorted(block_documents, key=lambda b: b.name)

    async def test_read_block_documents(self, session, block_documents):
        read_blocks = await models.block_documents.read_block_documents(session=session)

        # by default, exclude anonymous block documents
        assert {b.id for b in read_blocks} == {
            b.id for b in block_documents if not b.is_anonymous
        }

        # sorted by block document name
        assert [rb.id for rb in read_blocks] == [
            b.id for b in block_documents if not b.is_anonymous
        ]

    async def test_read_block_documents_with_is_anonymous_filter(
        self, session, block_documents
    ):
        non_anonymous_block_documents = (
            await models.block_documents.read_block_documents(
                session=session,
                block_document_filter=schemas.filters.BlockDocumentFilter(
                    is_anonymous=dict(eq_=False)
                ),
            )
        )

        anonymous_block_documents = await models.block_documents.read_block_documents(
            session=session,
            block_document_filter=schemas.filters.BlockDocumentFilter(
                is_anonymous=dict(eq_=True)
            ),
        )

        all_block_documents = await models.block_documents.read_block_documents(
            session=session,
            block_document_filter=schemas.filters.BlockDocumentFilter(
                is_anonymous=None
            ),
        )

        assert {b.id for b in non_anonymous_block_documents} == {
            b.id for b in block_documents if not b.is_anonymous
        }
        assert {b.id for b in anonymous_block_documents} == {
            b.id for b in block_documents if b.is_anonymous
        }
        assert {b.id for b in all_block_documents} == {b.id for b in block_documents}

    async def test_read_block_documents_limit_offset(self, session, block_documents):
        # sorted by block type name, block name
        read_block_documents = await models.block_documents.read_block_documents(
            session=session, limit=2
        )
        assert [b.id for b in read_block_documents] == [
            block_documents[1].id,
            block_documents[2].id,
        ]
        read_block_documents = await models.block_documents.read_block_documents(
            session=session, limit=2, offset=2
        )
        assert [b.id for b in read_block_documents] == [
            block_documents[3].id,
            block_documents[4].id,
        ]

    async def test_read_block_documents_filter_capabilities(
        self, session, block_documents
    ):
        fly_and_swim_block_documents = (
            await models.block_documents.read_block_documents(
                session=session,
                block_schema_filter=schemas.filters.BlockSchemaFilter(
                    block_capabilities=dict(all_=["fly", "swim"])
                ),
            )
        )
        assert len(fly_and_swim_block_documents) == 1
        assert [b.id for b in fly_and_swim_block_documents] == [block_documents[6].id]

        fly_block_documents = await models.block_documents.read_block_documents(
            session=session,
            block_schema_filter=schemas.filters.BlockSchemaFilter(
                block_capabilities=dict(all_=["fly"])
            ),
        )
        assert len(fly_block_documents) == 3
        assert [b.id for b in fly_block_documents] == [
            block_documents[2].id,
            block_documents[4].id,
            block_documents[6].id,
        ]

        swim_block_documents = await models.block_documents.read_block_documents(
            session=session,
            block_schema_filter=schemas.filters.BlockSchemaFilter(
                block_capabilities=dict(all_=["swim"])
            ),
        )
        assert len(swim_block_documents) == 1
        assert [b.id for b in swim_block_documents] == [block_documents[6].id]


class TestDeleteBlockDocument:
    async def test_delete_block(self, session, block_schemas):
        block = await models.block_documents.create_block_document(
            session=session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="x",
                data=dict(),
                block_schema_id=block_schemas[0].id,
                block_type_id=block_schemas[0].block_type_id,
            ),
        )

        block_document_id = block.id

        await models.block_documents.delete_block_document(
            session=session, block_document_id=block_document_id
        )
        assert not await models.block_documents.read_block_document_by_id(
            session=session, block_document_id=block_document_id
        )

    async def test_delete_nonexistant_block(self, session, block_schemas):
        assert not await models.block_documents.delete_block_document(
            session=session, block_document_id=uuid4()
        )


class TestUpdateBlockDocument:
    async def test_update_block_document_data(self, session, block_schemas):
        block_document = await models.block_documents.create_block_document(
            session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="test-update-data",
                data=dict(x=1),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
            ),
        )

        await models.block_documents.update_block_document(
            session,
            block_document_id=block_document.id,
            block_document=schemas.actions.BlockDocumentUpdate(data=dict(x=2)),
        )

        updated_block_document = await models.block_documents.read_block_document_by_id(
            session, block_document_id=block_document.id
        )
        assert updated_block_document.data == dict(x=2)

    async def test_update_block_document_data_partial(self, session, block_schemas):
        block_document = await models.block_documents.create_block_document(
            session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="test-update-data",
                data=dict(x=1, y=2, z=3),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
            ),
        )

        await models.block_documents.update_block_document(
            session,
            block_document_id=block_document.id,
            block_document=schemas.actions.BlockDocumentUpdate(data=dict(y=99)),
        )

        updated_block_document = await models.block_documents.read_block_document_by_id(
            session, block_document_id=block_document.id
        )
        assert updated_block_document.data == dict(x=1, y=99, z=3)

    async def test_update_anonymous_block_document_data(self, session, block_schemas):
        # ensure that updates work for anonymous blocks
        block_document = await models.block_documents.create_block_document(
            session,
            block_document=schemas.actions.BlockDocumentCreate(
                data=dict(x=1),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
                is_anonymous=True,
            ),
        )

        await models.block_documents.update_block_document(
            session,
            block_document_id=block_document.id,
            block_document=schemas.actions.BlockDocumentUpdate(data=dict(x=2)),
        )

        updated_block_document = await models.block_documents.read_block_document_by_id(
            session, block_document_id=block_document.id
        )
        assert updated_block_document.data == dict(x=2)

    async def test_update_nested_block_document_data(self, session, block_schemas):
        inner_block_document = await models.block_documents.create_block_document(
            session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="test-update-nested-block",
                data=dict(x=1),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
            ),
        )

        outer_block_document = await models.block_documents.create_block_document(
            session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="test-update-nested-block",
                data={
                    "b": {"$ref": {"block_document_id": inner_block_document.id}},
                    "z": "zzzzz",
                },
                block_schema_id=block_schemas[3].id,
                block_type_id=block_schemas[3].block_type_id,
            ),
        )

        block_document_before_update = (
            await models.block_documents.read_block_document_by_id(
                session, block_document_id=outer_block_document.id
            )
        )
        assert block_document_before_update.data == {
            "b": {"x": 1},
            "z": "zzzzz",
        }
        assert block_document_before_update.block_document_references == {
            "b": {
                "block_document": {
                    "id": inner_block_document.id,
                    "name": inner_block_document.name,
                    "block_type": inner_block_document.block_type,
                    "is_anonymous": False,
                    "block_document_references": {},
                }
            }
        }

        await models.block_documents.update_block_document(
            session,
            block_document_id=inner_block_document.id,
            block_document=schemas.actions.BlockDocumentUpdate(data=dict(x=4)),
        )

        block_document_after_update = (
            await models.block_documents.read_block_document_by_id(
                session, block_document_id=outer_block_document.id
            )
        )
        assert block_document_after_update.data == {
            "b": {"x": 4},
            "z": "zzzzz",
        }
        assert block_document_after_update.block_document_references == {
            "b": {
                "block_document": {
                    "id": inner_block_document.id,
                    "name": inner_block_document.name,
                    "block_type": inner_block_document.block_type,
                    "is_anonymous": False,
                    "block_document_references": {},
                }
            }
        }

    async def test_update_nested_block_document_reference(self, session, block_schemas):
        inner_block_document = await models.block_documents.create_block_document(
            session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="test-update-nested-block",
                data=dict(x=1),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
            ),
        )

        outer_block_document = await models.block_documents.create_block_document(
            session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="test-update-nested-block",
                data={
                    "b": {"$ref": {"block_document_id": inner_block_document.id}},
                    "z": "zzzzz",
                },
                block_schema_id=block_schemas[3].id,
                block_type_id=block_schemas[3].block_type_id,
            ),
        )

        block_document_before_update = (
            await models.block_documents.read_block_document_by_id(
                session, block_document_id=outer_block_document.id
            )
        )
        assert block_document_before_update.data == {
            "b": {"x": 1},
            "z": "zzzzz",
        }
        assert block_document_before_update.block_document_references == {
            "b": {
                "block_document": {
                    "id": inner_block_document.id,
                    "name": inner_block_document.name,
                    "block_type": inner_block_document.block_type,
                    "is_anonymous": False,
                    "block_document_references": {},
                }
            }
        }

        new_inner_block_document = await models.block_documents.create_block_document(
            session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="this-is-a-new-inner-block",
                data=dict(x=1000),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
            ),
        )

        await models.block_documents.update_block_document(
            session,
            block_document_id=outer_block_document.id,
            block_document=schemas.actions.BlockDocumentUpdate(
                data={
                    "b": {"$ref": {"block_document_id": new_inner_block_document.id}},
                    "z": "zzzzz",
                }
            ),
        )

        block_document_after_update = (
            await models.block_documents.read_block_document_by_id(
                session, block_document_id=outer_block_document.id
            )
        )
        assert block_document_after_update.data == {
            "b": {
                "x": 1000,
            },
            "z": "zzzzz",
        }
        assert block_document_after_update.block_document_references == {
            "b": {
                "block_document": {
                    "id": new_inner_block_document.id,
                    "name": new_inner_block_document.name,
                    "block_type": new_inner_block_document.block_type,
                    "is_anonymous": False,
                    "block_document_references": {},
                }
            }
        }

    async def test_update_with_faulty_block_document_reference(
        self, session, block_schemas
    ):
        inner_block_document = await models.block_documents.create_block_document(
            session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="test-update-nested-block",
                data=dict(x=1),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
            ),
        )

        outer_block_document = await models.block_documents.create_block_document(
            session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="test-update-nested-block",
                data={
                    "b": {"$ref": {"block_document_id": inner_block_document.id}},
                    "z": "zzzzz",
                },
                block_schema_id=block_schemas[3].id,
                block_type_id=block_schemas[3].block_type_id,
            ),
        )
        with pytest.raises(sa.exc.IntegrityError):
            await models.block_documents.update_block_document(
                session,
                block_document_id=outer_block_document.id,
                block_document=schemas.actions.BlockDocumentUpdate(
                    data={
                        "b": {"$ref": {"block_document_id": uuid4()}},
                        "z": "zzzzz",
                    }
                ),
            )

    async def test_update_with_missing_block_document_reference_id(
        self, session, block_schemas
    ):
        inner_block_document = await models.block_documents.create_block_document(
            session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="test-update-nested-block",
                data=dict(x=1),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
            ),
        )

        outer_block_document = await models.block_documents.create_block_document(
            session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="test-update-nested-block",
                data={
                    "b": {"$ref": {"block_document_id": inner_block_document.id}},
                    "z": "zzzzz",
                },
                block_schema_id=block_schemas[3].id,
                block_type_id=block_schemas[3].block_type_id,
            ),
        )
        with pytest.raises(
            ValueError,
            match="Received block reference without a block_document_id in key b",
        ):
            await models.block_documents.update_block_document(
                session,
                block_document_id=outer_block_document.id,
                block_document=schemas.actions.BlockDocumentUpdate(
                    data={
                        "b": {"$ref": {}},
                        "z": "zzzzz",
                    }
                ),
            )

    async def test_update_only_one_nested_block_document_reference(
        self, session, block_schemas
    ):
        inner_block_document = await models.block_documents.create_block_document(
            session=session,
            block_document=BlockDocumentCreate(
                name="inner-block-document",
                data=dict(x=1),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
            ),
        )

        middle_block_document_1 = await models.block_documents.create_block_document(
            session=session,
            block_document=BlockDocumentCreate(
                name="middle-block-document-1",
                data=dict(y=2),
                block_schema_id=block_schemas[2].id,
                block_type_id=block_schemas[2].block_type_id,
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
                block_schema_id=block_schemas[3].id,
                block_type_id=block_schemas[3].block_type_id,
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
                block_schema_id=block_schemas[4].id,
                block_type_id=block_schemas[4].block_type_id,
            ),
        )

        block_document_before_update = (
            await models.block_documents.read_block_document_by_id(
                session, block_document_id=outer_block_document.id
            )
        )
        assert block_document_before_update.data == {
            "c": {"y": 2},
            "d": {
                "b": {"x": 1},
                "z": "ztop",
            },
        }
        assert block_document_before_update.block_document_references == {
            "c": {
                "block_document": {
                    "id": middle_block_document_1.id,
                    "name": middle_block_document_1.name,
                    "is_anonymous": False,
                    "block_type": middle_block_document_1.block_type,
                    "block_document_references": {},
                },
            },
            "d": {
                "block_document": {
                    "id": middle_block_document_2.id,
                    "name": middle_block_document_2.name,
                    "block_type": middle_block_document_2.block_type,
                    "is_anonymous": False,
                    "block_document_references": {
                        "b": {
                            "block_document": {
                                "id": inner_block_document.id,
                                "name": inner_block_document.name,
                                "block_type": inner_block_document.block_type,
                                "is_anonymous": False,
                                "block_document_references": {},
                            }
                        }
                    },
                }
            },
        }

        new_middle_block_document_1 = (
            await models.block_documents.create_block_document(
                session=session,
                block_document=BlockDocumentCreate(
                    name="new-middle-block-document-1",
                    data=dict(y=2000),
                    block_schema_id=block_schemas[2].id,
                    block_type_id=block_schemas[2].block_type_id,
                ),
            )
        )

        await models.block_documents.update_block_document(
            session,
            block_document_id=outer_block_document.id,
            block_document=schemas.actions.BlockDocumentUpdate(
                data={
                    "c": {
                        "$ref": {"block_document_id": new_middle_block_document_1.id}
                    },
                    "d": {"$ref": {"block_document_id": middle_block_document_2.id}},
                }
            ),
        )

        block_document_after_update = (
            await models.block_documents.read_block_document_by_id(
                session, block_document_id=outer_block_document.id
            )
        )
        assert block_document_after_update.data == {
            "c": {
                "y": 2000,
            },
            "d": {
                "b": {"x": 1},
                "z": "ztop",
            },
        }
        assert block_document_after_update.block_document_references == {
            "c": {
                "block_document": {
                    "id": new_middle_block_document_1.id,
                    "name": new_middle_block_document_1.name,
                    "block_type": new_middle_block_document_1.block_type,
                    "is_anonymous": False,
                    "block_document_references": {},
                },
            },
            "d": {
                "block_document": {
                    "id": middle_block_document_2.id,
                    "name": middle_block_document_2.name,
                    "block_type": middle_block_document_2.block_type,
                    "is_anonymous": False,
                    "block_document_references": {
                        "b": {
                            "block_document": {
                                "id": inner_block_document.id,
                                "name": inner_block_document.name,
                                "block_type": inner_block_document.block_type,
                                "is_anonymous": False,
                                "block_document_references": {},
                            }
                        }
                    },
                }
            },
        }


class TestSecretBlockDocuments:
    @pytest.fixture()
    async def secret_block_type_and_schema(self, session):
        class SecretBlock(Block):
            x: SecretStr
            y: SecretBytes
            z: str

        secret_block_type = await models.block_types.create_block_type(
            session=session, block_type=SecretBlock._to_block_type()
        )
        secret_block_schema = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=SecretBlock._to_block_schema(
                block_type_id=secret_block_type.id
            ),
        )

        await session.commit()
        return secret_block_type, secret_block_schema

    @pytest.fixture()
    async def secret_block_document(self, session, secret_block_type_and_schema):
        secret_block_type, secret_block_schema = secret_block_type_and_schema
        block = await models.block_documents.create_block_document(
            session=session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="secret-block",
                data=dict(x=X, y=Y, z=Z),
                block_type_id=secret_block_type.id,
                block_schema_id=secret_block_schema.id,
            ),
        )
        await session.commit()
        return block

    async def test_create_secret_block_document_obfuscates_results(
        self, session, secret_block_type_and_schema
    ):
        secret_block_type, secret_block_schema = secret_block_type_and_schema
        block = await models.block_documents.create_block_document(
            session=session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="secret-block",
                data=dict(x=X, y=Y, z=Z),
                block_type_id=secret_block_type.id,
                block_schema_id=secret_block_schema.id,
            ),
        )

        assert block.data["x"] == obfuscate_string(X)
        assert block.data["y"] == obfuscate_string(Y)
        assert block.data["z"] == Z

    async def test_read_secret_block_document_by_id_obfuscates_results(
        self, session, secret_block_document
    ):

        block = await models.block_documents.read_block_document_by_id(
            session=session, block_document_id=secret_block_document.id
        )

        assert block.data["x"] == obfuscate_string(X)
        assert block.data["y"] == obfuscate_string(Y)
        assert block.data["z"] == Z

    async def test_read_secret_block_document_by_id_with_secrets(
        self, session, secret_block_document
    ):

        block = await models.block_documents.read_block_document_by_id(
            session=session,
            block_document_id=secret_block_document.id,
            include_secrets=True,
        )

        assert block.data["x"] == X
        assert block.data["y"] == Y
        assert block.data["z"] == Z

    async def test_read_secret_block_document_by_name_obfuscates_results(
        self, session, secret_block_document
    ):

        block = await models.block_documents.read_block_document_by_name(
            session=session,
            name=secret_block_document.name,
            block_type_slug=secret_block_document.block_type.slug,
        )

        assert block.data["x"] == obfuscate_string(X)
        assert block.data["y"] == obfuscate_string(Y)
        assert block.data["z"] == Z

    async def test_read_secret_block_document_by_name_with_secrets(
        self, session, secret_block_document
    ):

        block = await models.block_documents.read_block_document_by_name(
            session=session,
            name=secret_block_document.name,
            block_type_slug=secret_block_document.block_type.slug,
            include_secrets=True,
        )

        assert block.data["x"] == X
        assert block.data["y"] == Y
        assert block.data["z"] == Z

    async def test_read_secret_block_documents_obfuscates_results(
        self, session, secret_block_document
    ):

        blocks = await models.block_documents.read_block_documents(
            session=session,
            block_document_filter=schemas.filters.BlockDocumentFilter(
                block_type_id=dict(any_=[secret_block_document.block_type_id])
            ),
        )
        assert len(blocks) == 1
        assert blocks[0].data["x"] == obfuscate_string(X)
        assert blocks[0].data["y"] == obfuscate_string(Y)
        assert blocks[0].data["z"] == Z

    async def test_read_secret_block_documents_with_secrets(
        self, session, secret_block_document
    ):

        blocks = await models.block_documents.read_block_documents(
            session=session,
            block_document_filter=schemas.filters.BlockDocumentFilter(
                block_type_id=dict(any_=[secret_block_document.block_type_id])
            ),
            include_secrets=True,
        )
        assert len(blocks) == 1
        assert blocks[0].data["x"] == X
        assert blocks[0].data["y"] == Y
        assert blocks[0].data["z"] == Z

    async def test_updating_secret_block_document_with_obfuscated_result_is_ignored(
        self, session, secret_block_document
    ):

        block = await models.block_documents.read_block_document_by_id(
            session=session,
            block_document_id=secret_block_document.id,
            include_secrets=False,
        )

        assert block.data["x"] == obfuscate_string(X)

        # set X to the secret value
        await models.block_documents.update_block_document(
            session=session,
            block_document_id=secret_block_document.id,
            block_document=schemas.actions.BlockDocumentUpdate(
                data=dict(x=obfuscate_string(X))
            ),
        )

        block2 = await models.block_documents.read_block_document_by_id(
            session=session,
            block_document_id=secret_block_document.id,
            include_secrets=True,
        )

        # x was NOT overwritten
        assert block2.data["x"] != obfuscate_string(X)

    async def test_block_with_list_of_secrets(self, session):
        class ListSecretBlock(Block):
            x: List[SecretStr]

        # save the block
        orig_block = ListSecretBlock(x=["a", "b"])
        await orig_block.save(name="list-secret")

        # load the block
        block = await ListSecretBlock.load("list-secret")

        assert block.x[0].get_secret_value() == "a"
        assert block.x[1].get_secret_value() == "b"
