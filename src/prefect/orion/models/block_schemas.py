"""
Functions for interacting with block schema ORM objects.
Intended for internal use by the Orion API.
"""
import json
from typing import Dict, List, Optional, Tuple, Union
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import delete, select

from prefect.blocks.core import Block
from prefect.orion import schemas
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.models.block_types import read_block_type_by_name
from prefect.orion.schemas.actions import BlockSchemaCreate
from prefect.orion.schemas.core import BlockSchema, BlockSchemaReference


class MissingBlockTypeException(Exception):
    """Raised when the block type corresponding to a block schema cannot be found"""


@inject_db
async def create_block_schema(
    session: sa.orm.Session,
    block_schema: schemas.actions.BlockSchemaCreate,
    db: OrionDBInterface,
    override: bool = False,
    definitions: Optional[Dict] = None,
):
    """
    Create a new block schema.

    Args:
        session: A database session
        block_schema: a block schema object
        definitions: Definitions of fields from block schema fields
            attribute. Used when recursively creating nested block schemas

    Returns:
        block_schema: an ORM block schema model
    """
    insert_values = block_schema.dict(
        shallow=True,
        exclude_unset=False,
        exclude={"block_type", "id", "created", "updated"},
    )
    definitions = definitions or insert_values["fields"].pop("definitions", None)
    insert_values["checksum"] = Block._calculate_schema_checksum(
        insert_values["fields"]
    )

    block_schema_references: Dict = insert_values["fields"].pop(
        "block_schema_references", {}
    )

    insert_stmt = (await db.insert(db.BlockSchema)).values(**insert_values)
    if override:
        insert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=db.block_schema_unique_upsert_columns,
            set_=insert_values,
        )
    await session.execute(insert_stmt)

    query = (
        sa.select(db.BlockSchema)
        .where(
            db.BlockSchema.checksum == insert_values["checksum"],
        )
        .execution_options(populate_existing=True)
    )

    result = await session.execute(query)
    created_block_schema = result.scalar()

    await _register_nested_block_schemas(
        session=session,
        parent_block_schema_id=created_block_schema.id,
        block_schema_references=block_schema_references,
        base_fields=insert_values["fields"],
        definitions=definitions,
    )

    created_block_schema.fields["block_schema_references"] = block_schema_references
    if definitions is not None:
        created_block_schema.fields["definitions"] = definitions
    return created_block_schema


async def _register_nested_block_schemas(
    session: sa.orm.Session,
    parent_block_schema_id: UUID,
    block_schema_references: Dict[str, Union[Dict[str, str], List[Dict[str, str]]]],
    base_fields: Dict,
    definitions: Optional[Dict],
):
    """
    Iterates through each of the block schema references declared on the block schema.
    Attempts to register each of the nested block schemas if they have not already been
    registered. An error is thrown if the corresponding block type for a block schema
    has not been registered.

    Args:
        session: A database session.
        parent_block_schema_id: The ID of the parent block schema.
        block_schema_references: A dictionary containing the block schema references for
            the child block schemas of the parent block schema.
        base_fields: The field name and type declarations for the parent block schema.
        definitions: A dictionary of the field name and type declarations of each
            child block schema.
    """
    for reference_name, reference_values in block_schema_references.items():
        # Operate on a list so that we can share the same code paths for union cases
        reference_values = (
            reference_values
            if isinstance(reference_values, list)
            else [reference_values]
        )
        for reference_values_entry in reference_values:
            # Check to make sure that associated block type exists
            reference_block_type = await read_block_type_by_name(
                session=session,
                block_type_name=reference_values_entry["block_type_name"],
            )
            if reference_block_type is None:
                raise MissingBlockTypeException(
                    f"Cannot create block schema because block type {reference_values_entry['block_type_name']!r} was not found."
                    "Did you forget to register the block type?"
                )
            # Checks to see if the visited block schema has been previously created
            reference_block_schema = await read_block_schema_by_checksum(
                session=session,
                checksum=reference_values_entry["block_schema_checksum"],
            )
            # Attempts to create block schema since it has not already been registered
            if reference_block_schema is None:
                if definitions is None:
                    raise ValueError(
                        "Unable to create nested block schema due to missing definitions "
                        "in root block schema fields"
                    )
                sub_block_schema_fields = _get_fields_for_child_schema(
                    definitions, base_fields, reference_name, reference_block_type
                )

                if sub_block_schema_fields is None:
                    raise ValueError(
                        f"Unable to create nested block schema for block type {reference_block_type.name!r} due to missing definition."
                    )

                reference_block_schema = await create_block_schema(
                    session=session,
                    block_schema=BlockSchemaCreate(
                        fields=sub_block_schema_fields,
                        block_type_id=reference_block_type.id,
                    ),
                    definitions=definitions,
                )
            await create_block_schema_reference(
                session=session,
                block_schema_reference=BlockSchemaReference(
                    parent_block_schema_id=parent_block_schema_id,
                    reference_block_schema_id=reference_block_schema.id,
                    name=reference_name,
                ),
            )


