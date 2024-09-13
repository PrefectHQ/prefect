"""
Functions for interacting with block schema ORM objects.
Intended for internal use by the Prefect REST API.
"""

import json
from copy import copy
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import schemas
from prefect.server.database import orm_models
from prefect.server.database.dependencies import db_injector
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.models.block_types import read_block_type_by_slug
from prefect.server.schemas.actions import BlockSchemaCreate
from prefect.server.schemas.core import BlockSchema, BlockSchemaReference

if TYPE_CHECKING:
    from prefect.client.schemas.actions import (
        BlockSchemaCreate as ClientBlockSchemaCreate,
    )
    from prefect.client.schemas.objects import BlockSchema as ClientBlockSchema


class MissingBlockTypeException(Exception):
    """Raised when the block type corresponding to a block schema cannot be found"""


@db_injector
async def create_block_schema(
    db: PrefectDBInterface,
    session: AsyncSession,
    block_schema: Union[
        schemas.actions.BlockSchemaCreate,
        schemas.core.BlockSchema,
        "ClientBlockSchemaCreate",
        "ClientBlockSchema",
    ],
    override: bool = False,
    definitions: Optional[Dict] = None,
) -> Union[BlockSchema, orm_models.BlockSchema]:
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
    from prefect.blocks.core import Block, _get_non_block_reference_definitions

    # We take a shortcut in many unit tests and in block registration to pass client
    # models directly to this function.  We will support this by converting them to
    # the appropriate server model.
    if not isinstance(block_schema, schemas.actions.BlockSchemaCreate):
        block_schema = schemas.actions.BlockSchemaCreate.model_validate(
            block_schema.model_dump(
                mode="json",
                exclude={"id", "created", "updated", "checksum", "block_type"},
            )
        )

    insert_values = block_schema.model_dump_for_orm(
        exclude_unset=False,
        exclude={"block_type", "id", "created", "updated"},
    )

    definitions = definitions or block_schema.fields.get("definitions")
    fields_for_checksum = insert_values["fields"]
    if definitions:
        # Ensure definitions are available if this is a nested schema
        # that is being registered
        fields_for_checksum["definitions"] = definitions
    checksum = Block._calculate_schema_checksum(fields_for_checksum)

    # Check for existing block schema based on calculated checksum
    existing_block_schema = await read_block_schema_by_checksum(
        session=session, checksum=checksum, version=block_schema.version
    )
    # Return existing block schema if it exists. Allows block schema creation to be called multiple
    # times for the same schema without errors.
    if existing_block_schema:
        return existing_block_schema

    insert_values["checksum"] = checksum

    if definitions:
        # Get non block definitions for saving to the DB.
        non_block_definitions = _get_non_block_reference_definitions(
            insert_values["fields"], definitions
        )
        if non_block_definitions:
            insert_values["fields"][
                "definitions"
            ] = _get_non_block_reference_definitions(
                insert_values["fields"], definitions
            )
        else:
            # Prevent storing definitions for blocks. Those are reconstructed on read.
            insert_values["fields"].pop("definitions", None)

    # Prevent saving block schema references in the block_schema table. They have
    # their own table.
    block_schema_references: Dict = insert_values["fields"].pop(
        "block_schema_references", {}
    )

    insert_stmt = db.insert(orm_models.BlockSchema).values(**insert_values)
    if override:
        insert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=db.block_schema_unique_upsert_columns,
            set_=insert_values,
        )
    await session.execute(insert_stmt)

    query = (
        sa.select(orm_models.BlockSchema)
        .where(
            orm_models.BlockSchema.checksum == insert_values["checksum"],
        )
        .order_by(orm_models.BlockSchema.created.desc())
        .limit(1)
        .execution_options(populate_existing=True)
    )

    if block_schema.version is not None:
        query = query.where(orm_models.BlockSchema.version == block_schema.version)

    result = await session.execute(query)
    created_block_schema = copy(result.scalar_one())

    await _register_nested_block_schemas(
        session=session,
        parent_block_schema_id=created_block_schema.id,
        block_schema_references=block_schema_references,
        base_fields=insert_values["fields"],
        definitions=definitions,
        override=override,
    )

    created_block_schema.fields["block_schema_references"] = block_schema_references
    if definitions is not None:
        created_block_schema.fields["definitions"] = definitions

    return created_block_schema


