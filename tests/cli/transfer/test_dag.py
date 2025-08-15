"""Tests for the transfer DAG implementation."""

import asyncio
import uuid
from unittest.mock import AsyncMock

import pytest

from prefect.cli.transfer._dag import TransferDAG
from prefect.cli.transfer._migratable_resources import (
    construct_migratable_resource,
)
from prefect.client.schemas.objects import Deployment, WorkPool, WorkQueue


@pytest.fixture
def mock_work_pool():
    """Create a mock work pool."""
    return WorkPool(
        id=uuid.uuid4(), name="test-pool", type="kubernetes", base_job_template={}
    )


@pytest.fixture
def mock_work_queue(mock_work_pool):
    """Create a mock work queue that depends on work pool."""
    return WorkQueue(
        id=uuid.uuid4(),
        name="test-queue",
        work_pool_id=mock_work_pool.id,
        work_pool_name=mock_work_pool.name,
    )


@pytest.fixture
def mock_deployment(mock_work_pool):
    """Create a mock deployment that depends on work pool."""
    return Deployment(
        id=uuid.uuid4(),
        name="test-deployment",
        flow_id=uuid.uuid4(),
        work_pool_name=mock_work_pool.name,
        work_queue_name="default",
    )


async def test_dag_construction(mock_work_pool, mock_work_queue, mock_deployment):
    """Test that the DAG correctly builds from resources."""
    # Create migratable resources
    migratable_pool = await construct_migratable_resource(mock_work_pool)
    migratable_queue = await construct_migratable_resource(mock_work_queue)
    migratable_deployment = await construct_migratable_resource(mock_deployment)

    # Mock dependencies to avoid API calls
    migratable_queue.get_dependencies = AsyncMock(return_value=[migratable_pool])
    migratable_deployment.get_dependencies = AsyncMock(return_value=[migratable_pool])

    # Build DAG
    dag = TransferDAG()
    await dag.build_from_roots([migratable_queue, migratable_deployment])

    # Verify structure
    stats = dag.get_statistics()
    assert stats["total_nodes"] == 3
    assert stats["total_edges"] == 2
    assert not stats["has_cycles"]


async def test_dag_execution_order(mock_work_pool, mock_work_queue):
    """Test that resources are executed in dependency order."""
    # Create migratable resources
    migratable_pool = await construct_migratable_resource(mock_work_pool)
    migratable_queue = await construct_migratable_resource(mock_work_queue)

    # Mock dependencies
    migratable_queue.get_dependencies = AsyncMock(return_value=[migratable_pool])

    # Build DAG
    dag = TransferDAG()
    await dag.build_from_roots([migratable_queue])

    # Get execution layers
    layers = dag.get_execution_layers()
    assert len(layers) == 2

    # Pool should be in first layer (no dependencies)
    assert len(layers[0]) == 1
    assert layers[0][0].id == mock_work_pool.id

    # Queue should be in second layer (depends on pool)
    assert len(layers[1]) == 1
    assert layers[1][0].id == mock_work_queue.id


async def test_dag_concurrent_execution(
    mock_work_pool, mock_work_queue, mock_deployment
):
    """Test that independent resources execute concurrently."""
    # Create migratable resources
    migratable_pool = await construct_migratable_resource(mock_work_pool)
    migratable_queue = await construct_migratable_resource(mock_work_queue)
    migratable_deployment = await construct_migratable_resource(mock_deployment)

    # Both depend on pool
    migratable_queue.get_dependencies = AsyncMock(return_value=[migratable_pool])
    migratable_deployment.get_dependencies = AsyncMock(return_value=[migratable_pool])

    # Build DAG
    dag = TransferDAG()
    await dag.build_from_roots([migratable_queue, migratable_deployment])

    # Track execution order
    execution_order = []

    async def track_execution(resource):
        execution_order.append(resource.id)
        await asyncio.sleep(0.01)
        return uuid.uuid4()

    # Execute
    results = await dag.execute_concurrent(track_execution)

    # Pool should execute first
    assert execution_order[0] == mock_work_pool.id
    # Queue and deployment can execute in any order (concurrent)
    assert set(execution_order[1:]) == {mock_work_queue.id, mock_deployment.id}
    assert len(results) == 3


