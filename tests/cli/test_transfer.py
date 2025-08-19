"""Tests for the prefect transfer CLI command."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from prefect.cli.transfer import _find_root_resources, _get_resource_display_name
from prefect.cli.transfer._exceptions import TransferSkipped
from prefect.cli.transfer._migratable_resources.base import MigratableProtocol
from prefect.settings import Profile, ProfilesCollection
from prefect.testing.cli import invoke_and_assert
from prefect.utilities.asyncutils import run_sync_in_worker_thread


class MockMigratableResource:
    """Mock migratable resource for CLI testing."""

    def __init__(
        self,
        resource_id: uuid.UUID,
        name: str,
        resource_type: str = "test",
        migrate_success: bool = True,
        skip: bool = False,
    ):
        self.source_id = resource_id
        self.destination_id = None
        self.name = name
        self.resource_type = resource_type
        self._migrate_success = migrate_success
        self._skip = skip

        # Add source attributes for display name mapping
        if resource_type == "work_pool":
            self.source_work_pool = MagicMock()
            self.source_work_pool.name = name
        elif resource_type == "work_queue":
            self.source_work_queue = MagicMock()
            self.source_work_queue.name = name
        elif resource_type == "deployment":
            self.source_deployment = MagicMock()
            self.source_deployment.name = name
        elif resource_type == "flow":
            self.source_flow = MagicMock()
            self.source_flow.name = name
        elif resource_type == "block_document":
            self.source_block_document = MagicMock()
            self.source_block_document.name = name
        elif resource_type == "block_type":
            self.source_block_type = MagicMock()
            self.source_block_type.slug = name
        elif resource_type == "block_schema":
            self.source_block_schema = MagicMock()
            self.source_block_schema.id = resource_id
        elif resource_type == "variable":
            self.source_variable = MagicMock()
            self.source_variable.name = name
        elif resource_type == "automation":
            self.source_automation = MagicMock()
            self.source_automation.name = name
        elif resource_type == "concurrency_limit":
            self.source_global_concurrency_limit = MagicMock()
            self.source_global_concurrency_limit.name = name

    async def migrate(self) -> None:
        """Mock migrate method."""
        if self._skip:
            raise TransferSkipped(f"Skipped {self.name}")
        elif not self._migrate_success:
            raise ValueError(f"Migration failed for {self.name}")

    async def get_dependencies(self) -> list[MigratableProtocol]:
        """Mock get_dependencies method."""
        return []

    def __str__(self) -> str:
        return f"Mock{self.resource_type.title()}({self.name})"


@pytest.fixture
def mock_profiles():
    """Mock profile collection with test profiles."""
    source_profile = Profile(name="source", settings={})
    target_profile = Profile(name="target", settings={})
    return ProfilesCollection([source_profile, target_profile], active="source")


@pytest.fixture
def mock_resources():
    """Mock migratable resources of various types."""
    return [
        MockMigratableResource(uuid.uuid4(), "test-pool", "work_pool"),
        MockMigratableResource(uuid.uuid4(), "test-queue", "work_queue"),
        MockMigratableResource(uuid.uuid4(), "test-deployment", "deployment"),
        MockMigratableResource(uuid.uuid4(), "test-flow", "flow"),
        MockMigratableResource(uuid.uuid4(), "test-block", "block_document"),
        MockMigratableResource(uuid.uuid4(), "test-var", "variable"),
    ]


@pytest.fixture
def mock_client():
    """Mock PrefectClient with resource collections."""
    client = AsyncMock()
    # Mock empty collections by default - these need to be AsyncMock to be awaitable
    client.read_work_pools = AsyncMock(return_value=[])
    client.read_work_queues = AsyncMock(return_value=[])
    client.read_deployments = AsyncMock(return_value=[])
    client.read_block_documents = AsyncMock(return_value=[])
    client.read_variables = AsyncMock(return_value=[])
    client.read_global_concurrency_limits = AsyncMock(return_value=[])
    client.read_automations = AsyncMock(return_value=[])
    return client


@pytest.fixture
def mock_dag():
    """Mock TransferDAG for execution testing."""
    dag = MagicMock()
    dag.nodes = {}
    dag.get_statistics.return_value = {
        "total_nodes": 0,
        "total_edges": 0,
        "has_cycles": False,
    }
    dag.execute_concurrent = AsyncMock(return_value={})
    return dag


class TestTransferArguments:
    """Test command line argument validation."""

    @patch("prefect.cli.transfer.load_profiles")
    def test_transfer_source_profile_not_found(self, mock_load_profiles: MagicMock):
        """Test transfer command fails when source profile doesn't exist."""
        mock_load_profiles.return_value = ProfilesCollection([])

        invoke_and_assert(
            command=["transfer", "--from", "nonexistent", "--to", "target"],
            expected_code=1,
            expected_output_contains="Source profile 'nonexistent' not found",
        )

    @patch("prefect.cli.transfer.load_profiles")
    def test_transfer_target_profile_not_found(
        self, mock_load_profiles: MagicMock, mock_profiles: ProfilesCollection
    ):
        """Test transfer command fails when target profile doesn't exist."""
        # Only include source profile
        source_profile = Profile(name="source", settings={})
        mock_load_profiles.return_value = ProfilesCollection([source_profile])

        invoke_and_assert(
            command=["transfer", "--from", "source", "--to", "nonexistent"],
            expected_code=1,
            expected_output_contains="Target profile 'nonexistent' not found",
        )

    @patch("prefect.cli.transfer.load_profiles")
    def test_transfer_same_source_and_target_profiles(
        self, mock_load_profiles: MagicMock
    ):
        """Test transfer command fails when source and target are the same."""
        profile = Profile(name="same", settings={})
        mock_load_profiles.return_value = ProfilesCollection([profile])

        invoke_and_assert(
            command=["transfer", "--from", "same", "--to", "same"],
            expected_code=1,
            expected_output_contains="Source and target profiles must be different",
        )