async def _register_nested_block_schemas(
    session: AsyncSession,
    parent_block_schema_id: UUID,
    block_schema_references: Dict[str, Union[Dict[str, str], List[Dict[str, str]]]],
    base_fields: Dict,
    definitions: Optional[Dict],
    override: bool = False,
) -> None:
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
        override: Flag controlling if a block schema should updated in place.
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
            reference_block_type = await read_block_type_by_slug(
                session=session,
                block_type_slug=reference_values_entry["block_type_slug"],
            )
            if reference_block_type is None:
                raise MissingBlockTypeException(
                    "Cannot create block schema because block type"
                    f" {reference_values_entry['block_type_slug']!r} was not found.Did"
                    " you forget to register the block type?"
                )

            reference_block_schema: Union[BlockSchema, orm_models.BlockSchema, None]

            # Checks to see if the visited block schema has been previously created
            reference_block_schema = await read_block_schema_by_checksum(
                session=session,
                checksum=reference_values_entry["block_schema_checksum"],
            )
            # Attempts to create block schema since it has not already been registered
            if reference_block_schema is None:
                if definitions is None:
                    raise ValueError(
                        "Unable to create nested block schema due to missing"
                        " definitions in root block schema fields"
                    )
                sub_block_schema_fields = _get_fields_for_child_schema(
                    definitions, base_fields, reference_name, reference_block_type
                )

                if sub_block_schema_fields is None:
                    raise ValueError(
                        "Unable to create nested block schema for block type"
                        f" {reference_block_type.name!r} due to missing definition."
                    )

                reference_block_schema = await create_block_schema(
                    session=session,
                    block_schema=BlockSchemaCreate(
                        fields=sub_block_schema_fields,
                        block_type_id=reference_block_type.id,
                    ),
                    override=override,
                    definitions=definitions,
                )
            # Create a block schema reference linking the nested block schema to its parent.
            await create_block_schema_reference(
                session=session,
                block_schema_reference=BlockSchemaReference(
                    parent_block_schema_id=parent_block_schema_id,
                    reference_block_schema_id=reference_block_schema.id,
                    name=reference_name,
                ),
            )


def _get_fields_for_child_schema(
    definitions: Dict,
    base_fields: Dict,
    reference_name: str,
    reference_block_type: orm_models.BlockType,
) -> Dict[str, Any]:
    """
    Returns the field definitions for a child schema. The fields definitions are pulled from the provided `definitions`
    dictionary based on the information extracted from `base_fields` using the `reference_name`. `reference_block_type`
    is used to disambiguate fields that have a union type.
    """
    from prefect.blocks.core import _collect_nested_reference_strings

    spec_reference = base_fields["properties"][reference_name]
    sub_block_schema_fields = None
    reference_strings = _collect_nested_reference_strings(spec_reference)
    if len(reference_strings) == 1:
        sub_block_schema_fields = definitions.get(
            reference_strings[0].replace("#/definitions/", "")
        )
    else:
        for reference_string in reference_strings:
            definition_key = reference_string.replace("#/definitions/", "")
            potential_sub_block_schema_fields = definitions[definition_key]
            # Determines the definition to use when registering a child
            # block schema by verifying that the block type name stored in
            # the definition matches the name of the block type that we're
            # currently trying to register a block schema for.
            if (
                definitions[definition_key]["block_type_slug"]
                == reference_block_type.slug
            ):
                # Once we've found the matching definition, we no longer
                # need to iterate
                sub_block_schema_fields = potential_sub_block_schema_fields
                break
    return sub_block_schema_fields  # type: ignore


async def delete_block_schema(session: AsyncSession, block_schema_id: UUID) -> bool:
    """
    Delete a block schema by id.

    Args:
        session: A database session
        block_schema_id: a block schema id

    Returns:
        bool: whether or not the block schema was deleted
    """

    result = await session.execute(
        delete(orm_models.BlockSchema).where(
            orm_models.BlockSchema.id == block_schema_id
        )
    )
    return result.rowcount > 0