async def test_dag_failure_propagation(mock_work_pool, mock_work_queue):
    """Test that failures skip dependent resources."""
    # Create migratable resources
    migratable_pool = await construct_migratable_resource(mock_work_pool)
    migratable_queue = await construct_migratable_resource(mock_work_queue)

    # Mock dependencies
    migratable_queue.get_dependencies = AsyncMock(return_value=[migratable_pool])

    # Build DAG
    dag = TransferDAG()
    await dag.build_from_roots([migratable_queue])

    # Process function that fails for pool
    async def fail_on_pool(resource):
        if resource.id == mock_work_pool.id:
            raise ValueError("Failed to transfer pool")
        return uuid.uuid4()

    # Execute
    results = await dag.execute_concurrent(fail_on_pool)

    # Pool should have failed
    assert isinstance(results[mock_work_pool.id], ValueError)

    # Queue should be skipped
    assert isinstance(results[mock_work_queue.id], RuntimeError)
    assert "Skipped" in str(results[mock_work_queue.id])


async def test_dag_cycle_detection():
    """Test that the DAG detects cycles."""
    # Create resources with circular dependency
    pool1 = WorkPool(id=uuid.uuid4(), name="pool1", type="k8s", base_job_template={})
    pool2 = WorkPool(id=uuid.uuid4(), name="pool2", type="k8s", base_job_template={})

    migratable1 = await construct_migratable_resource(pool1)
    migratable2 = await construct_migratable_resource(pool2)

    # Create circular dependency
    migratable1.get_dependencies = AsyncMock(return_value=[migratable2])
    migratable2.get_dependencies = AsyncMock(return_value=[migratable1])

    # Build DAG
    dag = TransferDAG()
    await dag.build_from_roots([migratable1])

    # Should detect cycle
    assert dag.has_cycles()

    # Should raise on execution
    with pytest.raises(ValueError, match="Cannot execute DAG with cycles"):
        await dag.execute_concurrent(lambda x: uuid.uuid4())


async def test_dag_deduplication(mock_work_pool):
    """Test that resources are deduplicated by ID."""
    # Create multiple queues depending on same pool
    queue1 = WorkQueue(
        id=uuid.uuid4(),
        name="queue1",
        work_pool_id=mock_work_pool.id,
        work_pool_name=mock_work_pool.name,
    )
    queue2 = WorkQueue(
        id=uuid.uuid4(),
        name="queue2",
        work_pool_id=mock_work_pool.id,
        work_pool_name=mock_work_pool.name,
    )

    migratable_pool = await construct_migratable_resource(mock_work_pool)
    migratable_queue1 = await construct_migratable_resource(queue1)
    migratable_queue2 = await construct_migratable_resource(queue2)

    # Both depend on same pool
    migratable_queue1.get_dependencies = AsyncMock(return_value=[migratable_pool])
    migratable_queue2.get_dependencies = AsyncMock(return_value=[migratable_pool])

    # Build DAG
    dag = TransferDAG()
    await dag.build_from_roots([migratable_queue1, migratable_queue2])

    # Pool should only appear once
    stats = dag.get_statistics()
    assert stats["total_nodes"] == 3  # pool, queue1, queue2
    assert stats["total_edges"] == 2  # queue1->pool, queue2->pool


async def test_dag_strict_skip_on_failure(mock_work_pool, mock_work_queue):
    """Test that READY nodes are skipped when upstream fails."""
    # Create migratable resources
    migratable_pool = await construct_migratable_resource(mock_work_pool)
    migratable_queue = await construct_migratable_resource(mock_work_queue)

    # Mock dependencies
    migratable_queue.get_dependencies = AsyncMock(return_value=[migratable_pool])

    # Build DAG
    dag = TransferDAG()
    await dag.build_from_roots([migratable_queue])

    # Track execution
    executed = set()

    async def track_and_fail(resource):
        executed.add(resource.id)
        if resource.id == mock_work_pool.id:
            await asyncio.sleep(0.1)  # Delay to let queue become READY
            raise ValueError("Failed")
        return uuid.uuid4()

    # Execute
    results = await dag.execute_concurrent(track_and_fail, max_workers=10)

    # Only pool should have executed
    assert mock_work_pool.id in executed
    assert mock_work_queue.id not in executed

    # Queue should be skipped
    assert isinstance(results[mock_work_queue.id], RuntimeError)
