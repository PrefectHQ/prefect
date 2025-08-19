import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.cli.transfer._exceptions import TransferSkipped
from prefect.cli.transfer._migratable_resources.flows import MigratableFlow
from prefect.client.schemas.actions import FlowCreate
from prefect.client.schemas.objects import Flow
from prefect.exceptions import ObjectAlreadyExists


class TestMigratableFlow:
    async def test_construct_creates_new_instance(self, transfer_flow: Flow):
        """Test that construct creates a new MigratableFlow instance."""
        migratable = await MigratableFlow.construct(transfer_flow)

        assert isinstance(migratable, MigratableFlow)
        assert migratable.source_flow == transfer_flow
        assert migratable.source_id == transfer_flow.id
        assert migratable.destination_flow is None
        assert migratable.destination_id is None

    async def test_construct_returns_cached_instance(self, transfer_flow: Flow):
        """Test that construct returns cached instance for same ID."""

        # Clear any existing instances
        MigratableFlow._instances.clear()

        # Create first instance
        migratable1 = await MigratableFlow.construct(transfer_flow)

        # Create second instance with same flow
        migratable2 = await MigratableFlow.construct(transfer_flow)

        # Should be the same instance
        assert migratable1 is migratable2
        assert len(MigratableFlow._instances) == 1

    async def test_construct_different_flows_create_different_instances(
        self, session: AsyncSession
    ):
        """Test that different flows create different instances."""
        from prefect.client.schemas.objects import Flow
        from prefect.server import models, schemas

        # Create two different flows
        orm_flow1 = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name=f"test-flow-1-{uuid.uuid4()}"),
        )
        orm_flow2 = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name=f"test-flow-2-{uuid.uuid4()}"),
        )
        await session.commit()

        # Convert to client schema objects
        flow1 = Flow(
            id=orm_flow1.id,
            name=orm_flow1.name,
            tags=orm_flow1.tags or [],
            labels=orm_flow1.labels or {},
            created=orm_flow1.created,
            updated=orm_flow1.updated,
        )
        flow2 = Flow(
            id=orm_flow2.id,
            name=orm_flow2.name,
            tags=orm_flow2.tags or [],
            labels=orm_flow2.labels or {},
            created=orm_flow2.created,
            updated=orm_flow2.updated,
        )

        # Clear any existing instances
        MigratableFlow._instances.clear()

        migratable1 = await MigratableFlow.construct(flow1)
        migratable2 = await MigratableFlow.construct(flow2)

        assert migratable1 is not migratable2
        assert len(MigratableFlow._instances) == 2
        assert migratable1.source_id != migratable2.source_id

    async def test_get_instance_returns_cached_instance(self, transfer_flow: Flow):
        """Test that get_instance returns cached instance."""

        # Clear any existing instances
        MigratableFlow._instances.clear()

        # Create instance
        migratable = await MigratableFlow.construct(transfer_flow)

        # Retrieve instance
        retrieved = await MigratableFlow.get_instance(transfer_flow.id)

        assert retrieved is migratable

    async def test_get_instance_returns_none_for_unknown_id(self):
        """Test that get_instance returns None for unknown ID."""
        # Clear any existing instances
        MigratableFlow._instances.clear()

        unknown_id = uuid.uuid4()
        retrieved = await MigratableFlow.get_instance(unknown_id)

        assert retrieved is None

    async def test_get_dependencies_returns_empty_list(self, transfer_flow: Flow):
        """Test that get_dependencies returns empty list (flows have no dependencies)."""
        migratable = await MigratableFlow.construct(transfer_flow)
        dependencies = await migratable.get_dependencies()

        assert dependencies == []

    @patch("prefect.cli.transfer._migratable_resources.flows.get_client")
    async def test_migrate_success(
        self, mock_get_client: MagicMock, transfer_flow: Flow
    ):
        """Test successful flow migration."""

        # Mock the client
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        # Mock successful creation
        destination_flow = Flow(
            id=uuid.uuid4(),
            name=transfer_flow.name,
            tags=transfer_flow.tags,
            labels=transfer_flow.labels,
            created=transfer_flow.created,
            updated=transfer_flow.updated,
        )
        mock_response = MagicMock()
        mock_response.json.return_value = destination_flow.model_dump()
        mock_client.request.return_value = mock_response

        migratable = await MigratableFlow.construct(transfer_flow)
        await migratable.migrate()

        # Verify client was called correctly
        mock_client.request.assert_called_once_with(
            "POST",
            "/flows/",
            json=FlowCreate(
                name=transfer_flow.name,
                tags=transfer_flow.tags,
                labels=transfer_flow.labels,
            ).model_dump(mode="json"),
        )

        # Verify destination_flow is set
        assert migratable.destination_flow is not None
        assert migratable.destination_flow.name == destination_flow.name
        assert migratable.destination_flow.tags == destination_flow.tags
        assert migratable.destination_flow.labels == destination_flow.labels

    @patch("prefect.cli.transfer._migratable_resources.flows.get_client")
    async def test_migrate_already_exists_raises_transfer_skipped(
        self, mock_get_client: MagicMock, transfer_flow: Flow
    ):
        """Test migration when flow already exists raises TransferSkipped."""

        # Mock the client
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        # Mock ObjectAlreadyExists exception on create
        mock_http_exc = Exception("Conflict")
        mock_client.request.side_effect = ObjectAlreadyExists(mock_http_exc)

        # Mock successful read of existing flow
        from typing import cast

        from prefect.types import KeyValueLabelsField

        existing_flow = Flow(
            id=uuid.uuid4(),
            name=transfer_flow.name,
            tags=["existing-tag"],  # Different tags to show it reads existing
            labels=cast(
                KeyValueLabelsField, {"environment": "existing"}
            ),  # Different labels
            created=transfer_flow.created,
            updated=transfer_flow.updated,
        )
        mock_client.read_flows.return_value = [existing_flow]

        migratable = await MigratableFlow.construct(transfer_flow)

        # Should raise TransferSkipped
        with pytest.raises(TransferSkipped, match="Already exists"):
            await migratable.migrate()

        # Verify client calls
        mock_client.request.assert_called_once()
        mock_client.read_flows.assert_called_once()

        # Verify destination_flow is still set to the existing flow
        assert migratable.destination_flow == existing_flow
        assert migratable.destination_id == existing_flow.id

    @pytest.mark.parametrize(
        "tags,labels",
        [
            ([], {}),
            (["tag1", "tag2"], {}),
            ([], {"environment": "prod", "team": "data"}),
            (["tag1", "tag2"], {"environment": "prod", "team": "data"}),
        ],
        ids=["no-tags-no-labels", "tags-only", "labels-only", "tags-and-labels"],
    )
    async def test_flow_with_different_tags_and_labels(
        self, session: AsyncSession, tags: list[str], labels: dict[str, str]
    ):
        """Test flows with different combinations of tags and labels."""
        from prefect.client.schemas.objects import Flow
        from prefect.server import models, schemas

        # Clear instances before test
        MigratableFlow._instances.clear()

        from typing import cast

        from prefect.types import KeyValueLabelsField

        # Create flow with specific tags and labels
        orm_flow = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(
                name=f"test-flow-{uuid.uuid4()}",
                tags=tags,
                labels=cast(KeyValueLabelsField, labels),
            ),
        )
        await session.commit()

        # Convert to client schema object
        flow = Flow(
            id=orm_flow.id,
            name=orm_flow.name,
            tags=orm_flow.tags or [],
            labels=orm_flow.labels or {},
            created=orm_flow.created,
            updated=orm_flow.updated,
        )

        # Test construction works with different tags/labels combinations
        migratable = await MigratableFlow.construct(flow)
        assert migratable.source_flow.tags == tags
        assert migratable.source_flow.labels == labels
