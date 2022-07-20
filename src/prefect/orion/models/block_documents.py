"""
Functions for interacting with block document ORM objects.
Intended for internal use by the Orion API.
"""
from typing import Dict, List, Optional, Tuple
from uuid import UUID, uuid4

import sqlalchemy as sa

from prefect.orion import schemas
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.database.orm_models import ORMBlockDocument
from prefect.orion.schemas.actions import BlockDocumentReferenceCreate
from prefect.orion.schemas.core import (
    OBFUSCATED_SECRET,
    BlockDocument,
    BlockDocumentReference,
)
from prefect.orion.schemas.filters import BlockDocumentFilterIsAnonymous


@inject_db
async def create_block_document(
    session: sa.orm.Session,
    block_document: schemas.actions.BlockDocumentCreate,
    db: OrionDBInterface,
):

    # anonymous block documents can be given a random name if none is provided
    if block_document.is_anonymous and not block_document.name:
        name = f"anonymous:{uuid4()}"
    else:
        name = block_document.name

    orm_block = db.BlockDocument(
        name=name,
        block_schema_id=block_document.block_schema_id,
        block_type_id=block_document.block_type_id,
        is_anonymous=block_document.is_anonymous,
    )

    (
        block_document_data_without_refs,
        block_document_references,
    ) = _separate_block_references_from_data(block_document.data)

    # encrypt the data and store in block document
    await orm_block.encrypt_data(session=session, data=block_document_data_without_refs)

    session.add(orm_block)
    await session.flush()

    # Create a block document reference for each reference in the block document data
    for key, reference_block_document_id in block_document_references:
        await create_block_document_reference(
            session=session,
            block_document_reference=BlockDocumentReferenceCreate(
                parent_block_document_id=orm_block.id,
                reference_block_document_id=reference_block_document_id,
                name=key,
            ),
        )

    # reload the block document in order to load the associated block schema relationship
    return await read_block_document_by_id(
        session=session,
        block_document_id=orm_block.id,
        include_secrets=False,
    )


def _separate_block_references_from_data(
    block_document_data: Dict,
) -> Tuple[Dict, List[Tuple[str, UUID]]]:
    """
    Separates block document references from block document data so that a block
    document can be saved without references and the corresponding block document
    references can be saved.

    Args:
        block_document_data: Dictionary of block document data passed with request
            to create new block document

    Returns:
        block_document_data_with_out_refs: A copy of the block_document_data supplied
            with the block document references removed.
        block_document_references: A list of tuples each containing the name of the
            field referencing a block document and the ID of the referenced block
            document,
    """
    block_document_references = []
    block_document_data_without_refs = {}
    for key, value in block_document_data.items():
        # Current assumption is that any block references will be stored on a key of
        # the block document data and not nested in any other data structures.
        if isinstance(value, dict) and "$ref" in value:
            reference_block_document_id = value["$ref"].get("block_document_id")
            if reference_block_document_id is None:
                raise ValueError(
                    f"Received block reference without a block_document_id in key {key}"
                )
            block_document_references.append((key, reference_block_document_id))
        else:
            block_document_data_without_refs[key] = value
    return block_document_data_without_refs, block_document_references


@inject_db
async def read_block_document_by_id(
    session: sa.orm.Session,
    block_document_id: UUID,
    db: OrionDBInterface,
    include_secrets: bool = False,
):
    block_document_references_query = (
        sa.select(db.BlockDocumentReference)
        .filter_by(parent_block_document_id=block_document_id)
        .cte("block_document_references", recursive=True)
    )
    block_document_references_join = sa.select(db.BlockDocumentReference).join(
        block_document_references_query,
        db.BlockDocumentReference.parent_block_document_id
        == block_document_references_query.c.reference_block_document_id,
    )
    recursive_block_document_references_cte = block_document_references_query.union_all(
        block_document_references_join
    )
    nested_block_documents_query = (
        sa.select(
            [
                db.BlockDocument,
                recursive_block_document_references_cte.c.name,
                recursive_block_document_references_cte.c.parent_block_document_id,
            ]
        )
        .select_from(db.BlockDocument)
        .join(
            recursive_block_document_references_cte,
            db.BlockDocument.id
            == recursive_block_document_references_cte.c.reference_block_document_id,
            isouter=True,
        )
        .filter(
            sa.or_(
                db.BlockDocument.id == block_document_id,
                recursive_block_document_references_cte.c.parent_block_document_id.is_not(
                    None
                ),
            )
        )
        .execution_options(populate_existing=True)
    )

    result = await session.execute(nested_block_documents_query)
    return await _construct_full_block_document(
        session, result.all(), include_secrets=include_secrets
    )


