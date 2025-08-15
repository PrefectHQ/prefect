"""Tests for the transfer DAG implementation."""

import asyncio
import uuid

import pytest

from prefect.cli.transfer._dag import TransferDAG


class MockMigratableResource:
    """Mock resource that implements the MigratableProtocol."""

    def __init__(self, source_id: uuid.UUID, name: str):
        self.source_id = source_id
        self.destination_id = None
        self.name = name
        self._dependencies = []

    async def get_dependencies(self):
        return self._dependencies

    async def migrate(self):
        self.destination_id = uuid.uuid4()

    def __repr__(self):
        return f"MockResource({self.name})"


@pytest.fixture
def mock_pool():
    """Create a mock work pool resource."""
    return MockMigratableResource(uuid.uuid4(), "pool")


@pytest.fixture
def mock_queue(mock_pool):
    """Create a mock work queue resource that depends on pool."""
    resource = MockMigratableResource(uuid.uuid4(), "queue")
    resource._dependencies = [mock_pool]
    return resource


@pytest.fixture
def mock_deployment(mock_pool):
    """Create a mock deployment resource that depends on pool."""
    resource = MockMigratableResource(uuid.uuid4(), "deployment")
    resource._dependencies = [mock_pool]
    return resource


async def test_dag_construction(mock_pool, mock_queue, mock_deployment):
    """Test that the DAG correctly builds from resources."""
    # Build DAG
    dag = TransferDAG()
    await dag.build_from_roots([mock_queue, mock_deployment])

    # Verify structure
    stats = dag.get_statistics()
    assert stats["total_nodes"] == 3
    assert stats["total_edges"] == 2
    assert not stats["has_cycles"]


async def test_dag_execution_order(mock_pool, mock_queue):
    """Test that resources are executed in dependency order."""
    # Build DAG
    dag = TransferDAG()
    await dag.build_from_roots([mock_queue])

    # Get execution layers
    layers = dag.get_execution_layers()
    assert len(layers) == 2

    # Pool should be in first layer (no dependencies)
    assert len(layers[0]) == 1
    assert layers[0][0].source_id == mock_pool.source_id

    # Queue should be in second layer (depends on pool)
    assert len(layers[1]) == 1
    assert layers[1][0].source_id == mock_queue.source_id


async def test_dag_concurrent_execution(mock_pool, mock_queue, mock_deployment):
    """Test that independent resources execute concurrently."""
    # Build DAG
    dag = TransferDAG()
    await dag.build_from_roots([mock_queue, mock_deployment])

    # Track execution order
    execution_order = []

    async def track_execution(resource):
        execution_order.append(resource.source_id)
        await asyncio.sleep(0.01)
        return uuid.uuid4()

    # Execute
    results = await dag.execute_concurrent(track_execution)

    # Pool should execute first
    assert execution_order[0] == mock_pool.source_id
    # Queue and deployment can execute in any order (concurrent)
    assert set(execution_order[1:]) == {mock_queue.source_id, mock_deployment.source_id}
    assert len(results) == 3


async def test_dag_failure_propagation(mock_pool, mock_queue):
    """Test that failures skip dependent resources."""
    # Build DAG
    dag = TransferDAG()
    await dag.build_from_roots([mock_queue])

    # Process function that fails for pool
    async def fail_on_pool(resource):
        if resource.source_id == mock_pool.source_id:
            raise ValueError("Failed to transfer pool")
        return uuid.uuid4()

    # Execute
    results = await dag.execute_concurrent(fail_on_pool)

    # Pool should have failed
    assert isinstance(results[mock_pool.source_id], ValueError)

    # Queue should be skipped
    assert isinstance(results[mock_queue.source_id], RuntimeError)
    assert "Skipped" in str(results[mock_queue.source_id])


async def test_dag_cycle_detection():
    """Test that the DAG detects cycles."""
    # Create resources with circular dependency
    resource1 = MockMigratableResource(uuid.uuid4(), "resource1")
    resource2 = MockMigratableResource(uuid.uuid4(), "resource2")

    # Create circular dependency
    resource1._dependencies = [resource2]
    resource2._dependencies = [resource1]

    # Build DAG
    dag = TransferDAG()
    await dag.build_from_roots([resource1])

    # Should detect cycle
    assert dag.has_cycles()

    # Should raise on execution
    with pytest.raises(ValueError, match="Cannot execute DAG with cycles"):
        await dag.execute_concurrent(lambda x: uuid.uuid4())


async def test_dag_deduplication(mock_pool):
    """Test that resources are deduplicated by ID."""
    # Create multiple queues depending on same pool
    queue1 = MockMigratableResource(uuid.uuid4(), "queue1")
    queue1._dependencies = [mock_pool]

    queue2 = MockMigratableResource(uuid.uuid4(), "queue2")
    queue2._dependencies = [mock_pool]

    # Build DAG
    dag = TransferDAG()
    await dag.build_from_roots([queue1, queue2])

    # Pool should only appear once
    stats = dag.get_statistics()
    assert stats["total_nodes"] == 3  # pool, queue1, queue2
    assert stats["total_edges"] == 2  # queue1->pool, queue2->pool


async def test_dag_strict_skip_on_failure(mock_pool, mock_queue):
    """Test that READY nodes are skipped when upstream fails."""
    # Build DAG
    dag = TransferDAG()
    await dag.build_from_roots([mock_queue])

    # Track execution
    executed = set()

    async def track_and_fail(resource):
        executed.add(resource.source_id)
        if resource.source_id == mock_pool.source_id:
            await asyncio.sleep(0.1)  # Delay to let queue become READY
            raise ValueError("Failed")
        return uuid.uuid4()

    # Execute
    results = await dag.execute_concurrent(track_and_fail, max_workers=10)

    # Only pool should have executed
    assert mock_pool.source_id in executed
    assert mock_queue.source_id not in executed

    # Queue should be skipped
    assert isinstance(results[mock_queue.source_id], RuntimeError)