def _get_fields_for_child_schema(
    definitions, base_fields, reference_name, reference_block_type
):
    if definitions is None:
        raise ValueError(
            "Unable to create nested block schema due to missing definitions "
            "in root block schema fields"
        )
    spec_reference = base_fields["properties"][reference_name]
    sub_block_schema_fields = None
    # Looks for the nested schema definition in a union of block schemas
    if "anyOf" in spec_reference:
        for reference in spec_reference["anyOf"]:
            definition_key = reference["$ref"].replace("#/definitions/", "")
            potential_sub_block_schema_fields = definitions[definition_key]
            # Determines the definition to use when registering a child
            # block schema by verifying that the block type name stored in
            # the definition matches the name of the block type that we're
            # currently trying to register a block schema for.
            if (
                definitions[definition_key]["block_type_name"]
                == reference_block_type.name
            ):
                # Once we've found the matching definition, we not longer
                # need to iterate
                sub_block_schema_fields = potential_sub_block_schema_fields
                break
    else:
        # When a block schema reference is a single block, we can use the
        # title to directly find the definition for that block schema.
        sub_block_schema_fields = definitions[
            spec_reference["$ref"].replace("#/definitions/", "")
        ]
    return sub_block_schema_fields


@inject_db
async def delete_block_schema(
    session: sa.orm.Session, block_schema_id: UUID, db: OrionDBInterface
) -> bool:
    """
    Delete a block schema by id.

    Args:
        session: A database session
        block_schema_id: a block schema id

    Returns:
        bool: whether or not the block schema was deleted
    """

    result = await session.execute(
        delete(db.BlockSchema).where(db.BlockSchema.id == block_schema_id)
    )
    return result.rowcount > 0


@inject_db
async def read_block_schema(
    session: sa.orm.Session,
    block_schema_id: UUID,
    db: OrionDBInterface,
):
    """
    Reads a block schema by id. Will reconstruct the block schema's fields attribute
    to include block schema references.

    Args:
        session: A database session
        block_schema_id: a block_schema id

    Returns:
        db.Blockschema: the block_schema
    """

    # Construction of a recursive query which returns the specified block schema
    # along with and nested block schemas coupled with the ID of their parent schema
    # the key that they reside under.
    block_schema_references_query = (
        sa.select(db.BlockSchemaReference)
        .select_from(db.BlockSchemaReference)
        .filter_by(parent_block_schema_id=block_schema_id)
        .cte("block_schema_references", recursive=True)
    )
    block_schema_references_join = (
        sa.select(db.BlockSchemaReference)
        .select_from(db.BlockSchemaReference)
        .join(
            block_schema_references_query,
            db.BlockSchemaReference.parent_block_schema_id
            == block_schema_references_query.c.reference_block_schema_id,
        )
    )
    recursive_block_schema_references_cte = block_schema_references_query.union_all(
        block_schema_references_join
    )
    nested_block_schemas_query = (
        sa.select(
            [
                db.BlockSchema,
                recursive_block_schema_references_cte.c.name,
                recursive_block_schema_references_cte.c.parent_block_schema_id,
            ]
        )
        .select_from(db.BlockSchema)
        .join(
            recursive_block_schema_references_cte,
            db.BlockSchema.id
            == recursive_block_schema_references_cte.c.reference_block_schema_id,
            isouter=True,
        )
        .filter(
            sa.or_(
                db.BlockSchema.id == block_schema_id,
                recursive_block_schema_references_cte.c.parent_block_schema_id.is_not(
                    None
                ),
            )
        )
    )
    result = await session.execute(nested_block_schemas_query)

    return _construct_full_block_schema(result.all())