class TestResourceCollection:
    """Test resource collection from source profile."""

    @patch("prefect.cli.transfer.load_profiles")
    @patch("prefect.cli.transfer.use_profile")
    @patch("prefect.cli.transfer.get_client")
    async def test_transfer_no_resources_found(
        self,
        mock_get_client: MagicMock,
        mock_use_profile: MagicMock,
        mock_load_profiles: MagicMock,
        mock_profiles: ProfilesCollection,
    ):
        """Test transfer when no resources are found."""
        mock_load_profiles.return_value = mock_profiles

        # Mock context managers
        mock_use_profile.return_value.__enter__.return_value = None
        mock_use_profile.return_value.__exit__.return_value = None

        # Mock client with empty resource collections
        mock_client = AsyncMock()
        mock_client.read_work_pools = AsyncMock(return_value=[])
        mock_client.read_work_queues = AsyncMock(return_value=[])
        mock_client.read_deployments = AsyncMock(return_value=[])
        mock_client.read_block_documents = AsyncMock(return_value=[])
        mock_client.read_variables = AsyncMock(return_value=[])
        mock_client.read_global_concurrency_limits = AsyncMock(return_value=[])
        mock_client.read_automations = AsyncMock(return_value=[])
        mock_get_client.return_value.__aenter__.return_value = mock_client
        mock_get_client.return_value.__aexit__.return_value = None

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=["transfer", "--from", "source", "--to", "target"],
            expected_code=0,
            expected_output_contains="No resources found to transfer",
        )


class TestIntegrationScenarios:
    """Integration-style tests for common scenarios."""

    @patch("prefect.cli.transfer.load_profiles")
    def test_transfer_basic_help_and_validation(
        self, mock_load_profiles: MagicMock, mock_profiles: ProfilesCollection
    ):
        """Test that basic command structure and validation works."""
        # Test that the command is registered
        invoke_and_assert(
            command=["transfer", "--help"],
            expected_code=0,
            expected_output_contains=[
                "Transfer resources from one Prefect profile to another",
            ],
        )


