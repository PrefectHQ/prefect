import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from prefect.cli.transfer._exceptions import TransferSkipped
from prefect.cli.transfer._migratable_resources.blocks import (
    MigratableBlockDocument,
    MigratableBlockSchema,
    MigratableBlockType,
)
from prefect.client.schemas.actions import (
    BlockDocumentCreate,
    BlockSchemaCreate,
    BlockTypeCreate,
)
from prefect.client.schemas.objects import BlockDocument, BlockSchema, BlockType
from prefect.exceptions import ObjectAlreadyExists


class TestMigratableBlockType:
    async def test_construct_creates_new_instance(
        self, transfer_block_type_x: BlockType
    ):
        """Test that construct creates a new MigratableBlockType instance."""
        migratable = await MigratableBlockType.construct(transfer_block_type_x)

        assert isinstance(migratable, MigratableBlockType)
        assert migratable.source_block_type == transfer_block_type_x
        assert migratable.source_id == transfer_block_type_x.id
        assert migratable.destination_block_type is None
        assert migratable.destination_id is None

    async def test_construct_returns_cached_instance(
        self, transfer_block_type_x: BlockType
    ):
        """Test that construct returns cached instance for same ID."""
        # Clear any existing instances
        MigratableBlockType._instances.clear()

        # Create first instance
        migratable1 = await MigratableBlockType.construct(transfer_block_type_x)

        # Create second instance with same block type
        migratable2 = await MigratableBlockType.construct(transfer_block_type_x)

        # Should be the same instance
        assert migratable1 is migratable2
        assert len(MigratableBlockType._instances) == 1

    async def test_get_instance_returns_cached_instance(
        self, transfer_block_type_x: BlockType
    ):
        """Test that get_instance returns cached instance."""
        # Clear any existing instances
        MigratableBlockType._instances.clear()

        # Create instance
        migratable = await MigratableBlockType.construct(transfer_block_type_x)

        # Retrieve instance
        retrieved = await MigratableBlockType.get_instance(transfer_block_type_x.id)

        assert retrieved is migratable

    async def test_get_instance_returns_none_for_unknown_id(self):
        """Test that get_instance returns None for unknown ID."""
        # Clear any existing instances
        MigratableBlockType._instances.clear()

        unknown_id = uuid.uuid4()
        retrieved = await MigratableBlockType.get_instance(unknown_id)

        assert retrieved is None

    async def test_get_dependencies_returns_empty_list(
        self, transfer_block_type_x: BlockType
    ):
        """Test that get_dependencies returns empty list (block types have no dependencies)."""
        migratable = await MigratableBlockType.construct(transfer_block_type_x)
        dependencies = await migratable.get_dependencies()

        assert dependencies == []

    @patch("prefect.cli.transfer._migratable_resources.blocks.get_client")
    async def test_migrate_success(
        self, mock_get_client: MagicMock, transfer_block_type_x: BlockType
    ):
        """Test successful block type migration."""
        # Mock the client
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        # Mock successful creation
        destination_block_type = BlockType(
            id=uuid.uuid4(),
            name=transfer_block_type_x.name,
            slug=transfer_block_type_x.slug,
            logo_url=transfer_block_type_x.logo_url,
            documentation_url=transfer_block_type_x.documentation_url,
            description=transfer_block_type_x.description,
            code_example=transfer_block_type_x.code_example,
            is_protected=transfer_block_type_x.is_protected,
            created=transfer_block_type_x.created,
            updated=transfer_block_type_x.updated,
        )
        mock_client.create_block_type.return_value = destination_block_type

        migratable = await MigratableBlockType.construct(transfer_block_type_x)
        await migratable.migrate()

        # Verify client was called correctly
        mock_client.create_block_type.assert_called_once_with(
            block_type=BlockTypeCreate(
                name=transfer_block_type_x.name,
                slug=transfer_block_type_x.slug,
            )
        )

        # Verify destination_block_type is set
        assert migratable.destination_block_type == destination_block_type
        assert migratable.destination_id == destination_block_type.id

    @patch("prefect.cli.transfer._migratable_resources.blocks.get_client")
    async def test_migrate_already_exists(
        self, mock_get_client: MagicMock, transfer_block_type_x: BlockType
    ):
        """Test migration when block type already exists."""
        # Mock the client
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        # Mock ObjectAlreadyExists exception on create
        mock_http_exc = Exception("Conflict")
        mock_client.create_block_type.side_effect = ObjectAlreadyExists(mock_http_exc)

        # Mock successful read of existing block type
        existing_block_type = BlockType(
            id=uuid.uuid4(),
            name=transfer_block_type_x.name,
            slug=transfer_block_type_x.slug,
            logo_url="https://example.com/existing-logo.png",  # Different to show it reads existing
            documentation_url=transfer_block_type_x.documentation_url,
            description="existing description",
            code_example=transfer_block_type_x.code_example,
            is_protected=transfer_block_type_x.is_protected,
            created=transfer_block_type_x.created,
            updated=transfer_block_type_x.updated,
        )
        mock_client.read_block_type_by_slug.return_value = existing_block_type

        migratable = await MigratableBlockType.construct(transfer_block_type_x)

        # Should raise TransferSkipped
        with pytest.raises(TransferSkipped, match="Already exists"):
            await migratable.migrate()

        # Verify client calls
        mock_client.create_block_type.assert_called_once()
        mock_client.read_block_type_by_slug.assert_called_once_with(
            transfer_block_type_x.slug
        )

        # Verify destination_block_type is set to existing
        assert migratable.destination_block_type == existing_block_type
        assert migratable.destination_id == existing_block_type.id


