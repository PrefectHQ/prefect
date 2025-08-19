from __future__ import annotations

import uuid
from typing import Any, cast

from typing_extensions import Self

from prefect.cli.transfer._exceptions import TransferSkipped
from prefect.cli.transfer._migratable_resources import construct_migratable_resource
from prefect.cli.transfer._migratable_resources.base import (
    MigratableProtocol,
    MigratableResource,
)
from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import (
    BlockDocumentCreate,
    BlockSchemaCreate,
    BlockTypeCreate,
)
from prefect.client.schemas.objects import (
    BlockDocument,
    BlockSchema,
    BlockType,
)
from prefect.exceptions import (
    ObjectAlreadyExists,
)


class MigratableBlockType(MigratableResource[BlockType]):
    _instances: dict[uuid.UUID, Self] = {}

    def __init__(self, block_type: BlockType):
        self.source_block_type = block_type
        self.destination_block_type: BlockType | None = None

    @property
    def source_id(self) -> uuid.UUID:
        return self.source_block_type.id

    @property
    def destination_id(self) -> uuid.UUID | None:
        return self.destination_block_type.id if self.destination_block_type else None

    @classmethod
    async def construct(cls, obj: BlockType) -> Self:
        if obj.id in cls._instances:
            return cls._instances[obj.id]
        instance = cls(obj)
        cls._instances[obj.id] = instance
        return instance

    @classmethod
    async def get_instance(
        cls, id: uuid.UUID
    ) -> "MigratableResource[BlockType] | None":
        if id in cls._instances:
            return cls._instances[id]
        return None

    async def get_dependencies(self) -> "list[MigratableProtocol]":
        return []

    async def migrate(self) -> None:
        async with get_client() as client:
            try:
                block_type = await client.create_block_type(
                    block_type=BlockTypeCreate(
                        name=self.source_block_type.name,
                        slug=self.source_block_type.slug,
                    ),
                )
                self.destination_block_type = block_type
            except ObjectAlreadyExists:
                self.destination_block_type = await client.read_block_type_by_slug(
                    self.source_block_type.slug
                )
                raise TransferSkipped("Already exists")