class TestHelperFunctions:
    """Test helper functions used by the CLI."""

    def test_get_resource_display_name_work_pool(self):
        """Test display name generation for work pool."""

        resource = MockMigratableResource(uuid.uuid4(), "test-pool", "work_pool")
        display_name = _get_resource_display_name(resource)
        assert display_name == "work-pool/test-pool"

    def test_get_resource_display_name_work_queue(self):
        """Test display name generation for work queue."""

        resource = MockMigratableResource(uuid.uuid4(), "test-queue", "work_queue")
        display_name = _get_resource_display_name(resource)
        assert display_name == "work-queue/test-queue"

    def test_get_resource_display_name_deployment(self):
        """Test display name generation for deployment."""

        resource = MockMigratableResource(uuid.uuid4(), "test-deploy", "deployment")
        display_name = _get_resource_display_name(resource)
        assert display_name == "deployment/test-deploy"

    def test_get_resource_display_name_block_type(self):
        """Test display name generation for block type."""

        resource = MockMigratableResource(uuid.uuid4(), "test-block-type", "block_type")
        display_name = _get_resource_display_name(resource)
        assert display_name == "block-type/test-block-type"

    def test_get_resource_display_name_block_schema(self):
        """Test display name generation for block schema."""

        id = uuid.uuid4()
        resource = MockMigratableResource(id, "test-block-schema", "block_schema")
        display_name = _get_resource_display_name(resource)
        assert display_name == f"block-schema/{str(id)[:8]}"

    def test_get_resource_display_name_variable(self):
        """Test display name generation for variable."""

        resource = MockMigratableResource(uuid.uuid4(), "test-var", "variable")
        display_name = _get_resource_display_name(resource)
        assert display_name == "variable/test-var"

    def test_get_resource_display_name_automation(self):
        """Test display name generation for automation."""

        resource = MockMigratableResource(uuid.uuid4(), "test-automation", "automation")
        display_name = _get_resource_display_name(resource)
        assert display_name == "automation/test-automation"

    def test_get_resource_display_name_concurrency_limit(self):
        """Test display name generation for concurrency limit."""

        resource = MockMigratableResource(
            uuid.uuid4(), "test-concurrency-limit", "concurrency_limit"
        )
        display_name = _get_resource_display_name(resource)
        assert display_name == "concurrency-limit/test-concurrency-limit"

    def test_get_resource_display_name_block_document(self):
        """Test display name generation for block document."""

        resource = MockMigratableResource(
            uuid.uuid4(), "test-block-document", "block_document"
        )
        display_name = _get_resource_display_name(resource)
        assert display_name == "block-document/test-block-document"

    def test_get_resource_display_name_flow(self):
        """Test display name generation for flow."""

        resource = MockMigratableResource(uuid.uuid4(), "test-flow", "flow")
        display_name = _get_resource_display_name(resource)
        assert display_name == "flow/test-flow"

    def test_get_resource_display_name_unknown(self):
        """Test display name generation for unknown resource type."""

        resource = MockMigratableResource(uuid.uuid4(), "test", "unknown")
        display_name = _get_resource_display_name(resource)
        assert display_name == "MockUnknown(test)"

    async def test_find_root_resources_with_dependencies(
        self, mock_resources: list[MockMigratableResource]
    ):
        """Test _find_root_resources identifies correct root resources."""

        # Create mock resources with dependencies
        root1 = MockMigratableResource(uuid.uuid4(), "root1")
        root2 = MockMigratableResource(uuid.uuid4(), "root2")
        dep1 = MockMigratableResource(uuid.uuid4(), "dep1")
        dep2 = MockMigratableResource(uuid.uuid4(), "dep2")

        all_resources = [root1, root2, dep1, dep2]

        # Mock dependencies: root1 -> dep1, root2 -> dep2
        async def mock_get_deps_root1():
            return [dep1]

        async def mock_get_deps_root2():
            return [dep2]

        async def mock_get_deps_empty():
            return []

        root1.get_dependencies = mock_get_deps_root1
        root2.get_dependencies = mock_get_deps_root2
        dep1.get_dependencies = mock_get_deps_empty
        dep2.get_dependencies = mock_get_deps_empty

        roots = await _find_root_resources(all_resources)

        # Root1 and root2 should be identified as roots (not dependencies of others)
        root_ids = {r.source_id for r in roots}
        assert root1.source_id in root_ids
        assert root2.source_id in root_ids
        assert dep1.source_id not in root_ids
        assert dep2.source_id not in root_ids

    async def test_find_root_resources_no_dependencies(
        self, mock_resources: list[MockMigratableResource]
    ):
        """Test _find_root_resources when no resources have dependencies."""
        from prefect.cli.transfer import _find_root_resources

        # All resources have no dependencies - all should be roots
        async def mock_get_deps_empty():
            return []

        for resource in mock_resources:
            resource.get_dependencies = mock_get_deps_empty

        roots = await _find_root_resources(mock_resources)

        # All resources should be roots
        assert len(roots) == len(mock_resources)
