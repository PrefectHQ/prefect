"""
Functions for interacting with block document ORM objects.
Intended for internal use by the Orion API.
"""
from typing import Optional
from uuid import UUID

import sqlalchemy as sa

from prefect.orion import schemas
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface


@inject_db
async def create_block_document(
    session: sa.orm.Session,
    block_document: schemas.actions.BlockDocumentCreate,
    db: OrionDBInterface,
):

    orm_block = db.BlockDocument(
        name=block_document.name,
        block_schema_id=block_document.block_schema_id,
        block_type_id=block_document.block_type_id,
    )

    # encrypt the data and store in block document
    await orm_block.encrypt_data(session=session, data=block_document.data)

    # add the block document to the session and flush
    session.add(orm_block)
    await session.flush()

    # reload the block document in order to load the associated block schema relationship
    return await read_block_document_by_id(
        session=session, block_document_id=orm_block.id
    )


@inject_db
async def read_block_document_by_id(
    session: sa.orm.Session,
    block_document_id: UUID,
    db: OrionDBInterface,
):
    query = (
        sa.select(db.BlockDocument)
        .where(db.BlockDocument.id == block_document_id)
        .execution_options(populate_existing=True)
    )

    result = await session.execute(query)
    block_document = result.scalar()
    return block_document


@inject_db
async def read_block_document_by_name(
    session: sa.orm.Session,
    name: str,
    block_type_name: str,
    db: OrionDBInterface,
    block_schema_checksum: Optional[str] = None,
):
    """
    Read a block document with the given name and block type name. If a block schema checksum
    is provided, it is matched as well.
    """
    where_clause = [
        db.BlockDocument.name == name,
        db.BlockType.name == block_type_name,
    ]

    if block_schema_checksum is not None:
        where_clause.append(db.BlockSchema.checksum == block_schema_checksum)

    query = (
        sa.select(db.BlockDocument)
        .join(db.BlockSchema, db.BlockSchema.id == db.BlockDocument.block_schema_id)
        .join(db.BlockType, db.BlockType.id == db.BlockDocument.block_type_id)
        .where(sa.and_(*where_clause))
        .order_by(db.BlockDocument.created.desc())
        .limit(1)
    )
    result = await session.execute(query)
    block_document = result.scalar()
    return block_document


@inject_db
async def read_block_documents(
    session: sa.orm.Session,
    db: OrionDBInterface,
    block_type_id: Optional[UUID] = None,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
):
    """
    Read block documents with an optional limit and offset
    """

    query = (
        sa.select(db.BlockDocument)
        .join(db.BlockSchema, db.BlockSchema.id == db.BlockDocument.block_schema_id)
        .join(db.BlockType, db.BlockType.id == db.BlockDocument.block_type_id)
        .order_by(db.BlockType.name, db.BlockDocument.name)
    )

    if block_type_id is not None:
        query = query.where(db.BlockDocument.block_type_id == block_type_id)

    if offset is not None:
        query = query.offset(offset)

    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


@inject_db
async def delete_block_document(
    session: sa.orm.Session,
    block_document_id: UUID,
    db: OrionDBInterface,
) -> bool:

    query = sa.delete(db.BlockDocument).where(db.BlockDocument.id == block_document_id)
    result = await session.execute(query)
    return result.rowcount > 0


@inject_db
async def update_block_document(
    session: sa.orm.Session,
    block_document_id: UUID,
    block_document: schemas.actions.BlockDocumentUpdate,
    db: OrionDBInterface,
) -> bool:

    block_document = await session.get(db.BlockDocument, block_document_id)
    if not block_document:
        return False

    update_values = block_document.dict(shallow=True, exclude_unset=True)
    if "data" in update_values:
        block_document.encrypt_data(session=session, data=update_values["data"])
    if "name" in update_values:
        block_document.name = update_values["name"]

    await session.flush()

    return True


@inject_db
async def get_default_storage_block_document(
    session: sa.orm.Session, db: OrionDBInterface
):
    query = (
        sa.select(db.BlockDocument)
        .where(db.BlockDocument.is_default_storage_block_document.is_(True))
        .limit(1)
        .execution_options(populate_existing=True)
    )
    result = await session.execute(query)
    block = result.scalar()
    return block


@inject_db
async def set_default_storage_block_document(
    session: sa.orm.Session, block_document_id: UUID, db: OrionDBInterface
):
    block_document = await read_block_document_by_id(
        session=session, block_document_id=block_document_id
    )
    if not block_document:
        raise ValueError("Block document not found")
    elif "storage" not in block_document.block_schema.capabilities:
        raise ValueError("Block schema must have the 'storage' capability")

    await clear_default_storage_block_document(session=session)
    block_document.is_default_storage_block_document = True
    await session.flush()


@inject_db
async def clear_default_storage_block_document(
    session: sa.orm.Session, db: OrionDBInterface
):
    await session.execute(
        sa.update(db.BlockDocument)
        .where(db.BlockDocument.is_default_storage_block_document.is_(True))
        .values(is_default_storage_block_document=False)
    )
    await session.flush()