async def _construct_full_block_document(
    session: sa.orm.Session,
    block_documents_with_references: List[
        Tuple[ORMBlockDocument, Optional[str], Optional[UUID]]
    ],
    parent_block_document: Optional[BlockDocument] = None,
    include_secrets: bool = False,
) -> Optional[BlockDocument]:
    if len(block_documents_with_references) == 0:
        return None
    if parent_block_document is None:
        parent_block_document = await _find_parent_block_document(
            session, block_documents_with_references, include_secrets=include_secrets
        )

    if parent_block_document is None:
        raise ValueError("Unable to determine parent block document")

    # Recursively walk block document tree and construct the full block
    # document data for each child and add it to the parent's block document
    # data
    for (
        orm_block_document,
        name,
        parent_block_document_id,
    ) in block_documents_with_references:
        if parent_block_document_id == parent_block_document.id and name != None:
            block_document = await BlockDocument.from_orm_model(
                session, orm_block_document, include_secrets=include_secrets
            )
            full_child_block_document = await _construct_full_block_document(
                session,
                block_documents_with_references,
                parent_block_document=block_document,
                include_secrets=include_secrets,
            )
            parent_block_document.data[name] = full_child_block_document.data
            parent_block_document.block_document_references[name] = {
                "block_document": {
                    "id": block_document.id,
                    "name": block_document.name,
                    "block_type": block_document.block_type,
                    "is_anonymous": block_document.is_anonymous,
                    "block_document_references": full_child_block_document.block_document_references,
                }
            }

    return parent_block_document


async def _find_parent_block_document(
    session, block_documents_with_references, include_secrets: bool = False
):
    parent_orm_block_document = next(
        (
            block_document
            for (
                block_document,
                _,
                parent_block_document_id,
            ) in block_documents_with_references
            if parent_block_document_id is None
        ),
        None,
    )
    return (
        await BlockDocument.from_orm_model(
            session,
            parent_orm_block_document,
            include_secrets=include_secrets,
        )
        if parent_orm_block_document is not None
        else None
    )


@inject_db
async def read_block_document_by_name(
    session: sa.orm.Session,
    name: str,
    block_type_name: str,
    db: OrionDBInterface,
    include_secrets: bool = False,
):
    """
    Read a block document with the given name and block type name. If a block schema checksum
    is provided, it is matched as well.
    """
    root_block_document_cte = (
        sa.select(db.BlockDocument)
        .join(db.BlockType, db.BlockType.id == db.BlockDocument.block_type_id)
        .filter(db.BlockType.name == block_type_name, db.BlockDocument.name == name)
        .cte("root_block_document")
    )

    block_document_references_query = (
        sa.select(db.BlockDocumentReference)
        .filter_by(parent_block_document_id=root_block_document_cte.c.id)
        .cte("block_document_references", recursive=True)
    )
    block_document_references_join = sa.select(db.BlockDocumentReference).join(
        block_document_references_query,
        db.BlockDocumentReference.parent_block_document_id
        == block_document_references_query.c.reference_block_document_id,
    )
    recursive_block_document_references_cte = block_document_references_query.union_all(
        block_document_references_join
    )
    nested_block_documents_query = (
        sa.select(
            [
                db.BlockDocument,
                recursive_block_document_references_cte.c.name,
                recursive_block_document_references_cte.c.parent_block_document_id,
            ]
        )
        .select_from(db.BlockDocument)
        .join(
            recursive_block_document_references_cte,
            db.BlockDocument.id
            == recursive_block_document_references_cte.c.reference_block_document_id,
            isouter=True,
        )
        .filter(
            sa.or_(
                db.BlockDocument.id == root_block_document_cte.c.id,
                recursive_block_document_references_cte.c.parent_block_document_id.is_not(
                    None
                ),
            )
        )
        .execution_options(populate_existing=True)
    )

    result = await session.execute(nested_block_documents_query)
    return await _construct_full_block_document(
        session, result.all(), include_secrets=include_secrets
    )


