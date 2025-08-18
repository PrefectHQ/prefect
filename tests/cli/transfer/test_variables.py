import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.cli.transfer._exceptions import TransferSkipped
from prefect.cli.transfer._migratable_resources.variables import MigratableVariable
from prefect.client.schemas.actions import VariableCreate
from prefect.client.schemas.objects import Variable
from prefect.exceptions import ObjectAlreadyExists


class TestMigratableVariable:
    async def test_construct_creates_new_instance(self, transfer_variable: Variable):
        """Test that construct creates a new MigratableVariable instance."""
        migratable = await MigratableVariable.construct(transfer_variable)

        assert isinstance(migratable, MigratableVariable)
        assert migratable.source_variable == transfer_variable
        assert migratable.source_id == transfer_variable.id
        assert migratable.destination_variable is None
        assert migratable.destination_id is None

    async def test_construct_returns_cached_instance(self, transfer_variable: Variable):
        """Test that construct returns cached instance for same ID."""

        # Clear any existing instances
        MigratableVariable._instances.clear()

        # Create first instance
        migratable1 = await MigratableVariable.construct(transfer_variable)

        # Create second instance with same variable
        migratable2 = await MigratableVariable.construct(transfer_variable)

        # Should be the same instance
        assert migratable1 is migratable2
        assert len(MigratableVariable._instances) == 1

    async def test_get_instance_returns_cached_instance(
        self, transfer_variable: Variable
    ):
        """Test that get_instance returns cached instance."""

        # Clear any existing instances
        MigratableVariable._instances.clear()

        # Create instance
        migratable = await MigratableVariable.construct(transfer_variable)

        # Retrieve instance
        retrieved = await MigratableVariable.get_instance(transfer_variable.id)

        assert retrieved is migratable

    async def test_get_instance_returns_none_for_unknown_id(self):
        """Test that get_instance returns None for unknown ID."""
        # Clear any existing instances
        MigratableVariable._instances.clear()

        unknown_id = uuid.uuid4()
        retrieved = await MigratableVariable.get_instance(unknown_id)

        assert retrieved is None

    async def test_get_dependencies_returns_empty_list(
        self, transfer_variable: Variable
    ):
        """Test that get_dependencies returns empty list (variables have no dependencies)."""
        migratable = await MigratableVariable.construct(transfer_variable)
        dependencies = await migratable.get_dependencies()

        assert dependencies == []

    @patch("prefect.cli.transfer._migratable_resources.variables.get_client")
    async def test_migrate_success(
        self, mock_get_client: MagicMock, transfer_variable: Variable
    ):
        """Test successful variable migration."""

        # Mock the client
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        # Mock successful creation
        destination_variable = Variable(
            id=uuid.uuid4(),
            name=transfer_variable.name,
            value=transfer_variable.value,
            tags=transfer_variable.tags,
            created=transfer_variable.created,
            updated=transfer_variable.updated,
        )
        mock_client.create_variable.return_value = destination_variable

        migratable = await MigratableVariable.construct(transfer_variable)
        await migratable.migrate()

        # Verify client was called correctly
        mock_client.create_variable.assert_called_once_with(
            variable=VariableCreate(
                name=transfer_variable.name,
                value=transfer_variable.value,
                tags=transfer_variable.tags,
            )
        )

        # Verify destination_variable is set
        assert migratable.destination_variable == destination_variable
        assert migratable.destination_id == destination_variable.id

    @patch("prefect.cli.transfer._migratable_resources.variables.get_client")
    async def test_migrate_already_exists_raises_transfer_skipped(
        self, mock_get_client: MagicMock, transfer_variable: Variable
    ):
        """Test migration when variable already exists raises TransferSkipped."""

        # Mock the client
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        # Mock ObjectAlreadyExists exception on create
        mock_http_exc = Exception("Conflict")
        mock_client.create_variable.side_effect = ObjectAlreadyExists(mock_http_exc)

        # Mock successful read of existing variable
        existing_variable = Variable(
            id=uuid.uuid4(),
            name=transfer_variable.name,
            value="existing-value",  # Different value to show it reads existing
            tags=["existing-tag"],
            created=transfer_variable.created,
            updated=transfer_variable.updated,
        )
        mock_client.read_variable_by_name.return_value = existing_variable

        migratable = await MigratableVariable.construct(transfer_variable)

        # Should raise TransferSkipped
        with pytest.raises(TransferSkipped, match="Already exists"):
            await migratable.migrate()

        # Verify client calls
        mock_client.create_variable.assert_called_once()
        mock_client.read_variable_by_name.assert_called_once_with(
            transfer_variable.name
        )

        # Verify destination_variable is still set to the existing variable
        assert migratable.destination_variable == existing_variable
        assert migratable.destination_id == existing_variable.id

    @pytest.mark.parametrize(
        "test_value",
        [
            "string_value",
            123,
            12.34,
            True,
            {"key": "value", "nested": {"inner": "data"}},
            ["item1", "item2", "item3"],
            None,
        ],
        ids=[
            "string",
            "integer",
            "float",
            "boolean",
            "dict",
            "list",
            "none",
        ],
    )
    async def test_migration_with_different_value_types(
        self, session: AsyncSession, test_value: Any
    ):
        """Test migration with variables containing different value types."""
        from prefect.server import models, schemas

        # Clear instances before test
        MigratableVariable._instances.clear()

        # Create variable with specific value type
        orm_variable = await models.variables.create_variable(
            session=session,
            variable=schemas.actions.VariableCreate(
                name=f"test-var-{uuid.uuid4()}",
                value=test_value,
                tags=["test"],
            ),
        )
        await session.commit()

        # Convert to client schema object
        variable = Variable(
            id=orm_variable.id,
            name=orm_variable.name,
            value=orm_variable.value,
            tags=orm_variable.tags,
            created=orm_variable.created,
            updated=orm_variable.updated,
        )

        # Test construction works with different value types
        migratable = await MigratableVariable.construct(variable)
        assert migratable.source_variable.value == test_value

    async def test_variable_with_tags(self, session: AsyncSession):
        """Test variable with tags."""
        from prefect.server import models, schemas

        tags = ["tag1", "tag2", "environment:prod", "team:data"]
        orm_variable = await models.variables.create_variable(
            session=session,
            variable=schemas.actions.VariableCreate(
                name=f"tagged-var-{uuid.uuid4()}",
                value="tagged_value",
                tags=tags,
            ),
        )
        await session.commit()

        # Convert to client schema object
        variable = Variable(
            id=orm_variable.id,
            name=orm_variable.name,
            value=orm_variable.value,
            tags=orm_variable.tags,
            created=orm_variable.created,
            updated=orm_variable.updated,
        )

        migratable = await MigratableVariable.construct(variable)
        assert migratable.source_variable.tags == tags

    async def test_variable_without_tags(self, session: AsyncSession):
        """Test variable without tags."""
        from prefect.server import models, schemas

        orm_variable = await models.variables.create_variable(
            session=session,
            variable=schemas.actions.VariableCreate(
                name=f"untagged-var-{uuid.uuid4()}",
                value="untagged_value",
                tags=[],  # Empty tags
            ),
        )
        await session.commit()

        # Convert to client schema object
        variable = Variable(
            id=orm_variable.id,
            name=orm_variable.name,
            value=orm_variable.value,
            tags=orm_variable.tags,
            created=orm_variable.created,
            updated=orm_variable.updated,
        )

        migratable = await MigratableVariable.construct(variable)
        assert migratable.source_variable.tags == []