class MigratableBlockSchema(MigratableResource[BlockSchema]):
    _instances: dict[uuid.UUID, Self] = {}

    def __init__(self, block_schema: BlockSchema):
        self.source_block_schema = block_schema
        self.destination_block_schema: BlockSchema | None = None
        self._dependencies: dict[uuid.UUID, MigratableProtocol] = {}

    @property
    def source_id(self) -> uuid.UUID:
        return self.source_block_schema.id

    @property
    def destination_id(self) -> uuid.UUID | None:
        return (
            self.destination_block_schema.id if self.destination_block_schema else None
        )

    @classmethod
    async def construct(cls, obj: BlockSchema) -> Self:
        if obj.id in cls._instances:
            return cls._instances[obj.id]
        instance = cls(obj)
        cls._instances[obj.id] = instance
        return instance

    @classmethod
    async def get_instance(
        cls, id: uuid.UUID
    ) -> "MigratableResource[BlockSchema] | None":
        if id in cls._instances:
            return cls._instances[id]
        return None

    async def get_dependencies(self) -> "list[MigratableProtocol]":
        if self._dependencies:
            return list(self._dependencies.values())

        async with get_client() as client:
            if self.source_block_schema.block_type is not None:
                if dependency := await MigratableBlockType.get_instance(
                    id=self.source_block_schema.block_type.id
                ):
                    self._dependencies[self.source_block_schema.block_type.id] = (
                        dependency
                    )
                else:
                    self._dependencies[
                        self.source_block_schema.block_type.id
                    ] = await construct_migratable_resource(
                        self.source_block_schema.block_type
                    )
            elif self.source_block_schema.block_type_id is not None:
                if dependency := await MigratableBlockType.get_instance(
                    id=self.source_block_schema.block_type_id
                ):
                    self._dependencies[self.source_block_schema.block_type_id] = (
                        dependency
                    )
                else:
                    response = await client.request(
                        "GET",
                        "/block_types/{id}",
                        params={"id": self.source_block_schema.block_type_id},
                    )
                    block_type = BlockType.model_validate(response.json())
                    self._dependencies[
                        block_type.id
                    ] = await construct_migratable_resource(block_type)
            else:
                raise ValueError("Block schema has no associated block type")

            block_schema_references: dict[str, dict[str, Any]] = (
                self.source_block_schema.fields.get("block_schema_references", {})
            )
            for block_schema_reference in block_schema_references.values():
                if isinstance(block_schema_reference, list):
                    for nested_block_schema_reference in block_schema_reference:
                        if block_schema_checksum := cast(
                            dict[str, str], nested_block_schema_reference
                        ).get("block_schema_checksum"):
                            block_schema = await client.read_block_schema_by_checksum(
                                block_schema_checksum
                            )
                            if dependency := await MigratableBlockSchema.get_instance(
                                id=block_schema.id
                            ):
                                self._dependencies[block_schema.id] = dependency
                            else:
                                self._dependencies[
                                    block_schema.id
                                ] = await construct_migratable_resource(block_schema)
                else:
                    if block_schema_checksum := block_schema_reference.get(
                        "block_schema_checksum"
                    ):
                        block_schema = await client.read_block_schema_by_checksum(
                            block_schema_checksum
                        )
                        if dependency := await MigratableBlockSchema.get_instance(
                            id=block_schema.id
                        ):
                            self._dependencies[block_schema.id] = dependency
                        else:
                            self._dependencies[
                                block_schema.id
                            ] = await construct_migratable_resource(block_schema)

        return list(self._dependencies.values())

    async def migrate(self) -> None:
        if self.source_block_schema.block_type_id is None:
            raise ValueError("Block schema has no associated block type")
        if (
            destination_block_type := self._dependencies.get(
                self.source_block_schema.block_type_id
            )
        ) is None:
            raise ValueError("Unable to find destination block type")
        async with get_client() as client:
            try:
                self.destination_block_schema = await client.create_block_schema(
                    block_schema=BlockSchemaCreate(
                        fields=self.source_block_schema.fields,
                        block_type_id=destination_block_type.destination_id,
                        capabilities=self.source_block_schema.capabilities,
                        version=self.source_block_schema.version,
                    ),
                )
            except ObjectAlreadyExists:
                self.destination_block_schema = (
                    await client.read_block_schema_by_checksum(
                        self.source_block_schema.checksum
                    )
                )
                raise TransferSkipped("Already exists")