def _construct_full_block_schema(
    block_schemas_with_references: List[
        Tuple[BlockSchema, Optional[str], Optional[UUID]]
    ],
    root_block_schema: Optional[BlockSchema] = None,
) -> Optional[BlockSchema]:
    """
    Takes a list of block schemas along with reference information and reconstructs
    the root block schema's fields attribute to contain block schema references for
    client consumption.

    Args:
        block_schema_with_references: A list of tuples with the structure:
            - A block schema object
            - The name the block schema lives under in the parent block schema
            - The ID of the block schema's parent block schema
        root_block_schema: Optional block schema to start traversal. Will attempt to
            determine root block schema if not provided.

    Returns:
        BlockSchema: A block schema with a fully reconstructed fields attribute
    """
    if len(block_schemas_with_references) == 0:
        return None
    root_block_schema = (
        root_block_schema
        if root_block_schema is not None
        else _find_root_block_schema(block_schemas_with_references)
    )
    if root_block_schema is None:
        raise ValueError(
            "Unable to determine root block schema during schema reconstruction."
        )
    root_block_schema.fields = _construct_block_schema_fields_with_block_references(
        root_block_schema, block_schemas_with_references
    )
    definitions = _construct_block_schema_spec_definitions(
        root_block_schema, block_schemas_with_references
    )
    if definitions:
        root_block_schema.fields["definitions"] = definitions
    return root_block_schema


def _find_root_block_schema(block_schemas_with_references):
    """
    Attempts to find the root block schema from a list of block schemas
    with references. Returns None if a root block schema is not found.
    Returns only the first potential root block schema if multiple are found.
    """
    return next(
        (
            block_schema
            for (
                block_schema,
                _,
                parent_block_schema_id,
            ) in block_schemas_with_references
            if parent_block_schema_id is None
        ),
        None,
    )


def _construct_block_schema_spec_definitions(
    root_block_schema, block_schemas_with_references
):
    """
    Constructs field definitions for a block schema based on the nested block schemas
    as defined in the block_schemas_with_references list.
    """
    definitions = {}
    for _, block_schema_references in root_block_schema.fields[
        "block_schema_references"
    ].items():
        block_schema_references = (
            block_schema_references
            if isinstance(block_schema_references, list)
            else [block_schema_references]
        )
        for block_schema_reference in block_schema_references:
            child_block_schema = _find_block_schema_via_checksum(
                block_schemas_with_references,
                block_schema_reference["block_schema_checksum"],
            )

            if child_block_schema is not None:
                child_block_schema = _construct_full_block_schema(
                    block_schemas_with_references, child_block_schema
                )
                definitions = _add_block_schemas_fields_to_definitions(
                    definitions, child_block_schema
                )
    return definitions


def _find_block_schema_via_checksum(block_schemas_with_references, checksum):
    """Attempt to find a block schema via a given checksum. Returns None if not found."""
    return next(
        (
            block_schema
            for block_schema, _, _ in block_schemas_with_references
            if block_schema.checksum == checksum
        ),
        None,
    )


def _add_block_schemas_fields_to_definitions(definitions, child_block_schema):
    """
    Returns a new definitions dict with the fields of a block schema and it's child
    block schemas added to the existing defintions.
    """
    block_schema_title = child_block_schema.fields.get("title")
    if block_schema_title is not None:
        # Definitions are declared as a flat dict, so we pop off definitions
        # from child schemas and add them to the parent definitions dict
        child_definitions = child_block_schema.fields.pop("definitions", {})
        return {
            **definitions,
            **{block_schema_title: child_block_schema.fields},
            **child_definitions,
        }
    else:
        return definitions