async def read_block_schema(
    session: AsyncSession,
    block_schema_id: UUID,
) -> Union[BlockSchema, None]:
    """
    Reads a block schema by id. Will reconstruct the block schema's fields attribute
    to include block schema references.

    Args:
        session: A database session
        block_schema_id: a block_schema id

    Returns:
        orm_models..BlockSchema: the block_schema
    """

    # Construction of a recursive query which returns the specified block schema
    # along with and nested block schemas coupled with the ID of their parent schema
    # the key that they reside under.
    block_schema_references_query = (
        sa.select(orm_models.BlockSchemaReference)
        .select_from(orm_models.BlockSchemaReference)
        .filter_by(parent_block_schema_id=block_schema_id)
        .cte("block_schema_references", recursive=True)
    )
    block_schema_references_join = (
        sa.select(orm_models.BlockSchemaReference)
        .select_from(orm_models.BlockSchemaReference)
        .join(
            block_schema_references_query,
            orm_models.BlockSchemaReference.parent_block_schema_id
            == block_schema_references_query.c.reference_block_schema_id,
        )
    )
    recursive_block_schema_references_cte = block_schema_references_query.union_all(
        block_schema_references_join
    )
    nested_block_schemas_query = (
        sa.select(
            orm_models.BlockSchema,
            recursive_block_schema_references_cte.c.name,
            recursive_block_schema_references_cte.c.parent_block_schema_id,
        )
        .select_from(orm_models.BlockSchema)
        .join(
            recursive_block_schema_references_cte,
            orm_models.BlockSchema.id
            == recursive_block_schema_references_cte.c.reference_block_schema_id,
            isouter=True,
        )
        .filter(
            sa.or_(
                orm_models.BlockSchema.id == block_schema_id,
                recursive_block_schema_references_cte.c.parent_block_schema_id.is_not(
                    None
                ),
            )
        )
    )
    result = await session.execute(nested_block_schemas_query)

    return _construct_full_block_schema(result.all())  # type: ignore[arg-type]


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
        copy(root_block_schema)
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
    # Definitions for non block object may already exist in the block schema OpenAPI
    # spec, so we need to combine block and non-block definitions.
    if definitions or root_block_schema.fields.get("definitions"):
        root_block_schema.fields["definitions"] = {
            **root_block_schema.fields.get("definitions", {}),
            **definitions,
        }
    return root_block_schema


def _find_root_block_schema(
    block_schemas_with_references: List[
        Tuple[BlockSchema, Optional[str], Optional[UUID]]
    ],
) -> Union[BlockSchema, None]:
    """
    Attempts to find the root block schema from a list of block schemas
    with references. Returns None if a root block schema is not found.
    Returns only the first potential root block schema if multiple are found.
    """
    return next(
        (
            copy(block_schema)
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
    root_block_schema: BlockSchema,
    block_schemas_with_references: List[
        Tuple[BlockSchema, Optional[str], Optional[UUID]]
    ],
) -> Dict[str, Any]:
    """
    Constructs field definitions for a block schema based on the nested block schemas
    as defined in the block_schemas_with_references list.
    """
    definitions: dict[str, Any] = {}
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
                    block_schemas_with_references=block_schemas_with_references,
                    root_block_schema=child_block_schema,
                )
                assert child_block_schema
                definitions = _add_block_schemas_fields_to_definitions(
                    definitions, child_block_schema
                )
    return definitions


def _find_block_schema_via_checksum(
    block_schemas_with_references: List[
        Tuple[BlockSchema, Optional[str], Optional[UUID]]
    ],
    checksum: str,
) -> Optional[BlockSchema]:
    """Attempt to find a block schema via a given checksum. Returns None if not found."""
    return next(
        (
            block_schema
            for block_schema, _, _ in block_schemas_with_references
            if block_schema.checksum == checksum
        ),
        None,
    )