class MigratableBlockDocument(MigratableResource[BlockDocument]):
    _instances: dict[uuid.UUID, Self] = {}

    def __init__(self, block_document: BlockDocument):
        self.source_block_document = block_document
        self.destination_block_document: BlockDocument | None = None
        self._dependencies: dict[uuid.UUID, MigratableProtocol] = {}

    @property
    def source_id(self) -> uuid.UUID:
        return self.source_block_document.id

    @property
    def destination_id(self) -> uuid.UUID | None:
        return (
            self.destination_block_document.id
            if self.destination_block_document
            else None
        )

    @classmethod
    async def construct(cls, obj: BlockDocument) -> Self:
        if obj.id in cls._instances:
            return cls._instances[obj.id]
        instance = cls(obj)
        cls._instances[obj.id] = instance
        return instance

    @classmethod
    async def get_instance(
        cls, id: uuid.UUID
    ) -> "MigratableResource[BlockDocument] | None":
        if id in cls._instances:
            return cls._instances[id]
        return None

    async def get_dependencies(self) -> "list[MigratableProtocol]":
        if self._dependencies:
            return list(self._dependencies.values())

        # TODO: When we write serialized versions of the objects to disk, we should have a way to
        # use a client, but read from disk if the object has already been fetched.
        async with get_client() as client:
            if self.source_block_document.block_type is not None:
                if dependency := await MigratableBlockType.get_instance(
                    id=self.source_block_document.block_type.id
                ):
                    self._dependencies[self.source_block_document.block_type.id] = (
                        dependency
                    )
                else:
                    self._dependencies[
                        self.source_block_document.block_type.id
                    ] = await construct_migratable_resource(
                        self.source_block_document.block_type
                    )
            else:
                if dependency := await MigratableBlockType.get_instance(
                    id=self.source_block_document.block_type_id
                ):
                    self._dependencies[self.source_block_document.block_type_id] = (
                        dependency
                    )
                else:
                    response = await client.request(
                        "GET",
                        "/block_types/{id}",
                        params={"id": self.source_block_document.block_type_id},
                    )
                    block_type = BlockType.model_validate(response.json())
                    self._dependencies[
                        block_type.id
                    ] = await construct_migratable_resource(block_type)

            if self.source_block_document.block_schema is not None:
                if dependency := await MigratableBlockSchema.get_instance(
                    id=self.source_block_document.block_schema.id
                ):
                    self._dependencies[self.source_block_document.block_schema.id] = (
                        dependency
                    )
                else:
                    self._dependencies[
                        self.source_block_document.block_schema.id
                    ] = await construct_migratable_resource(
                        self.source_block_document.block_schema
                    )
            else:
                if dependency := await MigratableBlockSchema.get_instance(
                    id=self.source_block_document.block_schema_id
                ):
                    self._dependencies[self.source_block_document.block_schema_id] = (
                        dependency
                    )
                else:
                    response = await client.request(
                        "GET",
                        "/block_schemas/{id}",
                        params={"id": self.source_block_document.block_schema_id},
                    )
                    block_schema = BlockSchema.model_validate(response.json())
                    self._dependencies[
                        block_schema.id
                    ] = await construct_migratable_resource(block_schema)

            if self.source_block_document.block_document_references:
                for (
                    block_document_reference
                ) in self.source_block_document.block_document_references.values():
                    if block_document_id := block_document_reference.get(
                        "block_document_id"
                    ):
                        if dependency := await MigratableBlockDocument.get_instance(
                            id=block_document_id
                        ):
                            self._dependencies[block_document_id] = dependency
                        else:
                            block_document = await client.read_block_document(
                                block_document_id
                            )
                            self._dependencies[
                                block_document.id
                            ] = await construct_migratable_resource(block_document)

        return list(self._dependencies.values())

    async def migrate(self) -> None:
        if (
            destination_block_type := self._dependencies.get(
                self.source_block_document.block_type_id
            )
        ) is None or not destination_block_type.destination_id:
            raise ValueError("Unable to find destination block type")
        if (
            destination_block_schema := self._dependencies.get(
                self.source_block_document.block_schema_id
            )
        ) is None or not destination_block_schema.destination_id:
            raise ValueError("Unable to find destination block schema")

        async with get_client() as client:
            try:
                # TODO: Check if data needs to be written differently to maintain composition
                self.destination_block_document = await client.create_block_document(
                    block_document=BlockDocumentCreate(
                        name=self.source_block_document.name,
                        block_type_id=destination_block_type.destination_id,
                        block_schema_id=destination_block_schema.destination_id,
                        data=self.source_block_document.data,
                    ),
                )
            except ObjectAlreadyExists:
                if self.source_block_document.name is None:
                    # This is technically impossible, but our typing thinks it's possible
                    raise ValueError(
                        "Block document has no name, which should be impossible. "
                        "Please report this as a bug."
                    )

                if self.source_block_document.block_type is not None:
                    block_type_slug = self.source_block_document.block_type.slug
                else:
                    # TODO: Add real client methods for places where we use `client.request`
                    response = await client.request(
                        "GET",
                        "/block_types/{id}",
                        params={"id": self.source_block_document.block_type_id},
                    )
                    block_type = BlockType.model_validate(response.json())
                    block_type_slug = block_type.slug

                self.destination_block_document = (
                    await client.read_block_document_by_name(
                        block_type_slug=block_type_slug,
                        name=self.source_block_document.name,
                    )
                )
                raise TransferSkipped("Already exists")