def _construct_block_schema_fields_with_block_references(
    parent_block_schema: BlockSchema,
    block_schemas_with_references: List[
        Tuple[BlockSchema, Optional[str], Optional[UUID]]
    ],
):
    """
    Constructs the block_schema_references in a block schema's fields attributes. Returns
    a copy of the block schema with block_schema_references added.

    Args:
        parent_block_schema: The block schema that needs block references populated.
        block_schema_with_references: A list of tuples with the structure:
            - A block schema object
            - The name the block schema lives under in the parent block schema
            - The ID of the block schema's parent block schema

    Returns:
        Dict: Block schema fields with block schema references added.

    """
    block_schema_fields_copy = {
        **parent_block_schema.fields,
        "block_schema_references": {},
    }
    for (
        nested_block_schema,
        name,
        parent_block_schema_id,
    ) in block_schemas_with_references:
        if parent_block_schema_id == parent_block_schema.id:
            new_block_schema_reference = {
                "block_schema_checksum": nested_block_schema.checksum,
                "block_type_name": nested_block_schema.block_type.name,
            }
            # A block reference for this key does not yet exist
            if name not in block_schema_fields_copy["block_schema_references"]:
                block_schema_fields_copy["block_schema_references"][
                    name
                ] = new_block_schema_reference
            else:
                # List of block references for this key already exist and the block
                # reference that we are attempting add isn't present
                if (
                    isinstance(
                        block_schema_fields_copy["block_schema_references"][name],
                        list,
                    )
                    and new_block_schema_reference
                    not in block_schema_fields_copy["block_schema_references"][name]
                ):
                    block_schema_fields_copy["block_schema_references"][name].append(
                        new_block_schema_reference
                    )
                # A single block reference for this key already exists and it does not
                # match the block reference that we are attempting to add
                elif (
                    block_schema_fields_copy["block_schema_references"][name]
                    != new_block_schema_reference
                ):
                    block_schema_fields_copy["block_schema_references"][name] = [
                        block_schema_fields_copy["block_schema_references"][name],
                        new_block_schema_reference,
                    ]
    return block_schema_fields_copy


@inject_db
async def read_block_schemas(
    session: sa.orm.Session,
    db: OrionDBInterface,
    block_schema_filter: Optional[schemas.filters.BlockSchemaFilter] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
):
    """
    Reads block schemas, optionally filtered by type or name.

    Args:
        session: A database session
        block_schema_filter: a block schema filter object
        limit (int): query limit
        offset (int): query offset

    Returns:
        List[db.BlockSchema]: the block_schemas
    """
    # schemas are ordered by `created DESC` to get the most recently created
    # ones first (and to facilitate getting the newest one with `limit=1`).
    filtered_block_schemas_query = select([db.BlockSchema.id]).order_by(
        db.BlockSchema.created.desc()
    )

    if block_schema_filter:
        filtered_block_schemas_query = filtered_block_schemas_query.where(
            block_schema_filter.as_sql_filter(db)
        )

    if offset is not None:
        filtered_block_schemas_query = filtered_block_schemas_query.offset(offset)
    if limit is not None:
        filtered_block_schemas_query = filtered_block_schemas_query.limit(limit)

    filtered_block_schema_ids = (
        (await session.execute(filtered_block_schemas_query)).scalars().unique().all()
    )

    block_schema_references_query = (
        sa.select(db.BlockSchemaReference)
        .select_from(db.BlockSchemaReference)
        .filter(
            db.BlockSchemaReference.parent_block_schema_id.in_(
                filtered_block_schemas_query
            )
        )
        .cte("block_schema_references", recursive=True)
    )
    block_schema_references_join = (
        sa.select(db.BlockSchemaReference)
        .select_from(db.BlockSchemaReference)
        .join(
            block_schema_references_query,
            db.BlockSchemaReference.parent_block_schema_id
            == block_schema_references_query.c.reference_block_schema_id,
        )
    )
    recursive_block_schema_references_cte = block_schema_references_query.union_all(
        block_schema_references_join
    )

    nested_block_schemas_query = (
        sa.select(
            [
                db.BlockSchema,
                recursive_block_schema_references_cte.c.name,
                recursive_block_schema_references_cte.c.parent_block_schema_id,
            ]
        )
        .select_from(db.BlockSchema)
        # in order to reconstruct nested block schemas efficiently, we need to visit them
        # in the order they were created (so that we guarantee that nested/referenced schemas)
        # have already been seen. Therefore this second query sorts by created ASC
        .order_by(db.BlockSchema.created.asc())
        .join(
            recursive_block_schema_references_cte,
            db.BlockSchema.id
            == recursive_block_schema_references_cte.c.reference_block_schema_id,
            isouter=True,
        )
        .filter(
            sa.or_(
                db.BlockSchema.id.in_(filtered_block_schemas_query),
                recursive_block_schema_references_cte.c.parent_block_schema_id.is_not(
                    None
                ),
            )
        )
    )

    block_schemas_with_references = (
        (await session.execute(nested_block_schemas_query)).unique().all()
    )
    fully_constructed_block_schemas = []
    visited_block_schema_ids = []
    for root_block_schema, _, _ in block_schemas_with_references:
        if (
            root_block_schema.id in filtered_block_schema_ids
            and root_block_schema.id not in visited_block_schema_ids
        ):
            fully_constructed_block_schemas.append(
                _construct_full_block_schema(
                    block_schemas_with_references, root_block_schema
                )
            )
            visited_block_schema_ids.append(root_block_schema.id)

    # because we reconstructed schemas ordered by created ASC, we
    # reverse the final output to restore created DESC
    return list(reversed(fully_constructed_block_schemas))


