"""
Execution DAG for managing resource transfer dependencies.

This module provides a pure execution engine that:
- Stores nodes by UUID for deduplication
- Implements Kahn's algorithm for topological sorting
- Manages concurrent execution with worker pools
- Handles failure propagation (skip descendants)
"""

from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Coroutine, Sequence

import anyio
from anyio import create_task_group
from anyio.abc import TaskGroup

from prefect.cli.transfer._exceptions import TransferSkipped
from prefect.cli.transfer._migratable_resources import MigratableProtocol
from prefect.logging import get_logger

logger = get_logger(__name__)


class NodeState(Enum):
    """State of a node during traversal."""

    PENDING = "pending"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class NodeStatus:
    """Tracks the status of a node during traversal."""

    node: MigratableProtocol
    state: NodeState = NodeState.PENDING
    dependents: set[uuid.UUID] = field(default_factory=set)
    dependencies: set[uuid.UUID] = field(default_factory=set)
    error: Exception | None = None


class TransferDAG:
    """
    Execution DAG for managing resource transfer dependencies.

    Uses Kahn's algorithm for topological sorting and concurrent execution.
    See: https://en.wikipedia.org/wiki/Topological_sorting#Kahn%27s_algorithm

    The DAG ensures resources are transferred in dependency order while
    maximizing parallelism for independent resources.
    """

    def __init__(self):
        self.nodes: dict[uuid.UUID, MigratableProtocol] = {}
        self._dependencies: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
        self._dependents: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
        self._status: dict[uuid.UUID, NodeStatus] = {}
        self._lock = asyncio.Lock()

    def add_node(self, node: MigratableProtocol) -> uuid.UUID:
        """
        Add a node to the graph, deduplicating by source ID.

        Args:
            node: Resource to add to the graph

        Returns:
            The node's source UUID
        """
        if node.source_id not in self.nodes:
            self.nodes[node.source_id] = node
            self._status[node.source_id] = NodeStatus(node)
        return node.source_id

    def add_edge(self, dependent_id: uuid.UUID, dependency_id: uuid.UUID) -> None:
        """
        Add a dependency edge where dependent depends on dependency.

        Args:
            dependent_id: ID of the resource that has a dependency
            dependency_id: ID of the resource being depended upon
        """
        if dependency_id in self._dependencies[dependent_id]:
            return

        self._dependencies[dependent_id].add(dependency_id)
        self._dependents[dependency_id].add(dependent_id)

        self._status[dependent_id].dependencies.add(dependency_id)
        self._status[dependency_id].dependents.add(dependent_id)

    async def build_from_roots(self, roots: Sequence[MigratableProtocol]) -> None:
        """
        Build the graph from root resources by recursively discovering dependencies.

        Args:
            roots: Collection of root resources to start discovery from
        """
        visited: set[uuid.UUID] = set()

        async def visit(resource: MigratableProtocol):
            if resource.source_id in visited:
                return
            visited.add(resource.source_id)

            rid = self.add_node(resource)

            visit_coroutines: list[Coroutine[Any, Any, None]] = []
            for dep in await resource.get_dependencies():
                did = self.add_node(dep)
                self.add_edge(rid, did)
                visit_coroutines.append(visit(dep))
            await asyncio.gather(*visit_coroutines)

        visit_coroutines = [visit(r) for r in roots]
        await asyncio.gather(*visit_coroutines)

    def has_cycles(self) -> bool:
        """
        Check if the graph has cycles using three-color DFS.

        Uses the classic three-color algorithm where:
        - WHITE (0): Unvisited node
        - GRAY (1): Currently being explored (in DFS stack)
        - BLACK (2): Fully explored

        A cycle exists if we encounter a GRAY node during traversal (back edge).
        See: https://en.wikipedia.org/wiki/Depth-first_search#Vertex_orderings

        Returns:
            True if the graph contains cycles, False otherwise
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {node_id: WHITE for node_id in self.nodes}

        def visit(node_id: uuid.UUID) -> bool:
            if color[node_id] == GRAY:
                return True  # Back edge found - cycle detected
            if color[node_id] == BLACK:
                return False  # Already fully explored

            color[node_id] = GRAY
            for dep_id in self._dependencies[node_id]:
                if visit(dep_id):
                    return True
            color[node_id] = BLACK
            return False

        for node_id in self.nodes:
            if color[node_id] == WHITE:
                if visit(node_id):
                    return True
        return False

    def get_execution_layers(
        self, *, _assume_acyclic: bool = False
    ) -> list[list[MigratableProtocol]]:
        """
        Get execution layers using Kahn's algorithm.

        Each layer contains nodes that can be executed in parallel.
        Kahn's algorithm repeatedly removes nodes with no dependencies,
        forming layers of concurrent work.

        See: https://en.wikipedia.org/wiki/Topological_sorting#Kahn%27s_algorithm

        Args:
            _assume_acyclic: Skip cycle check if caller already verified

        Returns:
            List of layers, each containing nodes that can run in parallel

        Raises:
            ValueError: If the graph contains cycles
        """
        if not _assume_acyclic and self.has_cycles():
            raise ValueError("Cannot sort DAG with cycles")

        in_degree = {n: len(self._dependencies[n]) for n in self.nodes}

        layers: list[list[MigratableProtocol]] = []
        cur = [n for n in self.nodes if in_degree[n] == 0]

        while cur:
            layers.append([self.nodes[n] for n in cur])
            nxt: list[uuid.UUID] = []
            for n in cur:
                for d in self._dependents[n]:
                    in_degree[d] -= 1
                    if in_degree[d] == 0:
                        nxt.append(d)
            cur = nxt

        return layers

    async def execute_concurrent(
        self,
        process_node: Callable[[MigratableProtocol], Awaitable[Any]],
        max_workers: int = 10,
        skip_on_failure: bool = True,
    ) -> dict[uuid.UUID, Any]:
        """
        Execute the DAG concurrently using Kahn's algorithm.

        Processes nodes in topological order while maximizing parallelism.
        When a node completes, its dependents are checked to see if they're
        ready to execute (all dependencies satisfied).

        Args:
            process_node: Async function to process each node
            max_workers: Maximum number of concurrent workers
            skip_on_failure: Whether to skip descendants when a node fails

        Returns:
            Dictionary mapping node IDs to their results (or exceptions)

        Raises:
            ValueError: If the graph contains cycles
        """
        if self.has_cycles():
            raise ValueError("Cannot execute DAG with cycles")

        layers = self.get_execution_layers(_assume_acyclic=True)
        logger.debug(f"Execution plan has {len(layers)} layers")
        for i, layer in enumerate(layers):
            # Count each type in the layer
            type_counts: dict[str, int] = {}
            for node in layer:
                node_type = type(node).__name__
                type_counts[node_type] = type_counts.get(node_type, 0) + 1

            type_summary = ", ".join(
                [f"{count} {type_name}" for type_name, count in type_counts.items()]
            )
            logger.debug(f"Layer {i}: ({type_summary})")

        # Initialize with nodes that have no dependencies
        ready_queue: list[uuid.UUID] = []
        for nid in self.nodes:
            if not self._dependencies[nid]:
                ready_queue.append(nid)
                self._status[nid].state = NodeState.READY

        results: dict[uuid.UUID, Any] = {}
        limiter = anyio.CapacityLimiter(max_workers)
        processing: set[uuid.UUID] = set()

        async def worker(nid: uuid.UUID, tg: TaskGroup):
            """Process a single node."""
            node = self.nodes[nid]

            # Check if node was skipped after being queued
            if self._status[nid].state != NodeState.READY:
                logger.debug(f"Node {node} was skipped before execution")
                return

            async with limiter:
                try:
                    self._status[nid].state = NodeState.IN_PROGRESS
                    logger.debug(f"Processing {node}")

                    res = await process_node(node)
                    results[nid] = res

                    self._status[nid].state = NodeState.COMPLETED
                    logger.debug(f"Completed {node}")

                    # Mark dependents as ready if all their dependencies are satisfied
                    async with self._lock:
                        for did in self._status[nid].dependents:
                            dst = self._status[did]
                            if dst.state == NodeState.PENDING:
                                if all(
                                    self._status[d].state == NodeState.COMPLETED
                                    for d in dst.dependencies
                                ):
                                    dst.state = NodeState.READY
                                    # Start the newly ready task immediately
                                    if did not in processing:
                                        processing.add(did)
                                        tg.start_soon(worker, did, tg)

                except TransferSkipped as e:
                    results[nid] = e
                    self._status[nid].state = NodeState.SKIPPED
                    self._status[nid].error = e
                    logger.debug(f"Skipped {node}: {e}")

                except Exception as e:
                    results[nid] = e
                    self._status[nid].state = NodeState.FAILED
                    self._status[nid].error = e
                    logger.debug(f"Failed to process {node}: {e}")

                    if skip_on_failure:
                        # Skip all descendants of the failed node
                        to_skip = deque([nid])
                        seen_failed: set[uuid.UUID] = set()

                        while to_skip:
                            cur = to_skip.popleft()
                            if cur in seen_failed:
                                continue
                            seen_failed.add(cur)

                            for did in self._status[cur].dependents:
                                st = self._status[did]
                                # Skip nodes that haven't started yet
                                if st.state in {NodeState.PENDING, NodeState.READY}:
                                    st.state = NodeState.SKIPPED
                                    results[did] = TransferSkipped(
                                        "Skipped due to upstream resource failure"
                                    )
                                    logger.debug(
                                        f"Skipped {self.nodes[did]} due to upstream failure"
                                    )
                                    to_skip.append(did)
                finally:
                    processing.discard(nid)

        async with create_task_group() as tg:
            # Start processing all initially ready nodes
            for nid in ready_queue:
                if self._status[nid].state == NodeState.READY:
                    processing.add(nid)
                    tg.start_soon(worker, nid, tg)

        return results

    def get_statistics(self) -> dict[str, Any]:
        """
        Get statistics about the DAG structure.

        Returns:
            Dictionary with node counts, edge counts, and cycle detection
        """
        deps = self._dependencies
        return {
            "total_nodes": len(self.nodes),
            "total_edges": sum(len(v) for v in deps.values()),
            "max_in_degree": max((len(deps[n]) for n in self.nodes), default=0),
            "max_out_degree": max(
                (len(self._dependents[n]) for n in self.nodes), default=0
            ),
            "has_cycles": self.has_cycles(),
        }