class TestMigratableBlockSchema:
    async def test_construct_creates_new_instance(
        self, transfer_block_schema: BlockSchema
    ):
        """Test that construct creates a new MigratableBlockSchema instance."""
        migratable = await MigratableBlockSchema.construct(transfer_block_schema)

        assert isinstance(migratable, MigratableBlockSchema)
        assert migratable.source_block_schema == transfer_block_schema
        assert migratable.source_id == transfer_block_schema.id
        assert migratable.destination_block_schema is None
        assert migratable.destination_id is None
        assert migratable._dependencies == {}

    async def test_construct_returns_cached_instance(
        self, transfer_block_schema: BlockSchema
    ):
        """Test that construct returns cached instance for same ID."""
        # Clear any existing instances
        MigratableBlockSchema._instances.clear()

        # Create first instance
        migratable1 = await MigratableBlockSchema.construct(transfer_block_schema)

        # Create second instance with same block schema
        migratable2 = await MigratableBlockSchema.construct(transfer_block_schema)

        # Should be the same instance
        assert migratable1 is migratable2
        assert len(MigratableBlockSchema._instances) == 1

    async def test_get_instance_returns_cached_instance(
        self, transfer_block_schema: BlockSchema
    ):
        """Test that get_instance returns cached instance."""
        # Clear any existing instances
        MigratableBlockSchema._instances.clear()

        # Create instance
        migratable = await MigratableBlockSchema.construct(transfer_block_schema)

        # Retrieve instance
        retrieved = await MigratableBlockSchema.get_instance(transfer_block_schema.id)

        assert retrieved is migratable

    async def test_get_instance_returns_none_for_unknown_id(self):
        """Test that get_instance returns None for unknown ID."""
        # Clear any existing instances
        MigratableBlockSchema._instances.clear()

        unknown_id = uuid.uuid4()
        retrieved = await MigratableBlockSchema.get_instance(unknown_id)

        assert retrieved is None

    @patch(
        "prefect.cli.transfer._migratable_resources.blocks.construct_migratable_resource"
    )
    async def test_get_dependencies_with_block_type(
        self, mock_construct_resource: AsyncMock, transfer_block_schema: BlockSchema
    ):
        """Test get_dependencies with block_type present."""
        mock_migratable_block_type = MagicMock()
        mock_construct_resource.return_value = mock_migratable_block_type

        migratable = await MigratableBlockSchema.construct(transfer_block_schema)
        dependencies = await migratable.get_dependencies()

        assert len(dependencies) == 1
        assert dependencies[0] == mock_migratable_block_type
        assert transfer_block_schema.block_type.id in migratable._dependencies
        mock_construct_resource.assert_called_once_with(
            transfer_block_schema.block_type
        )

    @patch("prefect.cli.transfer._migratable_resources.blocks.get_client")
    @patch(
        "prefect.cli.transfer._migratable_resources.blocks.construct_migratable_resource"
    )
    async def test_get_dependencies_with_block_type_id_only(
        self, mock_construct_resource: AsyncMock, mock_get_client: MagicMock
    ):
        """Test get_dependencies with only block_type_id."""
        block_type_id = uuid.uuid4()
        block_schema = BlockSchema(
            id=uuid.uuid4(),
            checksum="test-checksum",
            fields={"type": "object"},
            block_type_id=block_type_id,
            block_type=None,  # No block_type object
            capabilities=[],
            version="1.0.0",
        )

        # Mock the client and response
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        mock_response = MagicMock()
        block_type = BlockType(
            id=block_type_id,
            name="test-block-type",
            slug="test-block-type",
            logo_url=None,
            documentation_url=None,
            description=None,
            code_example=None,
            is_protected=False,
        )
        mock_response.json.return_value = block_type.model_dump()
        mock_client.request.return_value = mock_response

        mock_migratable_block_type = MagicMock()
        mock_construct_resource.return_value = mock_migratable_block_type

        migratable = await MigratableBlockSchema.construct(block_schema)
        dependencies = await migratable.get_dependencies()

        assert len(dependencies) == 1
        assert dependencies[0] == mock_migratable_block_type
        assert block_type_id in migratable._dependencies
        mock_client.request.assert_called_once_with(
            "GET", "/block_types/{id}", params={"id": block_type_id}
        )

    async def test_get_dependencies_no_block_type_raises_error(self):
        """Test get_dependencies raises error when no block type."""
        block_schema = BlockSchema(
            id=uuid.uuid4(),
            checksum="test-checksum",
            fields={"type": "object"},
            block_type_id=None,
            block_type=None,
            capabilities=[],
            version="1.0.0",
        )

        migratable = await MigratableBlockSchema.construct(block_schema)

        with pytest.raises(
            ValueError, match="Block schema has no associated block type"
        ):
            await migratable.get_dependencies()

    @patch("prefect.cli.transfer._migratable_resources.blocks.get_client")
    async def test_migrate_success(
        self, mock_get_client: MagicMock, transfer_block_schema: BlockSchema
    ):
        """Test successful block schema migration."""
        # Mock the client
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        # Mock dependency
        mock_dependency = MagicMock()
        destination_block_type_id = uuid.uuid4()
        mock_dependency.destination_id = destination_block_type_id

        migratable = await MigratableBlockSchema.construct(transfer_block_schema)
        # Set up the dependency manually
        migratable._dependencies[transfer_block_schema.block_type_id] = mock_dependency

        # Mock successful creation
        destination_block_schema = BlockSchema(
            id=uuid.uuid4(),
            checksum=transfer_block_schema.checksum,
            fields=transfer_block_schema.fields,
            block_type_id=destination_block_type_id,
            block_type=None,
            capabilities=transfer_block_schema.capabilities,
            version=transfer_block_schema.version,
            created=transfer_block_schema.created,
            updated=transfer_block_schema.updated,
        )
        mock_client.create_block_schema.return_value = destination_block_schema

        await migratable.migrate()

        # Verify client was called correctly
        mock_client.create_block_schema.assert_called_once_with(
            block_schema=BlockSchemaCreate(
                fields=transfer_block_schema.fields,
                block_type_id=destination_block_type_id,
                capabilities=transfer_block_schema.capabilities,
                version=transfer_block_schema.version,
            )
        )

        # Verify destination_block_schema is set
        assert migratable.destination_block_schema == destination_block_schema
        assert migratable.destination_id == destination_block_schema.id

    @patch("prefect.cli.transfer._migratable_resources.blocks.get_client")
    async def test_migrate_already_exists(
        self, mock_get_client: MagicMock, transfer_block_schema: BlockSchema
    ):
        """Test migration when block schema already exists."""
        # Mock the client
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        # Mock dependency
        mock_dependency = MagicMock()
        destination_block_type_id = uuid.uuid4()
        mock_dependency.destination_id = destination_block_type_id

        migratable = await MigratableBlockSchema.construct(transfer_block_schema)
        migratable._dependencies[transfer_block_schema.block_type_id] = mock_dependency

        # Mock ObjectAlreadyExists exception on create
        mock_http_exc = Exception("Conflict")
        mock_client.create_block_schema.side_effect = ObjectAlreadyExists(mock_http_exc)

        # Mock successful read of existing block schema
        existing_block_schema = BlockSchema(
            id=uuid.uuid4(),
            checksum=transfer_block_schema.checksum,
            fields={"different": "fields"},  # Different to show it reads existing
            block_type_id=destination_block_type_id,
            block_type=None,
            capabilities=transfer_block_schema.capabilities,
            version=transfer_block_schema.version,
            created=transfer_block_schema.created,
            updated=transfer_block_schema.updated,
        )
        mock_client.read_block_schema_by_checksum.return_value = existing_block_schema

        # Should raise TransferSkipped
        with pytest.raises(TransferSkipped, match="Already exists"):
            await migratable.migrate()

        # Verify client calls
        mock_client.create_block_schema.assert_called_once()
        mock_client.read_block_schema_by_checksum.assert_called_once_with(
            transfer_block_schema.checksum
        )

        # Verify destination_block_schema is set to existing
        assert migratable.destination_block_schema == existing_block_schema
        assert migratable.destination_id == existing_block_schema.id

    async def test_migrate_no_block_type_raises_error(
        self, transfer_block_schema: BlockSchema
    ):
        """Test migrate raises error when no block type ID."""
        transfer_block_schema.block_type_id = None
        migratable = await MigratableBlockSchema.construct(transfer_block_schema)

        with pytest.raises(
            ValueError, match="Block schema has no associated block type"
        ):
            await migratable.migrate()