@inject_db
async def read_block_schema_by_checksum(
    session: sa.orm.Session,
    checksum: str,
    db: OrionDBInterface,
) -> Optional[BlockSchema]:
    """
    Reads a block_schema by checksum. Will reconstruct the block schema's fields
    attribute to include block schema references.

    Args:
        session: A database session
        checksum: a block_schema checksum

    Returns:
        db.BlockSchema: the block_schema
    """
    # Construction of a recursive query which returns the specified block schema
    # along with and nested block schemas coupled with the ID of their parent schema
    # the key that they reside under.
    root_block_schema_query = (
        sa.select(db.BlockSchema).filter_by(checksum=checksum).cte("root_block_schema")
    )

    block_schema_references_query = (
        sa.select(db.BlockSchemaReference)
        .select_from(db.BlockSchemaReference)
        .filter_by(parent_block_schema_id=root_block_schema_query.c.id)
        .cte("block_schema_references", recursive=True)
    )
    block_schema_references_join = (
        sa.select(db.BlockSchemaReference)
        .select_from(db.BlockSchemaReference)
        .join(
            block_schema_references_query,
            db.BlockSchemaReference.parent_block_schema_id
            == block_schema_references_query.c.reference_block_schema_id,
        )
    )
    recursive_block_schema_references_cte = block_schema_references_query.union_all(
        block_schema_references_join
    )
    nested_block_schemas_query = (
        sa.select(
            [
                db.BlockSchema,
                recursive_block_schema_references_cte.c.name,
                recursive_block_schema_references_cte.c.parent_block_schema_id,
            ]
        )
        .select_from(db.BlockSchema)
        .join(
            recursive_block_schema_references_cte,
            db.BlockSchema.id
            == recursive_block_schema_references_cte.c.reference_block_schema_id,
            isouter=True,
        )
        .filter(
            sa.or_(
                db.BlockSchema.id == root_block_schema_query.c.id,
                recursive_block_schema_references_cte.c.parent_block_schema_id.is_not(
                    None
                ),
            )
        )
    )
    result = await session.execute(nested_block_schemas_query)
    return _construct_full_block_schema(result.all())


@inject_db
async def read_available_block_capabilities(
    session: sa.orm.Session, db: OrionDBInterface
) -> List[str]:
    query = sa.select(
        db.json_arr_agg(db.cast_to_json(db.BlockSchema.capabilities.distinct()))
    )
    capability_combinations = (await session.execute(query)).scalars().first() or list()
    if db.uses_json_strings and isinstance(capability_combinations, str):
        capability_combinations = json.loads(capability_combinations)
    return list({c for capabilities in capability_combinations for c in capabilities})


@inject_db
async def create_block_schema_reference(
    session: sa.orm.Session,
    block_schema_reference: schemas.core.BlockSchemaReference,
    db: OrionDBInterface,
):
    insert_stmt = (await db.insert(db.BlockSchemaReference)).values(
        **block_schema_reference.dict(
            shallow=True, exclude_unset=True, exclude={"created", "updated"}
        )
    )
    await session.execute(insert_stmt)

    result = await session.execute(
        sa.select(db.BlockSchemaReference).where(
            db.BlockSchemaReference.id == block_schema_reference.id
        )
    )
    return result.scalar()