@inject_db
async def read_block_documents(
    session: sa.orm.Session,
    db: OrionDBInterface,
    block_document_filter: Optional[schemas.filters.BlockDocumentFilter] = None,
    block_schema_filter: Optional[schemas.filters.BlockSchemaFilter] = None,
    include_secrets: bool = False,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
):
    """
    Read block documents with an optional limit and offset
    """
    # if no filter is provided, one is created that excludes anonymous blocks
    if block_document_filter is None:
        block_document_filter = schemas.filters.BlockDocumentFilter(
            is_anonymous=BlockDocumentFilterIsAnonymous(eq_=False)
        )

    filtered_block_documents_query = sa.select(db.BlockDocument.id).order_by(
        db.BlockDocument.name
    )

    filtered_block_documents_query = filtered_block_documents_query.where(
        block_document_filter.as_sql_filter(db)
    )

    if block_schema_filter is not None:
        exists_clause = sa.select(db.BlockSchema).where(
            db.BlockSchema.id == db.BlockDocument.block_schema_id,
            block_schema_filter.as_sql_filter(db),
        )
        filtered_block_documents_query = filtered_block_documents_query.where(
            exists_clause.exists()
        )

    if offset is not None:
        filtered_block_documents_query = filtered_block_documents_query.offset(offset)

    if limit is not None:
        filtered_block_documents_query = filtered_block_documents_query.limit(limit)

    filtered_block_document_ids = (
        (await session.execute(filtered_block_documents_query)).scalars().unique().all()
    )

    block_document_references_query = (
        sa.select(db.BlockDocumentReference)
        .filter(
            db.BlockDocumentReference.parent_block_document_id.in_(
                filtered_block_document_ids
            )
        )
        .cte("block_document_references", recursive=True)
    )
    block_document_references_join = sa.select(db.BlockDocumentReference).join(
        block_document_references_query,
        db.BlockDocumentReference.parent_block_document_id
        == block_document_references_query.c.reference_block_document_id,
    )
    recursive_block_document_references_cte = block_document_references_query.union_all(
        block_document_references_join
    )
    nested_block_documents_query = (
        sa.select(
            [
                db.BlockDocument,
                recursive_block_document_references_cte.c.name,
                recursive_block_document_references_cte.c.parent_block_document_id,
            ]
        )
        .select_from(db.BlockDocument)
        .join(
            recursive_block_document_references_cte,
            db.BlockDocument.id
            == recursive_block_document_references_cte.c.reference_block_document_id,
            isouter=True,
        )
        .filter(
            sa.or_(
                db.BlockDocument.id.in_(filtered_block_document_ids),
                recursive_block_document_references_cte.c.parent_block_document_id.is_not(
                    None
                ),
            )
        )
        .order_by(db.BlockDocument.name)
        .execution_options(populate_existing=True)
    )

    block_documents_with_references = (
        (await session.execute(nested_block_documents_query)).unique().all()
    )
    fully_constructed_block_documents = []
    visited_block_document_ids = []
    for root_orm_block_document, _, _ in block_documents_with_references:
        if (
            root_orm_block_document.id in filtered_block_document_ids
            and root_orm_block_document.id not in visited_block_document_ids
        ):
            root_block_document = await BlockDocument.from_orm_model(
                session, root_orm_block_document, include_secrets=include_secrets
            )
            fully_constructed_block_documents.append(
                await _construct_full_block_document(
                    session,
                    block_documents_with_references,
                    root_block_document,
                    include_secrets=include_secrets,
                )
            )
            visited_block_document_ids.append(root_orm_block_document.id)
    return fully_constructed_block_documents


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

    current_block_document = await session.get(db.BlockDocument, block_document_id)
    if not current_block_document:
        return False

    update_values = block_document.dict(shallow=True, exclude_unset=True)

    if "name" in update_values:
        current_block_document.name = update_values["name"]

    if "data" in update_values and update_values["data"] is not None:

        # if a block data contains Prefect's own OBFUSCATED SECRET value,
        # it means someone is probably trying to update all of the documents
        # fields without realizing they are positing back obfuscated data,
        # so we disregard them
        for key, value in list(update_values["data"].items()):
            if value == OBFUSCATED_SECRET:
                del update_values["data"][key]

        # merge the existing data and the new data for partial updates
        merged_data = await current_block_document.decrypt_data(session=session)
        merged_data.update(update_values["data"])
        update_values["data"] = merged_data

        current_block_document_references = (
            (
                await session.execute(
                    sa.select(db.BlockDocumentReference).filter_by(
                        parent_block_document_id=block_document_id
                    )
                )
            )
            .scalars()
            .all()
        )
        (
            block_document_data_without_refs,
            new_block_document_references,
        ) = _separate_block_references_from_data(update_values["data"])

        # encrypt the data
        await current_block_document.encrypt_data(
            session=session, data=block_document_data_without_refs
        )

        unchanged_block_document_references = []
        for key, reference_block_document_id in new_block_document_references:
            matching_current_block_document_reference = _find_block_document_reference(
                current_block_document_references, key, reference_block_document_id
            )
            if matching_current_block_document_reference is None:
                await create_block_document_reference(
                    session=session,
                    block_document_reference=BlockDocumentReferenceCreate(
                        parent_block_document_id=block_document_id,
                        reference_block_document_id=reference_block_document_id,
                        name=key,
                    ),
                )
            else:
                unchanged_block_document_references.append(
                    matching_current_block_document_reference
                )

        for block_document_reference in current_block_document_references:
            if block_document_reference not in unchanged_block_document_references:
                await delete_block_document_reference(
                    session, block_document_reference_id=block_document_reference.id
                )

    await session.flush()

    return True


