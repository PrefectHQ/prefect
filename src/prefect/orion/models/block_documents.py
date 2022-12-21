"""
Functions for interacting with block document ORM objects.
Intended for internal use by the Orion API.
"""
from copy import copy
from typing import Dict, List, Optional, Tuple
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

import prefect.orion.models as models
from prefect.orion import schemas
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.database.orm_models import ORMBlockDocument
from prefect.orion.schemas.actions import BlockDocumentReferenceCreate
from prefect.orion.schemas.core import BlockDocument, BlockDocumentReference
from prefect.orion.schemas.filters import BlockSchemaFilter
from prefect.orion.utilities.database import UUID as UUIDTypeDecorator
from prefect.orion.utilities.names import obfuscate_string
from prefect.utilities.collections import dict_to_flatdict, flatdict_to_dict
from prefect.utilities.names import obfuscate


@inject_db
async def create_block_document(
    session: AsyncSession,
    block_document: schemas.actions.BlockDocumentCreate,
    db: OrionDBInterface,
):

    # anonymous block documents can be given a random name if none is provided
    if block_document.is_anonymous and not block_document.name:
        name = f"anonymous-{uuid4()}"
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

    # reload the block document in order to load the associated block schema
    # relationship
    return await read_block_document_by_id(
        session=session,
        block_document_id=orm_block.id,
        include_secrets=False,
    )


@inject_db
async def block_document_with_unique_values_exists(
    session: AsyncSession, block_type_id: UUID, name: str, db: OrionDBInterface
) -> bool:
    result = await session.execute(
        sa.select(sa.exists(db.BlockDocument)).where(
            db.BlockDocument.block_type_id == block_type_id,
            db.BlockDocument.name == name,
        )
    )
    return bool(result.scalar_one_or_none())


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
    session: AsyncSession,
    block_document_id: UUID,
    db: OrionDBInterface,
    include_secrets: bool = False,
):

    block_documents = await read_block_documents(
        session=session,
        db=db,
        block_document_filter=schemas.filters.BlockDocumentFilter(
            id=dict(any_=[block_document_id]),
            # don't apply any anonymous filtering
            is_anonymous=None,
        ),
        include_secrets=include_secrets,
        limit=1,
    )
    return block_documents[0] if block_documents else None