class TestMigratableBlockDocument:
    async def test_construct_creates_new_instance(
        self, transfer_block_document: BlockDocument
    ):
        """Test that construct creates a new MigratableBlockDocument instance."""
        migratable = await MigratableBlockDocument.construct(transfer_block_document)

        assert isinstance(migratable, MigratableBlockDocument)
        assert migratable.source_block_document == transfer_block_document
        assert migratable.source_id == transfer_block_document.id
        assert migratable.destination_block_document is None
        assert migratable.destination_id is None
        assert migratable._dependencies == {}

    async def test_construct_returns_cached_instance(
        self, transfer_block_document: BlockDocument
    ):
        """Test that construct returns cached instance for same ID."""
        # Clear any existing instances
        MigratableBlockDocument._instances.clear()

        # Create first instance
        migratable1 = await MigratableBlockDocument.construct(transfer_block_document)

        # Create second instance with same block document
        migratable2 = await MigratableBlockDocument.construct(transfer_block_document)

        # Should be the same instance
        assert migratable1 is migratable2
        assert len(MigratableBlockDocument._instances) == 1

    async def test_get_instance_returns_cached_instance(
        self, transfer_block_document: BlockDocument
    ):
        """Test that get_instance returns cached instance."""
        # Clear any existing instances
        MigratableBlockDocument._instances.clear()

        # Create instance
        migratable = await MigratableBlockDocument.construct(transfer_block_document)

        # Retrieve instance
        retrieved = await MigratableBlockDocument.get_instance(
            transfer_block_document.id
        )

        assert retrieved is migratable

    async def test_get_instance_returns_none_for_unknown_id(self):
        """Test that get_instance returns None for unknown ID."""
        # Clear any existing instances
        MigratableBlockDocument._instances.clear()

        unknown_id = uuid.uuid4()
        retrieved = await MigratableBlockDocument.get_instance(unknown_id)

        assert retrieved is None

    @patch(
        "prefect.cli.transfer._migratable_resources.blocks.construct_migratable_resource"
    )
    async def test_get_dependencies_with_block_type_and_schema(
        self, mock_construct_resource: AsyncMock, transfer_block_document: BlockDocument
    ):
        """Test get_dependencies with block_type and block_schema present."""
        mock_migratable_block_type = MagicMock()
        mock_migratable_block_schema = MagicMock()
        mock_construct_resource.side_effect = [
            mock_migratable_block_type,
            mock_migratable_block_schema,
        ]

        migratable = await MigratableBlockDocument.construct(transfer_block_document)
        dependencies = await migratable.get_dependencies()

        assert len(dependencies) == 2
        assert mock_migratable_block_type in dependencies
        assert mock_migratable_block_schema in dependencies
        assert transfer_block_document.block_type.id in migratable._dependencies
        assert transfer_block_document.block_schema.id in migratable._dependencies

    @patch("prefect.cli.transfer._migratable_resources.blocks.get_client")
    @patch(
        "prefect.cli.transfer._migratable_resources.blocks.construct_migratable_resource"
    )
    async def test_get_dependencies_with_document_references(
        self, mock_construct_resource: AsyncMock, mock_get_client: MagicMock
    ):
        """Test get_dependencies with block document references."""
        referenced_doc_id = uuid.uuid4()
        block_document = BlockDocument(
            id=uuid.uuid4(),
            name="test-block",
            data={"foo": "bar"},
            block_schema_id=uuid.uuid4(),
            block_schema=None,
            block_type_id=uuid.uuid4(),
            block_type=None,
            block_document_references={
                "ref1": {"block_document_id": str(referenced_doc_id)}
            },
            is_anonymous=False,
        )

        # Mock the client
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        # Mock referenced block document
        mock_referenced_doc = MagicMock()
        mock_referenced_doc.id = referenced_doc_id
        mock_client.read_block_document.return_value = mock_referenced_doc

        # Mock migratable resources
        mock_migratable_block_type = MagicMock()
        mock_migratable_block_schema = MagicMock()
        mock_migratable_referenced_doc = MagicMock()

        # Mock responses for block type and schema
        mock_type_response = MagicMock()
        mock_type_response.json.return_value = {
            "id": str(block_document.block_type_id),
            "name": "test-block-type",
            "slug": "test-block-type",
            "logo_url": None,
            "documentation_url": None,
            "description": None,
            "code_example": None,
            "is_protected": False,
            "created": "2023-01-01T00:00:00Z",
            "updated": "2023-01-01T00:00:00Z",
        }
        mock_schema_response = MagicMock()
        mock_schema_response.json.return_value = {
            "id": str(block_document.block_schema_id),
            "checksum": "test-checksum",
            "fields": {"type": "object"},
            "block_type_id": str(block_document.block_type_id),
            "capabilities": [],
            "version": "1.0.0",
            "created": "2023-01-01T00:00:00Z",
            "updated": "2023-01-01T00:00:00Z",
        }

        mock_client.request.side_effect = [mock_type_response, mock_schema_response]
        mock_construct_resource.side_effect = [
            mock_migratable_block_type,
            mock_migratable_block_schema,
            mock_migratable_referenced_doc,
        ]

        migratable = await MigratableBlockDocument.construct(block_document)
        dependencies = await migratable.get_dependencies()

        assert len(dependencies) == 3
        assert mock_migratable_block_type in dependencies
        assert mock_migratable_block_schema in dependencies
        assert mock_migratable_referenced_doc in dependencies
        assert referenced_doc_id in migratable._dependencies

    @patch("prefect.cli.transfer._migratable_resources.blocks.get_client")
    async def test_migrate_success(
        self, mock_get_client: MagicMock, transfer_block_document: BlockDocument
    ):
        """Test successful block document migration."""
        # Mock the client
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        # Mock dependencies
        mock_block_type_dependency = MagicMock()
        destination_block_type_id = uuid.uuid4()
        mock_block_type_dependency.destination_id = destination_block_type_id

        mock_block_schema_dependency = MagicMock()
        destination_block_schema_id = uuid.uuid4()
        mock_block_schema_dependency.destination_id = destination_block_schema_id

        migratable = await MigratableBlockDocument.construct(transfer_block_document)
        # Set up dependencies manually
        migratable._dependencies[transfer_block_document.block_type_id] = (
            mock_block_type_dependency
        )
        migratable._dependencies[transfer_block_document.block_schema_id] = (
            mock_block_schema_dependency
        )

        # Mock successful creation
        destination_block_document = BlockDocument(
            id=uuid.uuid4(),
            name=transfer_block_document.name,
            data=transfer_block_document.data,
            block_schema_id=destination_block_schema_id,
            block_schema=None,
            block_type_id=destination_block_type_id,
            block_type=None,
            block_document_references={},
            is_anonymous=transfer_block_document.is_anonymous,
            created=transfer_block_document.created,
            updated=transfer_block_document.updated,
        )
        mock_client.create_block_document.return_value = destination_block_document

        await migratable.migrate()

        # Verify client was called correctly
        mock_client.create_block_document.assert_called_once_with(
            block_document=BlockDocumentCreate(
                name=transfer_block_document.name,
                block_type_id=destination_block_type_id,
                block_schema_id=destination_block_schema_id,
                data=transfer_block_document.data,
            )
        )

        # Verify destination_block_document is set
        assert migratable.destination_block_document == destination_block_document
        assert migratable.destination_id == destination_block_document.id

    @patch("prefect.cli.transfer._migratable_resources.blocks.get_client")
    async def test_migrate_already_exists(
        self, mock_get_client: MagicMock, transfer_block_document: BlockDocument
    ):
        """Test migration when block document already exists."""
        # Mock the client
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        # Mock dependencies
        mock_block_type_dependency = MagicMock()
        destination_block_type_id = uuid.uuid4()
        mock_block_type_dependency.destination_id = destination_block_type_id

        mock_block_schema_dependency = MagicMock()
        destination_block_schema_id = uuid.uuid4()
        mock_block_schema_dependency.destination_id = destination_block_schema_id

        migratable = await MigratableBlockDocument.construct(transfer_block_document)
        migratable._dependencies[transfer_block_document.block_type_id] = (
            mock_block_type_dependency
        )
        migratable._dependencies[transfer_block_document.block_schema_id] = (
            mock_block_schema_dependency
        )

        # Mock ObjectAlreadyExists exception on create
        mock_http_exc = Exception("Conflict")
        mock_client.create_block_document.side_effect = ObjectAlreadyExists(
            mock_http_exc
        )

        # Mock successful read of existing block document
        existing_block_document = BlockDocument(
            id=uuid.uuid4(),
            name=transfer_block_document.name,
            data={"different": "data"},  # Different to show it reads existing
            block_schema_id=destination_block_schema_id,
            block_schema=None,
            block_type_id=destination_block_type_id,
            block_type=None,
            block_document_references={},
            is_anonymous=transfer_block_document.is_anonymous,
            created=transfer_block_document.created,
            updated=transfer_block_document.updated,
        )
        mock_client.read_block_document_by_name.return_value = existing_block_document

        # Should raise TransferSkipped
        with pytest.raises(TransferSkipped, match="Already exists"):
            await migratable.migrate()

        # Verify client calls
        mock_client.create_block_document.assert_called_once()
        mock_client.read_block_document_by_name.assert_called_once_with(
            block_type_slug=transfer_block_document.block_type.slug,
            name=transfer_block_document.name,
        )

        # Verify destination_block_document is set to existing
        assert migratable.destination_block_document == existing_block_document
        assert migratable.destination_id == existing_block_document.id

    async def test_migrate_missing_block_type_dependency_raises_error(
        self, transfer_block_document: BlockDocument
    ):
        """Test migrate raises error when block type dependency is missing."""
        migratable = await MigratableBlockDocument.construct(transfer_block_document)

        with pytest.raises(ValueError, match="Unable to find destination block type"):
            await migratable.migrate()

    async def test_migrate_missing_block_schema_dependency_raises_error(
        self, transfer_block_document: BlockDocument
    ):
        """Test migrate raises error when block schema dependency is missing."""
        # Mock block type dependency but not block schema
        mock_block_type_dependency = MagicMock()
        mock_block_type_dependency.destination_id = uuid.uuid4()

        migratable = await MigratableBlockDocument.construct(transfer_block_document)
        migratable._dependencies[transfer_block_document.block_type_id] = (
            mock_block_type_dependency
        )

        with pytest.raises(ValueError, match="Unable to find destination block schema"):
            await migratable.migrate()