def _find_block_document_reference(
    block_document_references: List[BlockDocumentReference],
    name: str,
    reference_block_document_id: UUID,
) -> Optional[BlockDocumentReference]:
    return next(
        (
            block_document_reference
            for block_document_reference in block_document_references
            if block_document_reference.name == name
            and block_document_reference.reference_block_document_id
            == reference_block_document_id
        ),
        None,
    )


@inject_db
async def get_default_storage_block_document(
    session: sa.orm.Session,
    db: OrionDBInterface,
    include_secrets: bool = True,
):
    query = (
        sa.select(db.BlockDocument)
        .where(db.BlockDocument.is_default_storage_block_document.is_(True))
        .limit(1)
        .execution_options(populate_existing=True)
    )
    result = await session.execute(query)
    orm_block_document = result.scalar()
    if orm_block_document is None:
        return None
    return await BlockDocument.from_orm_model(
        session, orm_block_document, include_secrets=include_secrets
    )


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
    await session.execute(
        sa.update(db.BlockDocument)
        .where(db.BlockDocument.id == block_document_id)
        .values(is_default_storage_block_document=True)
    )


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


@inject_db
async def create_block_document_reference(
    session: sa.orm.Session,
    block_document_reference: schemas.actions.BlockDocumentReferenceCreate,
    db: OrionDBInterface,
):
    values = block_document_reference.dict(
        shallow=True, exclude_unset=True, exclude={"created", "updated"}
    )

    insert_stmt = (await db.insert(db.BlockDocumentReference)).values(
        **block_document_reference.dict(
            shallow=True, exclude_unset=True, exclude={"created", "updated"}
        )
    )
    await session.execute(insert_stmt)

    result = await session.execute(
        sa.select(db.BlockDocumentReference).where(
            db.BlockDocumentReference.id == block_document_reference.id
        )
    )

    return result.scalar()


@inject_db
async def delete_block_document_reference(
    session: sa.orm.Session,
    block_document_reference_id: UUID,
    db: OrionDBInterface,
):
    query = sa.delete(db.BlockDocumentReference).where(
        db.BlockDocumentReference.id == block_document_reference_id
    )
    result = await session.execute(query)
    return result.rowcount > 0
