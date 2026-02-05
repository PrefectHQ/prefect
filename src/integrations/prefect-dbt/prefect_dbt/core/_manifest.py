"""
Data structures and parser for dbt manifest.json files.

This module provides:
- DbtNode: Immutable representation of a dbt node
- ExecutionWave: A group of nodes that can execute in parallel
- ManifestParser: Parser for dbt manifest.json with dependency resolution
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from dbt.artifacts.resources.types import NodeType


@dataclass(frozen=True)
class DbtNode:
    """Immutable representation of a dbt node from manifest.json.

    Attributes:
        unique_id: Full dbt identifier (e.g., "model.analytics.stg_users")
        name: Short name (e.g., "stg_users")
        resource_type: Node type from dbt (Model, Source, Test, etc.)
        depends_on: Tuple of unique_ids this node depends on (tuple for hashability)
        materialization: How the node is materialized ("view", "table", "ephemeral", etc.)
        relation_name: Database relation name
        original_file_path: Path to the source SQL/YAML file
        config: Node configuration dictionary
    """

    unique_id: str
    name: str
    resource_type: NodeType
    depends_on: tuple[str, ...] = field(default_factory=tuple)
    materialization: Optional[str] = None
    relation_name: Optional[str] = None
    original_file_path: Optional[str] = None
    config: dict[str, Any] = field(default_factory=dict)

    @property
    def is_executable(self) -> bool:
        """Return False for ephemeral models and sources.

        Ephemeral models are compiled inline and don't produce database objects.
        Sources are external tables and don't need to be executed.
        """
        if self.resource_type == NodeType.Source:
            return False
        if self.materialization == "ephemeral":
            return False
        return True

    @property
    def dbt_selector(self) -> str:
        """Return the dbt selector string for this node.

        This can be used with `dbt run --select <selector>`.
        """
        return self.unique_id

    def __hash__(self) -> int:
        return hash(self.unique_id)


@dataclass
class ExecutionWave:
    """A group of nodes that can be executed in parallel.

    All nodes in a wave have their dependencies satisfied by previous waves.

    Attributes:
        wave_number: Zero-indexed wave number (0 = first wave, no dependencies)
        nodes: List of DbtNode objects that can execute concurrently
    """

    wave_number: int
    nodes: list[DbtNode] = field(default_factory=list)


class ManifestParser:
    """Parser for dbt manifest.json files with dependency resolution.

    This parser:
    - Reads manifest.json directly (not using dbt's Manifest class)
    - Excludes ephemeral models and sources from executable nodes
    - Resolves transitive dependencies through ephemeral models
    - Computes execution waves using Kahn's algorithm

    Example:
        parser = ManifestParser(Path("target/manifest.json"))
        waves = parser.compute_execution_waves()
        for wave in waves:
            print(f"Wave {wave.wave_number}: {[n.name for n in wave.nodes]}")
    """

    def __init__(self, manifest_path: Path):
        """Initialize the parser with a path to manifest.json.

        Args:
            manifest_path: Path to the dbt manifest.json file

        Raises:
            FileNotFoundError: If the manifest file doesn't exist
        """
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

        self._manifest_path = manifest_path
        self._manifest_data: dict[str, Any] = {}
        self._nodes: dict[str, DbtNode] = {}
        self._all_nodes: dict[str, DbtNode] = {}  # includes ephemeral/sources
        self._load_manifest()

    def _load_manifest(self) -> None:
        """Load and parse the manifest.json file."""
        with open(self._manifest_path) as f:
            self._manifest_data = json.load(f)

        self._parse_nodes()

    def _parse_nodes(self) -> None:
        """Parse all nodes from the manifest data."""
        # Parse regular nodes (models, tests, snapshots, seeds, etc.)
        nodes_data = self._manifest_data.get("nodes", {})
        for unique_id, node_data in nodes_data.items():
            dbt_node = self._create_node(unique_id, node_data)
            self._all_nodes[unique_id] = dbt_node

        # Parse sources
        sources_data = self._manifest_data.get("sources", {})
        for unique_id, source_data in sources_data.items():
            dbt_node = self._create_source_node(unique_id, source_data)
            self._all_nodes[unique_id] = dbt_node

    def _create_node(self, unique_id: str, node_data: dict[str, Any]) -> DbtNode:
        """Create a DbtNode from manifest node data."""
        resource_type_str = node_data.get("resource_type", "model")
        try:
            resource_type = NodeType(resource_type_str)
        except ValueError:
            # Fall back to model if unknown type
            resource_type = NodeType.Model

        # Get depends_on nodes
        depends_on_data = node_data.get("depends_on", {})
        depends_on_nodes = depends_on_data.get("nodes", [])

        # Get materialization from config
        config = node_data.get("config", {})
        materialization = config.get("materialized")

        return DbtNode(
            unique_id=unique_id,
            name=node_data.get("name", ""),
            resource_type=resource_type,
            depends_on=tuple(depends_on_nodes),
            materialization=materialization,
            relation_name=node_data.get("relation_name"),
            original_file_path=node_data.get("original_file_path"),
            config=config,
        )

    def _create_source_node(
        self, unique_id: str, source_data: dict[str, Any]
    ) -> DbtNode:
        """Create a DbtNode from manifest source data."""
        return DbtNode(
            unique_id=unique_id,
            name=source_data.get("name", ""),
            resource_type=NodeType.Source,
            depends_on=tuple(),  # Sources have no dependencies
            materialization=None,
            relation_name=source_data.get("relation_name"),
            original_file_path=source_data.get("original_file_path"),
            config=source_data.get("config", {}),
        )

    def _resolve_dependencies_through_ephemeral(self, node: DbtNode) -> tuple[str, ...]:
        """Resolve dependencies, tracing through ephemeral models.

        Ephemeral models are compiled inline, so we need to find the
        actual executable dependencies by traversing through them.

        Args:
            node: The node to resolve dependencies for

        Returns:
            Tuple of unique_ids of executable dependencies
        """
        resolved: list[str] = []
        visited: set[str] = set()

        def collect(dep_id: str) -> None:
            if dep_id in visited:
                return
            visited.add(dep_id)

            dep_node = self._all_nodes.get(dep_id)
            if dep_node is None:
                return

            # Skip sources without relation_name
            if dep_node.resource_type == NodeType.Source and not dep_node.relation_name:
                return

            # For ephemeral nodes, trace through to their dependencies
            if dep_node.materialization == "ephemeral":
                for nested_dep in dep_node.depends_on:
                    collect(nested_dep)
                return

            # This is an executable dependency
            if dep_node.is_executable:
                resolved.append(dep_id)

        for dep_id in node.depends_on:
            collect(dep_id)

        return tuple(resolved)

    def get_executable_nodes(self) -> dict[str, DbtNode]:
        """Get all executable nodes (excluding ephemeral models and sources).

        Returns:
            Dictionary mapping unique_id to DbtNode for executable nodes.
            Dependencies are resolved through ephemeral models.
        """
        if self._nodes:
            return self._nodes

        for unique_id, node in self._all_nodes.items():
            if not node.is_executable:
                continue

            # Resolve dependencies through ephemeral models
            resolved_deps = self._resolve_dependencies_through_ephemeral(node)

            # Create new node with resolved dependencies
            resolved_node = DbtNode(
                unique_id=node.unique_id,
                name=node.name,
                resource_type=node.resource_type,
                depends_on=resolved_deps,
                materialization=node.materialization,
                relation_name=node.relation_name,
                original_file_path=node.original_file_path,
                config=node.config,
            )
            self._nodes[unique_id] = resolved_node

        return self._nodes

    def get_node_dependencies(self, node_id: str) -> list[str]:
        """Get the resolved dependencies for a specific node.

        Args:
            node_id: The unique_id of the node

        Returns:
            List of unique_ids that this node depends on (resolved through ephemeral)

        Raises:
            KeyError: If the node_id is not found
        """
        nodes = self.get_executable_nodes()
        if node_id not in nodes:
            raise KeyError(f"Node not found: {node_id}")
        return list(nodes[node_id].depends_on)

    def compute_execution_waves(self) -> list[ExecutionWave]:
        """Compute execution waves using Kahn's algorithm.

        Each wave contains nodes that can be executed in parallel.
        Wave 0 contains nodes with no dependencies. Wave N contains
        nodes whose dependencies are all in waves 0 through N-1.

        Returns:
            List of ExecutionWave objects in execution order

        Raises:
            ValueError: If the dependency graph contains cycles
        """
        nodes = self.get_executable_nodes()

        if not nodes:
            return []

        # Build in-degree map (count of unresolved dependencies)
        in_degree: dict[str, int] = {}
        for node_id, node in nodes.items():
            # Only count dependencies that are in our executable nodes
            deps_in_graph = [d for d in node.depends_on if d in nodes]
            in_degree[node_id] = len(deps_in_graph)

        # Build dependents map (who depends on each node)
        dependents: dict[str, list[str]] = {node_id: [] for node_id in nodes}
        for node_id, node in nodes.items():
            for dep_id in node.depends_on:
                if dep_id in dependents:
                    dependents[dep_id].append(node_id)

        # Kahn's algorithm
        waves: list[ExecutionWave] = []
        current_wave = [node_id for node_id, degree in in_degree.items() if degree == 0]

        processed_count = 0
        wave_number = 0

        while current_wave:
            # Create wave with current nodes
            wave_nodes = [nodes[node_id] for node_id in current_wave]
            waves.append(ExecutionWave(wave_number=wave_number, nodes=wave_nodes))
            processed_count += len(current_wave)

            # Find next wave
            next_wave: list[str] = []
            for node_id in current_wave:
                for dependent_id in dependents[node_id]:
                    in_degree[dependent_id] -= 1
                    if in_degree[dependent_id] == 0:
                        next_wave.append(dependent_id)

            current_wave = next_wave
            wave_number += 1

        # Check for cycles
        if processed_count != len(nodes):
            raise ValueError(
                "Dependency graph contains cycles. "
                f"Processed {processed_count} of {len(nodes)} nodes."
            )

        return waves

    def filter_nodes(
        self,
        select: Optional[list[str]] = None,
        exclude: Optional[list[str]] = None,
    ) -> dict[str, DbtNode]:
        """Filter nodes by selection criteria.

        Note: This is a stub for Phase 2. Currently returns all executable nodes.
        Phase 2 will implement proper dbt selector syntax via `dbt ls` delegation.

        Args:
            select: Node selectors to include (Phase 2)
            exclude: Node selectors to exclude (Phase 2)

        Returns:
            Dictionary of filtered executable nodes
        """
        # Stub: return all executable nodes
        # Phase 2 will implement proper filtering via dbt ls
        return self.get_executable_nodes()
