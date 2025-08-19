import asyncio
import uuid
from collections import defaultdict
from typing import Optional
from unittest.mock import patch

from prefect.cli.transfer._dag import NodeState, TransferDAG
from prefect.cli.transfer._exceptions import TransferSkipped
from prefect.cli.transfer._migratable_resources.base import MigratableProtocol


class MockMigratableResource:
    """Mock migratable resource for testing DAG functionality."""

    def __init__(
        self,
        resource_id: uuid.UUID,
        name: str,
        migrate_success: bool = True,
        dependencies: Optional[list[uuid.UUID]] = None,
    ):
        self.id = resource_id
        self.source_id = resource_id
        self.destination_id = None
        self.name = name
        self._migrate_success = migrate_success
        self._dependencies = dependencies or []
        self.migrate_called = False
        self.get_dependencies_called = False

    async def migrate(self) -> None:
        """Mock migrate method."""
        self.migrate_called = True
        if not self._migrate_success:
            if self.name.endswith("_skip"):
                raise TransferSkipped("Test skip")
            else:
                raise ValueError(f"Mock migration error for {self.name}")

    async def get_dependencies(self) -> list[MigratableProtocol]:
        """Mock get_dependencies method."""
        self.get_dependencies_called = True
        return [
            MockMigratableResource(dep_id, f"dep_{dep_id}")
            for dep_id in self._dependencies
        ]

    def __str__(self) -> str:
        return f"MockResource({self.name})"

    def __repr__(self) -> str:
        return f"MockResource(id={self.id}, name='{self.name}')"


