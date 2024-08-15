"""
Functions for interacting with block document ORM objects.
Intended for internal use by the Prefect REST API.
"""

from copy import copy
from typing import Dict, List, Optional, Tuple
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

import prefect.server.models as models
from prefect.server import schemas
from prefect.server.database import orm_models
from prefect.server.database.dependencies import db_injector
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.schemas.actions import BlockDocumentReferenceCreate
from prefect.server.schemas.core import BlockDocument, BlockDocumentReference
from prefect.server.schemas.filters import BlockSchemaFilter
from prefect.server.utilities.database import UUID as UUIDTypeDecorator
from prefect.utilities.collections import dict_to_flatdict, flatdict_to_dict
from prefect.utilities.names import obfuscate


async def create_block_document(
    session: AsyncSession,
    block_document: schemas.actions.BlockDocumentCreate,
):
    # lookup block type name and copy to the block document table
    block_type = await models.block_types.read_block_type(
        session=session, block_type_id=block_document.block_type_id
    )

    # anonymous block documents can be given a random name if none is provided
    if block_document.is_anonymous and not block_document.name:
        name = f"anonymous-{uuid4()}"
    else:
        name = block_document.name

    orm_block = orm_models.BlockDocument(
        name=name,
        block_schema_id=block_document.block_schema_id,
        block_type_id=block_document.block_type_id,
        block_type_name=block_type.name,
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


async def block_document_with_unique_values_exists(
    session: AsyncSession, block_type_id: UUID, name: str
) -> bool:
    result = await session.execute(
        sa.select(sa.exists(orm_models.BlockDocument)).where(
            orm_models.BlockDocument.block_type_id == block_type_id,
            orm_models.BlockDocument.name == name,
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


async def read_block_document_by_id(
    session: AsyncSession,
    block_document_id: UUID,
    include_secrets: bool = False,
):
    block_documents = await read_block_documents(
        session=session,
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
        Tuple[orm_models.ORMBlockDocument, Optional[str], Optional[UUID]]
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
        if parent_block_document_id == parent_block_document.id and name is not None:
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


async def read_block_document_by_name(
    session: AsyncSession,
    name: str,
    block_type_slug: str,
    include_secrets: bool = False,
):
    """
    Read a block document with the given name and block type slug.
    """
    block_documents = await read_block_documents(
        session=session,
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


def _apply_block_document_filters(
    query,
    block_document_filter: Optional[schemas.filters.BlockDocumentFilter] = None,
    block_schema_filter: Optional[schemas.filters.BlockSchemaFilter] = None,
    block_type_filter: Optional[schemas.filters.BlockTypeFilter] = None,
):
    # if no filter is provided, one is created that excludes anonymous blocks
    if block_document_filter is None:
        block_document_filter = schemas.filters.BlockDocumentFilter(
            is_anonymous=schemas.filters.BlockDocumentFilterIsAnonymous(eq_=False)
        )

    # --- Build an initial query that filters for the requested block documents
    query = query.where(block_document_filter.as_sql_filter())

    if block_type_filter is not None:
        block_type_exists_clause = sa.select(orm_models.BlockType).where(
            orm_models.BlockType.id == orm_models.BlockDocument.block_type_id,
            block_type_filter.as_sql_filter(),
        )
        query = query.where(block_type_exists_clause.exists())

    if block_schema_filter is not None:
        block_schema_exists_clause = sa.select(orm_models.BlockSchema).where(
            orm_models.BlockSchema.id == orm_models.BlockDocument.block_schema_id,
            block_schema_filter.as_sql_filter(),
        )
        query = query.where(block_schema_exists_clause.exists())

    return query


async def read_block_documents(
    session: AsyncSession,
    block_document_filter: Optional[schemas.filters.BlockDocumentFilter] = None,
    block_type_filter: Optional[schemas.filters.BlockTypeFilter] = None,
    block_schema_filter: Optional[schemas.filters.BlockSchemaFilter] = None,
    include_secrets: bool = False,
    sort: Optional[
        schemas.sorting.BlockDocumentSort
    ] = schemas.sorting.BlockDocumentSort.NAME_ASC,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
):
    """
    Read block documents with an optional limit and offset
    """
    # --- Build an initial query that filters for the requested block documents
    filtered_block_documents_query = sa.select(orm_models.BlockDocument.id)
    filtered_block_documents_query = _apply_block_document_filters(
        query=filtered_block_documents_query,
        block_document_filter=block_document_filter,
        block_type_filter=block_type_filter,
        block_schema_filter=block_schema_filter,
    )
    filtered_block_documents_query = filtered_block_documents_query.order_by(
        sort.as_sql_sort()
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
            orm_models.BlockDocumentReference.reference_block_document_id,
            orm_models.BlockDocumentReference.name,
            orm_models.BlockDocumentReference.parent_block_document_id,
        )
        .select_from(parent_documents)
        .join(
            orm_models.BlockDocumentReference,
            orm_models.BlockDocumentReference.parent_block_document_id
            == parent_documents.c.id,
        )
    )
    # union the recursive CTE
    all_block_documents_query = parent_documents.union_all(referenced_documents)

    # --- Join the recursive query that contains all required document IDs
    # back to the BlockDocument table to load info for every document
    # and order by name
    final_query = (
        sa.select(
            orm_models.BlockDocument,
            all_block_documents_query.c.reference_name,
            all_block_documents_query.c.reference_parent_block_document_id,
        )
        .select_from(all_block_documents_query)
        .join(
            orm_models.BlockDocument,
            orm_models.BlockDocument.id == all_block_documents_query.c.id,
        )
        .order_by(sort.as_sql_sort())
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


async def count_block_documents(
    session: AsyncSession,
    block_document_filter: Optional[schemas.filters.BlockDocumentFilter] = None,
    block_type_filter: Optional[schemas.filters.BlockTypeFilter] = None,
    block_schema_filter: Optional[schemas.filters.BlockSchemaFilter] = None,
) -> int:
    """
    Count block documents that match the filters.
    """
    query = sa.select(sa.func.count()).select_from(orm_models.BlockDocument)

    query = _apply_block_document_filters(
        query=query,
        block_document_filter=block_document_filter,
        block_schema_filter=block_schema_filter,
        block_type_filter=block_type_filter,
    )

    result = await session.execute(query)
    return result.scalar()  # type: ignore


async def delete_block_document(
    session: AsyncSession,
    block_document_id: UUID,
) -> bool:
    query = sa.delete(orm_models.BlockDocument).where(
        orm_models.BlockDocument.id == block_document_id
    )
    result = await session.execute(query)
    return result.rowcount > 0


async def update_block_document(
    session: AsyncSession,
    block_document_id: UUID,
    block_document: schemas.actions.BlockDocumentUpdate,
) -> bool:
    merge_existing_data = block_document.merge_existing_data
    current_block_document = await session.get(
        orm_models.BlockDocument, block_document_id
    )
    if not current_block_document:
        return False

    update_values = block_document.model_dump_for_orm(
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
                if flat_update_data.get(secret_key) == obfuscate(current_secret):
                    flat_update_data[secret_key] = current_secret
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
                    sa.select(orm_models.BlockDocumentReference).filter_by(
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

        # encrypt the data and write updated data to the block document
        await current_block_document.encrypt_data(
            session=session, data=block_document_data_without_refs
        )

        # `proposed_block_schema` is always the same as the schema on the client-side
        # Block class that is calling `save`, which may or may not be the same schema
        # as the one on the saved block document
        proposed_block_schema_id = block_document.block_schema_id

        # if a new schema is proposed, update the block schema id for the block document
        if (
            proposed_block_schema_id is not None
            and proposed_block_schema_id != current_block_document.block_schema_id
        ):
            proposed_block_schema = await session.get(
                orm_models.BlockSchema, proposed_block_schema_id
            )

            # make sure the proposed schema is of the same block type as the current document
            if (
                proposed_block_schema.block_type_id
                != current_block_document.block_type_id
            ):
                raise ValueError(
                    "Must migrate block document to a block schema of the same block"
                    " type."
                )
            await session.execute(
                sa.update(orm_models.BlockDocument)
                .where(orm_models.BlockDocument.id == block_document_id)
                .values(block_schema_id=proposed_block_schema_id)
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


@db_injector
async def create_block_document_reference(
    db: PrefectDBInterface,
    session: AsyncSession,
    block_document_reference: schemas.actions.BlockDocumentReferenceCreate,
):
    insert_stmt = db.insert(orm_models.BlockDocumentReference).values(
        **block_document_reference.model_dump_for_orm(
            exclude_unset=True, exclude={"created", "updated"}
        )
    )
    await session.execute(insert_stmt)

    result = await session.execute(
        sa.select(orm_models.BlockDocumentReference).where(
            orm_models.BlockDocumentReference.id == block_document_reference.id
        )
    )

    return result.scalar()


async def delete_block_document_reference(
    session: AsyncSession,
    block_document_reference_id: UUID,
):
    query = sa.delete(orm_models.BlockDocumentReference).where(
        orm_models.BlockDocumentReference.id == block_document_reference_id
    )
    result = await session.execute(query)
    return result.rowcount > 0