async def _construct_full_block_document(
    session: AsyncSession,
    block_documents_with_references: List[
        Tuple[ORMBlockDocument, Optional[str], Optional[UUID]]
    ],
    parent_block_document: Optional[BlockDocument] = None,
    include_secrets: bool = False,
) -> Optional[BlockDocument]:
    if len(block_documents_with_references) == 0:
        return None
    if parent_block_document is None:
        parent_block_document = copy(
            await _find_parent_block_document(
                session,
                block_documents_with_references,
                include_secrets=include_secrets,
            )
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
                parent_block_document=copy(block_document),
                include_secrets=include_secrets,
            )
            parent_block_document.data[name] = full_child_block_document.data
            parent_block_document.block_document_references[name] = {
                "block_document": {
                    "id": block_document.id,
                    "name": block_document.name,
                    "block_type": block_document.block_type,
                    "is_anonymous": block_document.is_anonymous,
                    "block_document_references": (
                        full_child_block_document.block_document_references
                    ),
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
    session: AsyncSession,
    name: str,
    block_type_slug: str,
    db: OrionDBInterface,
    include_secrets: bool = False,
):
    """
    Read a block document with the given name and block type slug.
    """
    block_documents = await read_block_documents(
        session=session,
        db=db,
        block_document_filter=schemas.filters.BlockDocumentFilter(
            name=dict(any_=[name]),
            # don't apply any anonymous filtering
            is_anonymous=None,
        ),
        block_type_filter=schemas.filters.BlockTypeFilter(
            slug=dict(any_=[block_type_slug])
        ),
        include_secrets=include_secrets,
        limit=1,
    )
    return block_documents[0] if block_documents else None


@inject_db
async def read_block_documents(
    session: AsyncSession,
    db: OrionDBInterface,
    block_document_filter: Optional[schemas.filters.BlockDocumentFilter] = None,
    block_type_filter: Optional[schemas.filters.BlockTypeFilter] = None,
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
            is_anonymous=schemas.filters.BlockDocumentFilterIsAnonymous(eq_=False)
        )

    # --- Build an initial query that filters for the requested block documents
    filtered_block_documents_query = sa.select(db.BlockDocument.id).where(
        block_document_filter.as_sql_filter(db)
    )

    if block_type_filter is not None:
        block_type_exists_clause = sa.select(db.BlockType).where(
            db.BlockType.id == db.BlockDocument.block_type_id,
            block_type_filter.as_sql_filter(db),
        )
        filtered_block_documents_query = filtered_block_documents_query.where(
            block_type_exists_clause.exists()
        )

    if block_schema_filter is not None:
        block_schema_exists_clause = sa.select(db.BlockSchema).where(
            db.BlockSchema.id == db.BlockDocument.block_schema_id,
            block_schema_filter.as_sql_filter(db),
        )
        filtered_block_documents_query = filtered_block_documents_query.where(
            block_schema_exists_clause.exists()
        )

    if offset is not None:
        filtered_block_documents_query = filtered_block_documents_query.offset(offset)

    if limit is not None:
        filtered_block_documents_query = filtered_block_documents_query.limit(limit)

    filtered_block_documents_query = filtered_block_documents_query.cte(
        "filtered_block_documents"
    )

    # --- Build a recursive query that starts with the filtered block documents
    # and iteratively loads all referenced block documents. The query includes
    # the ID of each block document as well as the ID of the document that
    # references it and name it's referenced by, if applicable.
    parent_documents = (
        sa.select(
            filtered_block_documents_query.c.id,
            sa.cast(sa.null(), sa.String).label("reference_name"),
            sa.cast(sa.null(), UUIDTypeDecorator).label(
                "reference_parent_block_document_id"
            ),
        )
        .select_from(filtered_block_documents_query)
        .cte("all_block_documents", recursive=True)
    )
    # recursive part of query
    referenced_documents = (
        sa.select(
            db.BlockDocumentReference.reference_block_document_id,
            db.BlockDocumentReference.name,
            db.BlockDocumentReference.parent_block_document_id,
        )
        .select_from(parent_documents)
        .join(
            db.BlockDocumentReference,
            db.BlockDocumentReference.parent_block_document_id == parent_documents.c.id,
        )
    )
    # union the recursive CTE
    all_block_documents_query = parent_documents.union_all(referenced_documents)

    # --- Join the recursive query that contains all required document IDs
    # back to the BlockDocument table to load info for every document
    # and order by name
    final_query = (
        sa.select(
            db.BlockDocument,
            all_block_documents_query.c.reference_name,
            all_block_documents_query.c.reference_parent_block_document_id,
        )
        .select_from(all_block_documents_query)
        .join(db.BlockDocument, db.BlockDocument.id == all_block_documents_query.c.id)
        .order_by(db.BlockDocument.name)
    )

    result = await session.execute(
        final_query.execution_options(populate_existing=True)
    )

    block_documents_with_references = result.unique().all()

    # identify true "parent" documents as those with no reference parent ids
    parent_block_document_ids = [
        d[0].id
        for d in block_documents_with_references
        if d.reference_parent_block_document_id is None
    ]

    # walk the resulting dataset and hydrate all block documents
    fully_constructed_block_documents = []
    visited_block_document_ids = []
    for root_orm_block_document, _, _ in block_documents_with_references:
        if (
            root_orm_block_document.id in parent_block_document_ids
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

    block_schema_ids = [
        block_document.block_schema_id
        for block_document in fully_constructed_block_documents
    ]
    block_schemas = await models.block_schemas.read_block_schemas(
        session=session,
        block_schema_filter=BlockSchemaFilter(id=dict(any_=block_schema_ids)),
    )
    for block_document in fully_constructed_block_documents:
        corresponding_block_schema = next(
            block_schema
            for block_schema in block_schemas
            if block_schema.id == block_document.block_schema_id
        )
        block_document.block_schema = corresponding_block_schema
    return fully_constructed_block_documents


@inject_db
async def delete_block_document(
    session: AsyncSession,
    block_document_id: UUID,
    db: OrionDBInterface,
) -> bool:

    query = sa.delete(db.BlockDocument).where(db.BlockDocument.id == block_document_id)
    result = await session.execute(query)
    return result.rowcount > 0


@inject_db
async def update_block_document(
    session: AsyncSession,
    block_document_id: UUID,
    block_document: schemas.actions.BlockDocumentUpdate,
    db: OrionDBInterface,
) -> bool:

    merge_existing_data = block_document.merge_existing_data
    current_block_document = await session.get(db.BlockDocument, block_document_id)
    if not current_block_document:
        return False

    update_values = block_document.dict(
        shallow=True,
        exclude_unset=merge_existing_data,
        exclude={"merge_existing_data"},
    )

    if "data" in update_values and update_values["data"] is not None:
        current_data = await current_block_document.decrypt_data(session=session)

        # if a value for a secret field was provided that is identical to the
        # obfuscated value of the current secret value, it means someone is
        # probably trying to update all of the documents fields without
        # realizing they are posting back obfuscated data, so we disregard the update
        flat_update_data = dict_to_flatdict(update_values["data"])
        flat_current_data = dict_to_flatdict(current_data)
        for secret_field in current_block_document.block_schema.fields.get(
            "secret_fields", []
        ):
            secret_key = tuple(secret_field.split("."))
            current_secret = flat_current_data.get(secret_key)
            if current_secret is not None:
                if flat_update_data.get(secret_key) == obfuscate_string(current_secret):
                    del flat_update_data[secret_key]
            # Looks for obfuscated values nested under a secret field with a wildcard.
            # If any obfuscated values are found, we assume that it shouldn't be update,
            # and they are replaced with the current value for that key to avoid losing
            # data during update.
            elif "*" in secret_key:
                wildcard_index = secret_key.index("*")
                for data_key in flat_update_data.keys():
                    if (
                        secret_key[0:wildcard_index] == data_key[0:wildcard_index]
                    ) and (
                        flat_update_data[data_key]
                        == obfuscate(flat_update_data[data_key])
                    ):
                        flat_update_data[data_key] = flat_current_data[data_key]

        update_values["data"] = flatdict_to_dict(flat_update_data)

        if merge_existing_data:
            # merge the existing data and the new data for partial updates
            current_data.update(update_values["data"])
            update_values["data"] = current_data

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
        for secret_key, reference_block_document_id in new_block_document_references:
            matching_current_block_document_reference = _find_block_document_reference(
                current_block_document_references,
                secret_key,
                reference_block_document_id,
            )
            if matching_current_block_document_reference is None:
                await create_block_document_reference(
                    session=session,
                    block_document_reference=BlockDocumentReferenceCreate(
                        parent_block_document_id=block_document_id,
                        reference_block_document_id=reference_block_document_id,
                        name=secret_key,
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
async def create_block_document_reference(
    session: AsyncSession,
    block_document_reference: schemas.actions.BlockDocumentReferenceCreate,
    db: OrionDBInterface,
):
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
    session: AsyncSession,
    block_document_reference_id: UUID,
    db: OrionDBInterface,
):
    query = sa.delete(db.BlockDocumentReference).where(
        db.BlockDocumentReference.id == block_document_reference_id
    )
    result = await session.execute(query)
    return result.rowcount > 0