class TestTransferDAG:
    def test_init_creates_empty_dag(self):
        """Test DAG initialization creates empty structures."""
        dag = TransferDAG()

        assert dag.nodes == {}
        assert dag._dependencies == defaultdict(set)
        assert dag._dependents == defaultdict(set)
        assert dag._status == {}

    def test_add_node_creates_new_node(self):
        """Test adding a new node to the DAG."""
        dag = TransferDAG()
        resource = MockMigratableResource(uuid.uuid4(), "test-resource")

        node_id = dag.add_node(resource)

        assert node_id == resource.source_id
        assert resource.source_id in dag.nodes
        assert dag.nodes[resource.source_id] == resource
        assert dag._status[resource.source_id].state == NodeState.PENDING

    def test_add_node_returns_existing_node(self):
        """Test adding an existing node returns the cached node."""
        dag = TransferDAG()
        resource = MockMigratableResource(uuid.uuid4(), "test-resource")

        node_id1 = dag.add_node(resource)
        node_id2 = dag.add_node(resource)

        assert node_id1 == node_id2
        assert len(dag.nodes) == 1

    def test_add_edge_creates_dependency(self):
        """Test adding an edge creates proper dependency relationship."""
        dag = TransferDAG()
        parent = MockMigratableResource(uuid.uuid4(), "parent")
        child = MockMigratableResource(uuid.uuid4(), "child")

        dag.add_node(parent)
        dag.add_node(child)
        dag.add_edge(parent.source_id, child.source_id)

        assert child.source_id in dag._dependencies[parent.source_id]
        assert parent.source_id in dag._dependents[child.source_id]

    async def test_build_from_roots_single_resource(self):
        """Test building DAG from a single resource with no dependencies."""
        dag = TransferDAG()
        resource = MockMigratableResource(uuid.uuid4(), "single-resource")

        await dag.build_from_roots([resource])

        assert len(dag.nodes) == 1
        assert resource.source_id in dag.nodes
        assert len(dag._dependencies) == 0
        assert resource.get_dependencies_called

    async def test_build_from_roots_with_dependencies(self):
        """Test building DAG from resources with dependencies."""
        dag = TransferDAG()

        dep_id = uuid.uuid4()
        root_resource = MockMigratableResource(
            uuid.uuid4(), "root-resource", dependencies=[dep_id]
        )

        with patch.object(root_resource, "get_dependencies") as mock_get_deps:
            dependency = MockMigratableResource(dep_id, "dependency")
            mock_get_deps.return_value = [dependency]

            await dag.build_from_roots([root_resource])

            assert len(dag.nodes) == 2
            assert root_resource.source_id in dag.nodes
            assert dependency.source_id in dag.nodes
            assert dependency.source_id in dag._dependencies[root_resource.source_id]
            assert root_resource.source_id in dag._dependents[dependency.source_id]
            mock_get_deps.assert_called_once()

    async def test_build_from_roots_complex_dependency_chain(self):
        """Test building DAG with complex dependency chains."""
        dag = TransferDAG()

        # Create a chain: root -> mid -> leaf
        leaf_id = uuid.uuid4()
        mid_id = uuid.uuid4()
        root_id = uuid.uuid4()

        leaf = MockMigratableResource(leaf_id, "leaf")
        mid = MockMigratableResource(mid_id, "mid", dependencies=[leaf_id])
        root = MockMigratableResource(root_id, "root", dependencies=[mid_id])

        with (
            patch.object(mid, "get_dependencies", return_value=[leaf]),
            patch.object(root, "get_dependencies", return_value=[mid]),
            patch.object(leaf, "get_dependencies", return_value=[]),
        ):
            await dag.build_from_roots([root])

            assert len(dag.nodes) == 3
            assert mid_id in dag._dependencies[root_id]
            assert leaf_id in dag._dependencies[mid_id]
            assert len(dag._dependencies[leaf_id]) == 0
            assert len(dag._dependencies[mid_id]) == 1
            assert len(dag._dependencies[root_id]) == 1

    def test_detect_cycles_no_cycle(self):
        """Test cycle detection on acyclic graph."""
        dag = TransferDAG()

        node1 = MockMigratableResource(uuid.uuid4(), "node1")
        node2 = MockMigratableResource(uuid.uuid4(), "node2")

        dag.add_node(node1)
        dag.add_node(node2)
        dag.add_edge(node1.source_id, node2.source_id)

        has_cycles = dag.has_cycles()
        assert has_cycles is False

    def test_detect_cycles_with_cycle(self):
        """Test cycle detection finds cycles."""
        dag = TransferDAG()

        node1 = MockMigratableResource(uuid.uuid4(), "node1")
        node2 = MockMigratableResource(uuid.uuid4(), "node2")
        node3 = MockMigratableResource(uuid.uuid4(), "node3")

        dag.add_node(node1)
        dag.add_node(node2)
        dag.add_node(node3)

        # Create cycle: node1 -> node2 -> node3 -> node1
        dag.add_edge(node1.source_id, node2.source_id)
        dag.add_edge(node2.source_id, node3.source_id)
        dag.add_edge(node3.source_id, node1.source_id)

        has_cycles = dag.has_cycles()
        assert has_cycles is True

    def test_detect_cycles_self_loop(self):
        """Test cycle detection finds self loops."""
        dag = TransferDAG()

        node = MockMigratableResource(uuid.uuid4(), "self-loop")
        dag.add_node(node)
        dag.add_edge(node.source_id, node.source_id)

        has_cycles = dag.has_cycles()
        assert has_cycles is True

    def test_get_execution_layers_empty_dag(self):
        """Test getting execution layers from empty DAG."""
        dag = TransferDAG()
        layers = dag.get_execution_layers()
        assert layers == []

    def test_get_execution_layers_single_node(self):
        """Test getting execution layers with single node."""
        dag = TransferDAG()
        resource = MockMigratableResource(uuid.uuid4(), "single")

        dag.add_node(resource)
        layers = dag.get_execution_layers()

        assert len(layers) == 1
        assert len(layers[0]) == 1
        assert resource in layers[0]

    def test_get_execution_layers_dependency_chain(self):
        """Test getting execution layers with dependency chain."""
        dag = TransferDAG()

        # Create chain: dep -> resource
        dep = MockMigratableResource(uuid.uuid4(), "dep")
        resource = MockMigratableResource(uuid.uuid4(), "resource")

        dag.add_node(dep)
        dag.add_node(resource)
        dag.add_edge(resource.source_id, dep.source_id)  # resource depends on dep

        layers = dag.get_execution_layers()

        assert len(layers) == 2
        assert dep in layers[0]  # Dependencies first
        assert resource in layers[1]  # Dependents second

    def test_get_execution_layers_complex_graph(self):
        """Test getting execution layers with complex dependency graph."""
        dag = TransferDAG()

        # Create diamond dependency: root -> [dep1, dep2] -> leaf
        root = MockMigratableResource(uuid.uuid4(), "root")
        dep1 = MockMigratableResource(uuid.uuid4(), "dep1")
        dep2 = MockMigratableResource(uuid.uuid4(), "dep2")
        leaf = MockMigratableResource(uuid.uuid4(), "leaf")

        for resource in [root, dep1, dep2, leaf]:
            dag.add_node(resource)

        # Root depends on dep1 and dep2
        dag.add_edge(root.source_id, dep1.source_id)
        dag.add_edge(root.source_id, dep2.source_id)
        # dep1 and dep2 depend on leaf
        dag.add_edge(dep1.source_id, leaf.source_id)
        dag.add_edge(dep2.source_id, leaf.source_id)

        layers = dag.get_execution_layers()

        assert len(layers) == 3
        assert leaf in layers[0]  # Leaf first (no dependencies)
        assert {dep1, dep2} == set(layers[1])  # dep1 and dep2 parallel
        assert root in layers[2]  # Root last

    async def test_execute_success_single_resource(self):
        """Test successful execution of single resource."""
        dag = TransferDAG()
        resource = MockMigratableResource(uuid.uuid4(), "test-resource")

        await dag.build_from_roots([resource])

        async def process_node(node: MigratableProtocol):
            await node.migrate()
            return "success"

        results = await dag.execute_concurrent(process_node)

        assert len([r for r in results.values() if r == "success"]) == 1
        assert resource.migrate_called

    async def test_execute_success_multiple_resources(self):
        """Test successful execution of multiple independent resources."""
        dag = TransferDAG()
        resource1 = MockMigratableResource(uuid.uuid4(), "resource1")
        resource2 = MockMigratableResource(uuid.uuid4(), "resource2")

        await dag.build_from_roots([resource1, resource2])

        async def process_node(node: MigratableProtocol):
            await node.migrate()
            return "success"

        results = await dag.execute_concurrent(process_node)

        assert len([r for r in results.values() if r == "success"]) == 2
        assert resource1.migrate_called
        assert resource2.migrate_called

    async def test_execute_with_skipped_resource(self):
        """Test execution with skipped resource."""
        dag = TransferDAG()
        resource = MockMigratableResource(
            uuid.uuid4(), "test_skip", migrate_success=False
        )

        await dag.build_from_roots([resource])

        async def process_node(node: MigratableProtocol):
            await node.migrate()
            return "success"

        results = await dag.execute_concurrent(process_node)

        # Should have TransferSkipped exception
        assert len([r for r in results.values() if isinstance(r, TransferSkipped)]) == 1

    async def test_execute_with_failed_resource(self):
        """Test execution with failed resource."""
        dag = TransferDAG()
        resource = MockMigratableResource(
            uuid.uuid4(), "test_fail", migrate_success=False
        )

        await dag.build_from_roots([resource])

        async def process_node(node: MigratableProtocol):
            await node.migrate()
            return "success"

        results = await dag.execute_concurrent(process_node)

        # Should have ValueError exception
        assert len([r for r in results.values() if isinstance(r, ValueError)]) == 1

    async def test_execute_failure_propagation(self):
        """Test that failure propagates to skip dependent resources."""
        dag = TransferDAG()

        # Create failing dependency and successful root
        dep = MockMigratableResource(uuid.uuid4(), "failing_dep", migrate_success=False)
        root = MockMigratableResource(uuid.uuid4(), "root")

        dag.add_node(dep)
        dag.add_node(root)
        dag.add_edge(root.source_id, dep.source_id)  # root depends on dep

        async def process_node(node: MigratableProtocol):
            await node.migrate()
            return "success"

        results = await dag.execute_concurrent(process_node)

        # Should have one failure and one skip
        assert len([r for r in results.values() if isinstance(r, ValueError)]) == 1
        assert len([r for r in results.values() if isinstance(r, TransferSkipped)]) == 1

        # Root should not be migrated due to failed dependency
        assert not root.migrate_called
        assert dep.migrate_called

    async def test_execute_with_dependency_chain(self):
        """Test execution with successful dependency chain."""
        dag = TransferDAG()

        # Create chain: leaf <- mid <- root (execution order: leaf, mid, root)
        leaf = MockMigratableResource(uuid.uuid4(), "leaf")
        mid = MockMigratableResource(uuid.uuid4(), "mid")
        root = MockMigratableResource(uuid.uuid4(), "root")

        dag.add_node(leaf)
        dag.add_node(mid)
        dag.add_node(root)

        dag.add_edge(mid.source_id, leaf.source_id)  # mid depends on leaf
        dag.add_edge(root.source_id, mid.source_id)  # root depends on mid

        async def process_node(node: MigratableProtocol):
            await node.migrate()
            return "success"

        results = await dag.execute_concurrent(process_node)

        assert len([r for r in results.values() if r == "success"]) == 3

        assert leaf.migrate_called
        assert mid.migrate_called
        assert root.migrate_called

    async def test_execute_concurrent_worker_pool(self):
        """Test execution uses concurrent worker pool."""
        dag = TransferDAG()

        # Create multiple independent resources
        resources = [
            MockMigratableResource(uuid.uuid4(), f"resource_{i}") for i in range(5)
        ]

        for resource in resources:
            dag.add_node(resource)

        # Mock sleep to verify concurrency
        async def mock_migrate(self: MockMigratableResource):
            await asyncio.sleep(0.1)  # Simulate work
            self.migrate_called = True

        for resource in resources:
            resource.migrate = mock_migrate.__get__(resource, MockMigratableResource)

        async def process_node(node: MigratableProtocol):
            await node.migrate()
            return "success"

        # Execute with worker pool
        start_time = asyncio.get_event_loop().time()
        results = await dag.execute_concurrent(process_node, max_workers=3)
        end_time = asyncio.get_event_loop().time()

        # Should complete faster than sequential execution due to concurrency
        assert end_time - start_time < 0.5  # Would be 0.5s if sequential
        assert len([r for r in results.values() if r == "success"]) == 5

        for resource in resources:
            assert resource.migrate_called

    async def test_execute_respects_max_workers_limit(self):
        """Test execution respects max_workers limiter."""
        dag = TransferDAG()

        # Track active workers
        active_workers: list[str] = []
        max_concurrent = 0

        async def mock_migrate(self: MockMigratableResource):
            nonlocal max_concurrent
            active_workers.append(self.name)
            max_concurrent = max(max_concurrent, len(active_workers))
            await asyncio.sleep(0.1)
            active_workers.remove(self.name)
            self.migrate_called = True

        # Create resources
        resources = [
            MockMigratableResource(uuid.uuid4(), f"resource_{i}") for i in range(5)
        ]

        for resource in resources:
            dag.add_node(resource)
            resource.migrate = mock_migrate.__get__(resource, MockMigratableResource)

        async def process_node(node: MigratableProtocol):
            await node.migrate()
            return "success"

        await dag.execute_concurrent(process_node, max_workers=2)

        # Should never exceed max_workers limit
        assert max_concurrent <= 2

        for resource in resources:
            assert resource.migrate_called

    def test_statistics_empty_dag(self):
        """Test statistics for empty DAG."""
        dag = TransferDAG()
        stats = dag.get_statistics()

        assert stats["total_nodes"] == 0
        assert stats["total_edges"] == 0

    def test_statistics_with_nodes_and_edges(self):
        """Test statistics calculation with nodes and edges."""
        dag = TransferDAG()

        resource1 = MockMigratableResource(uuid.uuid4(), "resource1")
        resource2 = MockMigratableResource(uuid.uuid4(), "resource2")
        resource3 = MockMigratableResource(uuid.uuid4(), "resource3")

        dag.add_node(resource1)
        dag.add_node(resource2)
        dag.add_node(resource3)

        dag.add_edge(resource1.source_id, resource2.source_id)
        dag.add_edge(resource2.source_id, resource3.source_id)

        stats = dag.get_statistics()

        assert stats["total_nodes"] == 3
        assert stats["total_edges"] == 2

    async def test_node_status_tracking(self):
        """Test that node status is properly tracked during execution."""
        dag = TransferDAG()

        success_resource = MockMigratableResource(uuid.uuid4(), "success")
        skip_resource = MockMigratableResource(
            uuid.uuid4(), "test_skip", migrate_success=False
        )
        fail_resource = MockMigratableResource(
            uuid.uuid4(), "fail", migrate_success=False
        )

        dag.add_node(success_resource)
        dag.add_node(skip_resource)
        dag.add_node(fail_resource)

        async def process_node(node: MigratableProtocol):
            await node.migrate()
            return "success"

        await dag.execute_concurrent(process_node)

        # Check final node states
        assert dag._status[success_resource.source_id].state == NodeState.COMPLETED
        assert (
            dag._status[skip_resource.source_id].state == NodeState.SKIPPED
        )  # TransferSkipped is treated as failure
        assert dag._status[fail_resource.source_id].state == NodeState.FAILED

    async def test_build_from_roots_handles_duplicate_dependencies(self):
        """Test building DAG handles duplicate dependency references correctly."""
        dag = TransferDAG()

        shared_dep_id = uuid.uuid4()
        shared_dep = MockMigratableResource(shared_dep_id, "shared-dep")

        root1 = MockMigratableResource(
            uuid.uuid4(), "root1", dependencies=[shared_dep_id]
        )
        root2 = MockMigratableResource(
            uuid.uuid4(), "root2", dependencies=[shared_dep_id]
        )

        with (
            patch.object(root1, "get_dependencies", return_value=[shared_dep]),
            patch.object(root2, "get_dependencies", return_value=[shared_dep]),
            patch.object(shared_dep, "get_dependencies", return_value=[]),
        ):
            await dag.build_from_roots([root1, root2])

            # Should have 3 nodes (root1, root2, shared_dep)
            assert len(dag.nodes) == 3
            # shared_dep should be depended on by both roots
            assert len(dag._dependents[shared_dep_id]) == 2
            # Both roots should depend on shared_dep
            assert shared_dep_id in dag._dependencies[root1.source_id]
            assert shared_dep_id in dag._dependencies[root2.source_id]

    async def test_execute_empty_dag_returns_zero_stats(self):
        """Test executing empty DAG returns empty results."""
        dag = TransferDAG()

        async def process_node(node: MigratableProtocol):
            await node.migrate()
            return "success"

        results = await dag.execute_concurrent(process_node)

        assert results == {}
