from uuid import uuid4

import pytest
import sqlalchemy as sa

from prefect.blocks.core import Block
from prefect.orion import models, schemas
from prefect.orion.schemas.actions import BlockDocumentCreate


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

        assert result.name.startswith("anonymous:")
        assert result.data == dict(y=1)
        assert result.block_schema_id == block_schemas[0].id
        assert result.block_schema.checksum == block_schemas[0].checksum
        assert result.is_anonymous is True

        db_block_document = await models.block_documents.read_block_document_by_id(
            session=session, block_document_id=result.id
        )
        assert db_block_document.id == result.id

    async def test_create_anonymous_block_document_errors_if_name_provided(
        self, session, block_schemas
    ):
        with pytest.raises(
            ValueError,
            match="(Names cannot be provided for anonymous block documents.)",
        ):
            schemas.actions.BlockDocumentCreate(
                name="test-name",
                data=dict(y=1),
                block_schema_id=block_schemas[0].id,
                block_type_id=block_schemas[0].block_type_id,
                is_anonymous=True,
            )

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

    async def test_create_anonymous_block_document_creates_deterministic_name(
        self, session, block_schemas
    ):
        block_document = schemas.actions.BlockDocumentCreate(
            data=dict(y=1),
            block_schema_id=block_schemas[0].id,
            block_type_id=block_schemas[0].block_type_id,
            is_anonymous=True,
        )
        result = await models.block_documents.create_block_document(
            session=session, block_document=block_document
        )

        anonymous_name = models.block_documents.generate_anonymous_name_from_fields(
            data=block_document.data,
            block_schema_id=block_document.block_schema_id,
            block_type_id=block_document.block_type_id,
        )
        assert result.name == anonymous_name

    async def test_named_blocks_have_unique_names(self, session, block_schemas, db):
        block_document = schemas.actions.BlockDocumentCreate(
            name="test-block",
            data=dict(y=1),
            block_schema_id=block_schemas[0].id,
            block_type_id=block_schemas[0].block_type_id,
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

    async def test_anonymous_blocks_are_idempotent(self, session, block_schemas, db):
        block_document = schemas.actions.BlockDocumentCreate(
            # name="hi",
            data=dict(y=1),
            block_schema_id=block_schemas[0].id,
            block_type_id=block_schemas[0].block_type_id,
            is_anonymous=True,
        )

        before_count = await session.execute(
            sa.select(sa.func.count()).select_from(db.BlockDocument)
        )
        # create the same block document twice
        result1 = await models.block_documents.create_block_document(
            session=session, block_document=block_document
        )
        await session.commit()
        result2 = await models.block_documents.create_block_document(
            session=session, block_document=block_document
        )
        await session.commit()
        after_count = await session.execute(
            sa.select(sa.func.count()).select_from(db.BlockDocument)
        )

        # only one block created
        assert result1.id == result2.id
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
                    "block_document_references": {},
                }
            }
        }

    async def test_create_multiply_nested_block_document(self, session, block_schemas):
        inner_block_document = await models.block_documents.create_block_document(
            session=session,
            block_document=BlockDocumentCreate(
                name="inner_block_document",
                data=dict(x=1),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
            ),
        )

        middle_block_document_1 = await models.block_documents.create_block_document(
            session=session,
            block_document=BlockDocumentCreate(
                name="middle_block_document_1",
                data=dict(y=2),
                block_schema_id=block_schemas[2].id,
                block_type_id=block_schemas[2].block_type_id,
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
                block_schema_id=block_schemas[3].id,
                block_type_id=block_schemas[3].block_type_id,
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
                    "block_document_references": {},
                },
            },
            "d": {
                "block_document": {
                    "id": middle_block_document_2.id,
                    "name": middle_block_document_2.name,
                    "block_type": middle_block_document_2.block_type,
                    "block_document_references": {
                        "b": {
                            "block_document": {
                                "id": inner_block_document.id,
                                "name": inner_block_document.name,
                                "block_type": inner_block_document.block_type,
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
                    "block_document_references": {},
                },
            },
            "d": {
                "block_document": {
                    "id": middle_block_document_2.id,
                    "name": middle_block_document_2.name,
                    "block_type": middle_block_document_2.block_type,
                    "block_document_references": {
                        "b": {
                            "block_document": {
                                "id": inner_block_document.id,
                                "name": inner_block_document.name,
                                "block_type": inner_block_document.block_type,
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
                name="inner_block_document",
                data=dict(x=1),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
            ),
        )

        outer_block_document = await models.block_documents.create_block_document(
            session=session,
            block_document=BlockDocumentCreate(
                name="outer_block_document",
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
            block_type_name=block_schemas[0].block_type.name,
        )
        assert result.id == block.id
        assert result.name == block.name
        assert result.block_schema_id == block_schemas[0].id

    async def test_read_block_with_nesting_by_name(self, session, block_schemas):
        inner_block_document = await models.block_documents.create_block_document(
            session=session,
            block_document=BlockDocumentCreate(
                name="inner_block_document",
                data=dict(x=1),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
            ),
        )

        outer_block_document = await models.block_documents.create_block_document(
            session=session,
            block_document=BlockDocumentCreate(
                name="outer_block_document",
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
            block_type_name=block_schemas[3].block_type.name,
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
                    "block_document_references": {},
                }
            }
        }

    async def test_read_block_by_name_doesnt_exist(self, session):
        assert not await models.block_documents.read_block_document_by_name(
            session=session, name="x", block_type_name="not-here"
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
                    name="Block 1",
                    block_type_id=block_schemas[0].block_type_id,
                ),
            )
        )
        block_documents.append(
            await models.block_documents.create_block_document(
                session=session,
                block_document=schemas.actions.BlockDocumentCreate(
                    block_schema_id=block_schemas[1].id,
                    name="Block 2",
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
                    name="Block 3",
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
                    name="Block 4",
                    block_type_id=block_schemas[1].block_type_id,
                ),
            )
        )
        block_documents.append(
            await models.block_documents.create_block_document(
                session=session,
                block_document=schemas.actions.BlockDocumentCreate(
                    block_schema_id=block_schemas[2].id,
                    name="Block 5",
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
                    name="Nested Block 1",
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
                    name="Nested Block 2",
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

        # sorted by block type name, block document name
        assert read_blocks == [b for b in block_documents if not b.is_anonymous]

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
            block_documents[0].id,
            block_documents[1].id,
        ]
        read_block_documents = await models.block_documents.read_block_documents(
            session=session, limit=2, offset=2
        )
        assert [b.id for b in read_block_documents] == [
            block_documents[2].id,
            block_documents[3].id,
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
        assert fly_and_swim_block_documents == [block_documents[5]]

        fly_block_documents = await models.block_documents.read_block_documents(
            session=session,
            block_schema_filter=schemas.filters.BlockSchemaFilter(
                block_capabilities=dict(all_=["fly"])
            ),
        )
        assert len(fly_block_documents) == 3
        assert fly_block_documents == [
            block_documents[1],
            block_documents[3],
            block_documents[5],
        ]

        swim_block_documents = await models.block_documents.read_block_documents(
            session=session,
            block_schema_filter=schemas.filters.BlockSchemaFilter(
                block_capabilities=dict(all_=["swim"])
            ),
        )
        assert len(swim_block_documents) == 1
        assert swim_block_documents == [block_documents[5]]


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


class TestDefaultStorage:
    @pytest.fixture
    async def storage_block_schema(self, session, block_type_x):
        storage_block_schema = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.actions.BlockSchemaCreate(
                block_type_id=block_type_x.id, fields={}, capabilities=["storage"]
            ),
        )
        await session.commit()
        return storage_block_schema

    @pytest.fixture
    async def storage_block(self, session, storage_block_schema):
        block = await models.block_documents.create_block_document(
            session=session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="storage",
                data=dict(),
                block_schema_id=storage_block_schema.id,
                block_type_id=storage_block_schema.block_type_id,
            ),
        )
        await session.commit()
        return block

    async def test_set_default_storage_block_document(self, session, storage_block):
        assert not await models.block_documents.get_default_storage_block_document(
            session=session
        )

        await models.block_documents.set_default_storage_block_document(
            session=session, block_document_id=storage_block.id
        )

        result = await models.block_documents.get_default_storage_block_document(
            session=session
        )
        assert result.id == storage_block.id

    async def test_set_default_fails_if_not_storage_block(self, session, block_schemas):
        non_storage_block = await models.block_documents.create_block_document(
            session=session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="non-storage",
                data=dict(),
                block_schema_id=block_schemas[0].id,
                block_type_id=block_schemas[0].block_type_id,
            ),
        )
        await session.commit()

        with pytest.raises(
            ValueError, match="Block schema must have the 'storage' capability"
        ):
            await models.block_documents.set_default_storage_block_document(
                session=session, block_document_id=non_storage_block.id
            )
        assert not await models.block_documents.get_default_storage_block_document(
            session=session
        )

    async def test_clear_default_storage_block_document(self, session, storage_block):

        await models.block_documents.set_default_storage_block_document(
            session=session, block_document_id=storage_block.id
        )
        result = await models.block_documents.get_default_storage_block_document(
            session=session
        )
        assert result.id == storage_block.id

        await models.block_documents.clear_default_storage_block_document(
            session=session
        )

        assert not await models.block_documents.get_default_storage_block_document(
            session=session
        )

    async def test_set_default_storage_block_clears_old_block(
        self, session, storage_block, storage_block_schema, db
    ):
        storage_block_2 = await models.block_documents.create_block_document(
            session=session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="storage-2",
                data=dict(),
                block_schema_id=storage_block_schema.id,
                block_type_id=storage_block_schema.block_type_id,
            ),
        )
        await session.commit()

        await models.block_documents.set_default_storage_block_document(
            session=session, block_document_id=storage_block.id
        )

        result = await session.execute(
            sa.select(db.BlockDocument).where(
                db.BlockDocument.is_default_storage_block_document.is_(True)
            )
        )
        default_blocks = result.scalars().unique().all()
        assert len(default_blocks) == 1
        assert default_blocks[0].id == storage_block.id

        await models.block_documents.set_default_storage_block_document(
            session=session, block_document_id=storage_block_2.id
        )

        result = await session.execute(
            sa.select(db.BlockDocument).where(
                db.BlockDocument.is_default_storage_block_document.is_(True)
            )
        )
        default_blocks = result.scalars().unique().all()
        assert len(default_blocks) == 1
        assert default_blocks[0].id == storage_block_2.id


class TestUpdateBlockDocument:
    async def test_update_block_document_name(self, session, block_schemas):
        block_document = await models.block_documents.create_block_document(
            session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="test-update-name",
                data=dict(x=1),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
            ),
        )

        await models.block_documents.update_block_document(
            session,
            block_document_id=block_document.id,
            block_document=schemas.actions.BlockDocumentUpdate(name="updated"),
        )

        updated_block_document = await models.block_documents.read_block_document_by_id(
            session, block_document_id=block_document.id
        )
        assert updated_block_document.name == "updated"

    async def test_update_block_document_name_fails_for_anonymous_blocks(
        self, session, block_schemas
    ):
        block_document = await models.block_documents.create_block_document(
            session,
            block_document=schemas.actions.BlockDocumentCreate(
                data=dict(x=1),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
                is_anonymous=True,
            ),
        )

        with pytest.raises(
            ValueError, match="(Names cannot be provided for anonymous blocks.)"
        ):
            await models.block_documents.update_block_document(
                session,
                block_document_id=block_document.id,
                block_document=schemas.actions.BlockDocumentUpdate(name="updated"),
            )

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

    async def test_update_anonymous_block_document_data_changes_name(
        self, session, block_schemas
    ):

        block_document = await models.block_documents.create_block_document(
            session,
            block_document=schemas.actions.BlockDocumentCreate(
                data=dict(x=1),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
                is_anonymous=True,
            ),
        )

        assert block_document.name.startswith("anonymous:")

        await models.block_documents.update_block_document(
            session,
            block_document_id=block_document.id,
            block_document=schemas.actions.BlockDocumentUpdate(data=dict(x=2)),
        )

        updated_block_document = await models.block_documents.read_block_document_by_id(
            session, block_document_id=block_document.id
        )

        # name was updated

        expected_anonymous_name = (
            models.block_documents.generate_anonymous_name_from_fields(
                data=dict(x=2),
                block_schema_id=block_document.block_schema_id,
                block_type_id=block_document.block_type_id,
            )
        )
        assert updated_block_document.name == expected_anonymous_name
        assert updated_block_document.name.startswith("anonymous:")
        assert updated_block_document.name != block_document.name

    async def test_update_anonymous_block_document_data_doesnt_change_name_if_data_doesnt_change(
        self, session, block_schemas
    ):

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
            # note the new data is the same as the old data
            block_document=schemas.actions.BlockDocumentUpdate(data=dict(x=1)),
        )

        updated_block_document = await models.block_documents.read_block_document_by_id(
            session, block_document_id=block_document.id
        )

        # name was not updated
        assert updated_block_document.name == block_document.name

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
                name="inner_block_document",
                data=dict(x=1),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
            ),
        )

        middle_block_document_1 = await models.block_documents.create_block_document(
            session=session,
            block_document=BlockDocumentCreate(
                name="middle_block_document_1",
                data=dict(y=2),
                block_schema_id=block_schemas[2].id,
                block_type_id=block_schemas[2].block_type_id,
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
                block_schema_id=block_schemas[3].id,
                block_type_id=block_schemas[3].block_type_id,
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
                    "block_type": middle_block_document_1.block_type,
                    "block_document_references": {},
                },
            },
            "d": {
                "block_document": {
                    "id": middle_block_document_2.id,
                    "name": middle_block_document_2.name,
                    "block_type": middle_block_document_2.block_type,
                    "block_document_references": {
                        "b": {
                            "block_document": {
                                "id": inner_block_document.id,
                                "name": inner_block_document.name,
                                "block_type": inner_block_document.block_type,
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
                    name="new_middle_block_document_1",
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
                    "block_document_references": {},
                },
            },
            "d": {
                "block_document": {
                    "id": middle_block_document_2.id,
                    "name": middle_block_document_2.name,
                    "block_type": middle_block_document_2.block_type,
                    "block_document_references": {
                        "b": {
                            "block_document": {
                                "id": inner_block_document.id,
                                "name": inner_block_document.name,
                                "block_type": inner_block_document.block_type,
                                "block_document_references": {},
                            }
                        }
                    },
                }
            },
        }