def _add_block_schemas_fields_to_definitions(
    definitions: Dict, child_block_schema: BlockSchema
) -> Dict[str, Any]:
    """
    Returns a new definitions dict with the fields of a block schema and it's child
    block schemas added to the existing definitions.
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
) -> Dict[str, Any]:
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
            assert (
                nested_block_schema.block_type
            ), f"{nested_block_schema} has no block type"

            new_block_schema_reference = {
                "block_schema_checksum": nested_block_schema.checksum,
                "block_type_slug": nested_block_schema.block_type.slug,
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


async def read_block_schemas(
    session: AsyncSession,
    block_schema_filter: Optional[schemas.filters.BlockSchemaFilter] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> List[BlockSchema]:
    """
    Reads block schemas, optionally filtered by type or name.

    Args:
        session: A database session
        block_schema_filter: a block schema filter object
        limit (int): query limit
        offset (int): query offset

    Returns:
        List[orm_models.BlockSchema]: the block_schemas
    """
    # schemas are ordered by `created DESC` to get the most recently created
    # ones first (and to facilitate getting the newest one with `limit=1`).
    filtered_block_schemas_query = select(orm_models.BlockSchema.id).order_by(
        orm_models.BlockSchema.created.desc()
    )

    if block_schema_filter:
        filtered_block_schemas_query = filtered_block_schemas_query.where(
            block_schema_filter.as_sql_filter()
        )

    if offset is not None:
        filtered_block_schemas_query = filtered_block_schemas_query.offset(offset)
    if limit is not None:
        filtered_block_schemas_query = filtered_block_schemas_query.limit(limit)

    filtered_block_schema_ids = (
        (await session.execute(filtered_block_schemas_query)).scalars().unique().all()
    )

    block_schema_references_query = (
        sa.select(orm_models.BlockSchemaReference)
        .select_from(orm_models.BlockSchemaReference)
        .filter(
            orm_models.BlockSchemaReference.parent_block_schema_id.in_(
                filtered_block_schemas_query
            )
        )
        .cte("block_schema_references", recursive=True)
    )
    block_schema_references_join = (
        sa.select(orm_models.BlockSchemaReference)
        .select_from(orm_models.BlockSchemaReference)
        .join(
            block_schema_references_query,
            orm_models.BlockSchemaReference.parent_block_schema_id
            == block_schema_references_query.c.reference_block_schema_id,
        )
    )
    recursive_block_schema_references_cte = block_schema_references_query.union_all(
        block_schema_references_join
    )

    nested_block_schemas_query = (
        sa.select(
            orm_models.BlockSchema,
            recursive_block_schema_references_cte.c.name,
            recursive_block_schema_references_cte.c.parent_block_schema_id,
        )
        .select_from(orm_models.BlockSchema)
        # in order to reconstruct nested block schemas efficiently, we need to visit them
        # in the order they were created (so that we guarantee that nested/referenced schemas)
        # have already been seen. Therefore this second query sorts by created ASC
        .order_by(orm_models.BlockSchema.created.asc())
        .join(
            recursive_block_schema_references_cte,
            orm_models.BlockSchema.id
            == recursive_block_schema_references_cte.c.reference_block_schema_id,
            isouter=True,
        )
        .filter(
            sa.or_(
                orm_models.BlockSchema.id.in_(filtered_block_schemas_query),
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
            constructed = _construct_full_block_schema(
                block_schemas_with_references=block_schemas_with_references,  # type: ignore[arg-type]
                root_block_schema=root_block_schema,
            )
            assert constructed
            fully_constructed_block_schemas.append(constructed)
            visited_block_schema_ids.append(root_block_schema.id)

    # because we reconstructed schemas ordered by created ASC, we
    # reverse the final output to restore created DESC
    return list(reversed(fully_constructed_block_schemas))


async def read_block_schema_by_checksum(
    session: AsyncSession,
    checksum: str,
    version: Optional[str] = None,
) -> Optional[BlockSchema]:
    """
    Reads a block_schema by checksum. Will reconstruct the block schema's fields
    attribute to include block schema references.

    Args:
        session: A database session
        checksum: a block_schema checksum
        version: A block_schema version

    Returns:
        orm_models.BlockSchema: the block_schema
    """
    # Construction of a recursive query which returns the specified block schema
    # along with and nested block schemas coupled with the ID of their parent schema
    # the key that they reside under.

    # The same checksum with different versions can occur in the DB. Return only the
    # most recently created one.
    root_block_schema_query = (
        sa.select(orm_models.BlockSchema)
        .filter_by(checksum=checksum)
        .order_by(orm_models.BlockSchema.created.desc())
        .limit(1)
    )

    if version is not None:
        root_block_schema_query = root_block_schema_query.filter_by(version=version)

    root_block_schema_cte = root_block_schema_query.cte("root_block_schema")

    block_schema_references_query = (
        sa.select(orm_models.BlockSchemaReference)
        .select_from(orm_models.BlockSchemaReference)
        .filter_by(parent_block_schema_id=root_block_schema_cte.c.id)
        .cte("block_schema_references", recursive=True)
    )
    block_schema_references_join = (
        sa.select(orm_models.BlockSchemaReference)
        .select_from(orm_models.BlockSchemaReference)
        .join(
            block_schema_references_query,
            orm_models.BlockSchemaReference.parent_block_schema_id
            == block_schema_references_query.c.reference_block_schema_id,
        )
    )
    recursive_block_schema_references_cte = block_schema_references_query.union_all(
        block_schema_references_join
    )
    nested_block_schemas_query = (
        sa.select(
            orm_models.BlockSchema,
            recursive_block_schema_references_cte.c.name,
            recursive_block_schema_references_cte.c.parent_block_schema_id,
        )
        .select_from(orm_models.BlockSchema)
        .join(
            recursive_block_schema_references_cte,
            orm_models.BlockSchema.id
            == recursive_block_schema_references_cte.c.reference_block_schema_id,
            isouter=True,
        )
        .filter(
            sa.or_(
                orm_models.BlockSchema.id == root_block_schema_cte.c.id,
                recursive_block_schema_references_cte.c.parent_block_schema_id.is_not(
                    None
                ),
            )
        )
    )
    result = await session.execute(nested_block_schemas_query)
    return _construct_full_block_schema(result.all())  # type: ignore[arg-type]


@db_injector
async def read_available_block_capabilities(
    db: PrefectDBInterface,
    session: AsyncSession,
) -> List[str]:
    """
    Retrieves a list of all available block capabilities.

    Args:
        session: A database session.

    Returns:
        List[str]: List of all available block capabilities.
    """
    query = sa.select(
        db.json_arr_agg(db.cast_to_json(orm_models.BlockSchema.capabilities.distinct()))
    )
    capability_combinations = (await session.execute(query)).scalars().first() or list()
    if db.uses_json_strings and isinstance(capability_combinations, str):
        capability_combinations = json.loads(capability_combinations)
    return list({c for capabilities in capability_combinations for c in capabilities})


@db_injector
async def create_block_schema_reference(
    db: PrefectDBInterface,
    session: AsyncSession,
    block_schema_reference: schemas.core.BlockSchemaReference,
) -> Union[orm_models.BlockSchemaReference, None]:
    """
    Retrieves a list of all available block capabilities.

    Args:
        session: A database session.
        block_schema_reference: A block schema reference object.

    Returns:
        orm_models.BlockSchemaReference: The created BlockSchemaReference
    """
    query_stmt = sa.select(orm_models.BlockSchemaReference).where(
        orm_models.BlockSchemaReference.name == block_schema_reference.name,
        orm_models.BlockSchemaReference.parent_block_schema_id
        == block_schema_reference.parent_block_schema_id,
        orm_models.BlockSchemaReference.reference_block_schema_id
        == block_schema_reference.reference_block_schema_id,
    )

    existing_reference = (await session.execute(query_stmt)).scalar()
    if existing_reference:
        return existing_reference

    insert_stmt = db.insert(orm_models.BlockSchemaReference).values(
        **block_schema_reference.model_dump_for_orm(
            exclude_unset=True, exclude={"created", "updated"}
        )
    )
    await session.execute(insert_stmt)

    result = await session.execute(
        sa.select(orm_models.BlockSchemaReference).where(
            orm_models.BlockSchemaReference.id == block_schema_reference.id
        )
    )
    return result.scalar()
