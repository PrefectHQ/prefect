"""
Tests for DbtNode, ExecutionWave, and ManifestParser.
"""

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from dbt.artifacts.resources.types import NodeType
from prefect_dbt.core._manifest import (
    DbtLsError,
    DbtNode,
    ExecutionWave,
    ManifestParser,
    resolve_selection,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def minimal_manifest_data() -> dict[str, Any]:
    """Create minimal manifest data with a single model."""
    return {
        "nodes": {
            "model.test_project.my_model": {
                "name": "my_model",
                "resource_type": "model",
                "depends_on": {"nodes": []},
                "config": {"materialized": "table"},
                "relation_name": '"db"."schema"."my_model"',
                "original_file_path": "models/my_model.sql",
            }
        },
        "sources": {},
    }


@pytest.fixture
def manifest_with_ephemeral() -> dict[str, Any]:
    """Create manifest with ephemeral model chain: final -> ephemeral -> source_model."""
    return {
        "nodes": {
            "model.test_project.source_model": {
                "name": "source_model",
                "resource_type": "model",
                "depends_on": {"nodes": []},
                "config": {"materialized": "table"},
                "relation_name": '"db"."schema"."source_model"',
                "original_file_path": "models/source_model.sql",
            },
            "model.test_project.ephemeral_model": {
                "name": "ephemeral_model",
                "resource_type": "model",
                "depends_on": {"nodes": ["model.test_project.source_model"]},
                "config": {"materialized": "ephemeral"},
                "relation_name": None,
                "original_file_path": "models/ephemeral_model.sql",
            },
            "model.test_project.final_model": {
                "name": "final_model",
                "resource_type": "model",
                "depends_on": {"nodes": ["model.test_project.ephemeral_model"]},
                "config": {"materialized": "view"},
                "relation_name": '"db"."schema"."final_model"',
                "original_file_path": "models/final_model.sql",
            },
        },
        "sources": {},
    }


@pytest.fixture
def diamond_dependency_manifest() -> dict[str, Any]:
    """Create diamond dependency pattern: root -> left/right -> leaf.

    Execution waves should be:
    - Wave 0: root
    - Wave 1: left, right
    - Wave 2: leaf
    """
    return {
        "nodes": {
            "model.test_project.root": {
                "name": "root",
                "resource_type": "model",
                "depends_on": {"nodes": []},
                "config": {"materialized": "table"},
                "relation_name": '"db"."schema"."root"',
                "original_file_path": "models/root.sql",
            },
            "model.test_project.left": {
                "name": "left",
                "resource_type": "model",
                "depends_on": {"nodes": ["model.test_project.root"]},
                "config": {"materialized": "table"},
                "relation_name": '"db"."schema"."left"',
                "original_file_path": "models/left.sql",
            },
            "model.test_project.right": {
                "name": "right",
                "resource_type": "model",
                "depends_on": {"nodes": ["model.test_project.root"]},
                "config": {"materialized": "table"},
                "relation_name": '"db"."schema"."right"',
                "original_file_path": "models/right.sql",
            },
            "model.test_project.leaf": {
                "name": "leaf",
                "resource_type": "model",
                "depends_on": {
                    "nodes": [
                        "model.test_project.left",
                        "model.test_project.right",
                    ]
                },
                "config": {"materialized": "table"},
                "relation_name": '"db"."schema"."leaf"',
                "original_file_path": "models/leaf.sql",
            },
        },
        "sources": {},
    }


@pytest.fixture
def manifest_with_sources() -> dict[str, Any]:
    """Create manifest with source dependencies."""
    return {
        "nodes": {
            "model.test_project.staging_model": {
                "name": "staging_model",
                "resource_type": "model",
                "depends_on": {"nodes": ["source.test_project.raw.users"]},
                "config": {"materialized": "view"},
                "relation_name": '"db"."schema"."staging_model"',
                "original_file_path": "models/staging_model.sql",
            },
        },
        "sources": {
            "source.test_project.raw.users": {
                "name": "users",
                "resource_type": "source",
                "relation_name": '"raw"."users"',
                "original_file_path": "models/sources.yml",
                "config": {},
            },
        },
    }


@pytest.fixture
def cyclic_manifest() -> dict[str, Any]:
    """Create manifest with cyclic dependencies: a -> b -> c -> a."""
    return {
        "nodes": {
            "model.test_project.model_a": {
                "name": "model_a",
                "resource_type": "model",
                "depends_on": {"nodes": ["model.test_project.model_c"]},
                "config": {"materialized": "table"},
                "relation_name": '"db"."schema"."model_a"',
                "original_file_path": "models/model_a.sql",
            },
            "model.test_project.model_b": {
                "name": "model_b",
                "resource_type": "model",
                "depends_on": {"nodes": ["model.test_project.model_a"]},
                "config": {"materialized": "table"},
                "relation_name": '"db"."schema"."model_b"',
                "original_file_path": "models/model_b.sql",
            },
            "model.test_project.model_c": {
                "name": "model_c",
                "resource_type": "model",
                "depends_on": {"nodes": ["model.test_project.model_b"]},
                "config": {"materialized": "table"},
                "relation_name": '"db"."schema"."model_c"',
                "original_file_path": "models/model_c.sql",
            },
        },
        "sources": {},
    }


def write_manifest(tmp_path: Path, data: dict[str, Any]) -> Path:
    """Helper to write manifest data to a file."""
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(data))
    return manifest_path


# =============================================================================
# DbtNode Tests
# =============================================================================


class TestDbtNode:
    """Tests for the DbtNode dataclass."""

    def test_is_executable_table(self):
        """Table materialization should be executable."""
        node = DbtNode(
            unique_id="model.test.my_model",
            name="my_model",
            resource_type=NodeType.Model,
            materialization="table",
        )
        assert node.is_executable is True

    def test_is_executable_view(self):
        """View materialization should be executable."""
        node = DbtNode(
            unique_id="model.test.my_model",
            name="my_model",
            resource_type=NodeType.Model,
            materialization="view",
        )
        assert node.is_executable is True

    def test_is_executable_incremental(self):
        """Incremental materialization should be executable."""
        node = DbtNode(
            unique_id="model.test.my_model",
            name="my_model",
            resource_type=NodeType.Model,
            materialization="incremental",
        )
        assert node.is_executable is True

    def test_is_executable_ephemeral(self):
        """Ephemeral materialization should NOT be executable."""
        node = DbtNode(
            unique_id="model.test.my_model",
            name="my_model",
            resource_type=NodeType.Model,
            materialization="ephemeral",
        )
        assert node.is_executable is False

    def test_is_executable_source(self):
        """Source nodes should NOT be executable."""
        node = DbtNode(
            unique_id="source.test.raw.users",
            name="users",
            resource_type=NodeType.Source,
        )
        assert node.is_executable is False

    def test_is_executable_seed(self):
        """Seed nodes should be executable."""
        node = DbtNode(
            unique_id="seed.test.my_seed",
            name="my_seed",
            resource_type=NodeType.Seed,
        )
        assert node.is_executable is True

    def test_is_executable_snapshot(self):
        """Snapshot nodes should be executable."""
        node = DbtNode(
            unique_id="snapshot.test.my_snapshot",
            name="my_snapshot",
            resource_type=NodeType.Snapshot,
        )
        assert node.is_executable is True

    def test_is_executable_test(self):
        """Test nodes should NOT be executable (they use `dbt test`)."""
        node = DbtNode(
            unique_id="test.test.my_test",
            name="my_test",
            resource_type=NodeType.Test,
        )
        assert node.is_executable is False

    def test_is_executable_exposure(self):
        """Exposure nodes should NOT be executable."""
        node = DbtNode(
            unique_id="exposure.test.my_exposure",
            name="my_exposure",
            resource_type=NodeType.Exposure,
        )
        assert node.is_executable is False

    def test_dbt_selector_uses_path(self):
        """dbt_selector should return path:<file> when original_file_path is set."""
        node = DbtNode(
            unique_id="model.analytics.stg_users",
            name="stg_users",
            resource_type=NodeType.Model,
            fqn=("analytics", "staging", "stg_users"),
            original_file_path="models/staging/stg_users.sql",
        )
        assert node.dbt_selector == "path:models/staging/stg_users.sql"

    def test_dbt_selector_falls_back_to_fqn(self):
        """dbt_selector should fall back to FQN when file path is absent."""
        node = DbtNode(
            unique_id="model.analytics.stg_users",
            name="stg_users",
            resource_type=NodeType.Model,
            fqn=("analytics", "staging", "stg_users"),
        )
        assert node.dbt_selector == "analytics.staging.stg_users"

    def test_dbt_selector_falls_back_to_name(self):
        """dbt_selector should fall back to name when FQN and path are empty."""
        node = DbtNode(
            unique_id="model.analytics.stg_users",
            name="stg_users",
            resource_type=NodeType.Model,
        )
        assert node.dbt_selector == "stg_users"

    def test_dbt_selector_skips_path_for_non_runnable_types(self):
        """Test nodes share YAML files, so path: would over-select; fall back to FQN."""
        node = DbtNode(
            unique_id="test.analytics.not_null_stg_users_id",
            name="not_null_stg_users_id",
            resource_type=NodeType.Test,
            fqn=("analytics", "not_null_stg_users_id"),
            original_file_path="models/staging/schema.yml",
        )
        assert node.dbt_selector == "analytics.not_null_stg_users_id"

    def test_hashability(self):
        """DbtNode should be hashable (usable in sets/dicts)."""
        node1 = DbtNode(
            unique_id="model.test.my_model",
            name="my_model",
            resource_type=NodeType.Model,
            depends_on=("model.test.other",),
        )
        node2 = DbtNode(
            unique_id="model.test.my_model",
            name="my_model",
            resource_type=NodeType.Model,
            depends_on=("model.test.other",),
        )

        # Should be hashable
        node_set = {node1, node2}
        assert len(node_set) == 1

        # Should work as dict key
        node_dict = {node1: "value"}
        assert node_dict[node2] == "value"

    def test_immutability(self):
        """DbtNode should be immutable (frozen=True)."""
        node = DbtNode(
            unique_id="model.test.my_model",
            name="my_model",
            resource_type=NodeType.Model,
        )
        with pytest.raises(AttributeError):
            node.name = "new_name"  # type: ignore[misc]

    def test_equality(self):
        """DbtNodes with same attributes should be equal."""
        node1 = DbtNode(
            unique_id="model.test.my_model",
            name="my_model",
            resource_type=NodeType.Model,
            depends_on=("dep1", "dep2"),
        )
        node2 = DbtNode(
            unique_id="model.test.my_model",
            name="my_model",
            resource_type=NodeType.Model,
            depends_on=("dep1", "dep2"),
        )
        assert node1 == node2

    def test_depends_on_as_tuple(self):
        """depends_on should be a tuple for hashability."""
        node = DbtNode(
            unique_id="model.test.my_model",
            name="my_model",
            resource_type=NodeType.Model,
            depends_on=("dep1", "dep2"),
        )
        assert isinstance(node.depends_on, tuple)
        assert node.depends_on == ("dep1", "dep2")


# =============================================================================
# ExecutionWave Tests
# =============================================================================


class TestExecutionWave:
    """Tests for the ExecutionWave dataclass."""

    def test_creation(self):
        """ExecutionWave should store wave number and nodes."""
        node = DbtNode(
            unique_id="model.test.my_model",
            name="my_model",
            resource_type=NodeType.Model,
        )
        wave = ExecutionWave(wave_number=0, nodes=[node])

        assert wave.wave_number == 0
        assert len(wave.nodes) == 1
        assert wave.nodes[0] == node

    def test_empty_wave(self):
        """ExecutionWave can be created with no nodes."""
        wave = ExecutionWave(wave_number=0, nodes=[])
        assert wave.wave_number == 0
        assert wave.nodes == []

    def test_multiple_nodes(self):
        """ExecutionWave can contain multiple nodes."""
        nodes = [
            DbtNode(
                unique_id=f"model.test.model_{i}",
                name=f"model_{i}",
                resource_type=NodeType.Model,
            )
            for i in range(3)
        ]
        wave = ExecutionWave(wave_number=1, nodes=nodes)

        assert wave.wave_number == 1
        assert len(wave.nodes) == 3


# =============================================================================
# ManifestParser Tests
# =============================================================================


class TestManifestParser:
    """Tests for the ManifestParser class."""

    def test_file_not_found(self, tmp_path: Path):
        """Should raise FileNotFoundError for missing manifest."""
        with pytest.raises(FileNotFoundError, match="Manifest file not found"):
            ManifestParser(tmp_path / "nonexistent.json")

    def test_parse_minimal_manifest(
        self, tmp_path: Path, minimal_manifest_data: dict[str, Any]
    ):
        """Should parse a minimal manifest with one model."""
        manifest_path = write_manifest(tmp_path, minimal_manifest_data)
        parser = ManifestParser(manifest_path)

        nodes = parser.get_executable_nodes()
        assert len(nodes) == 1
        assert "model.test_project.my_model" in nodes

        node = nodes["model.test_project.my_model"]
        assert node.name == "my_model"
        assert node.resource_type == NodeType.Model
        assert node.materialization == "table"
        assert node.depends_on == ()

    def test_exclude_ephemeral(
        self, tmp_path: Path, manifest_with_ephemeral: dict[str, Any]
    ):
        """Should exclude ephemeral models from executable nodes."""
        manifest_path = write_manifest(tmp_path, manifest_with_ephemeral)
        parser = ManifestParser(manifest_path)

        nodes = parser.get_executable_nodes()
        node_names = {n.name for n in nodes.values()}

        assert "source_model" in node_names
        assert "final_model" in node_names
        assert "ephemeral_model" not in node_names

    def test_resolve_dependencies_through_ephemeral(
        self, tmp_path: Path, manifest_with_ephemeral: dict[str, Any]
    ):
        """Should resolve dependencies through ephemeral models."""
        manifest_path = write_manifest(tmp_path, manifest_with_ephemeral)
        parser = ManifestParser(manifest_path)

        nodes = parser.get_executable_nodes()
        final_model = nodes["model.test_project.final_model"]

        # final_model depends on ephemeral_model which depends on source_model
        # Resolved dependency should be directly to source_model
        assert "model.test_project.source_model" in final_model.depends_on
        assert "model.test_project.ephemeral_model" not in final_model.depends_on

    def test_exclude_sources(
        self, tmp_path: Path, manifest_with_sources: dict[str, Any]
    ):
        """Should exclude source nodes from executable nodes."""
        manifest_path = write_manifest(tmp_path, manifest_with_sources)
        parser = ManifestParser(manifest_path)

        nodes = parser.get_executable_nodes()

        # Source should not be in executable nodes
        assert "source.test_project.raw.users" not in nodes

        # Model should be present
        assert "model.test_project.staging_model" in nodes

    def test_get_node_dependencies(
        self, tmp_path: Path, diamond_dependency_manifest: dict[str, Any]
    ):
        """Should return dependencies for a specific node."""
        manifest_path = write_manifest(tmp_path, diamond_dependency_manifest)
        parser = ManifestParser(manifest_path)

        deps = parser.get_node_dependencies("model.test_project.leaf")
        assert set(deps) == {
            "model.test_project.left",
            "model.test_project.right",
        }

    def test_get_node_dependencies_not_found(
        self, tmp_path: Path, minimal_manifest_data: dict[str, Any]
    ):
        """Should raise KeyError for unknown node."""
        manifest_path = write_manifest(tmp_path, minimal_manifest_data)
        parser = ManifestParser(manifest_path)

        with pytest.raises(KeyError, match="Node not found"):
            parser.get_node_dependencies("model.test_project.nonexistent")

    def test_filter_nodes_none_returns_all(
        self, tmp_path: Path, minimal_manifest_data: dict[str, Any]
    ):
        """filter_nodes(None) returns all executable nodes."""
        manifest_path = write_manifest(tmp_path, minimal_manifest_data)
        parser = ManifestParser(manifest_path)

        filtered = parser.filter_nodes()
        assert filtered == parser.get_executable_nodes()

        filtered = parser.filter_nodes(selected_node_ids=None)
        assert filtered == parser.get_executable_nodes()


# =============================================================================
# ExecutionWave Computation Tests
# =============================================================================


class TestComputeExecutionWaves:
    """Tests for ManifestParser.compute_execution_waves()."""

    def test_empty_manifest(self, tmp_path: Path):
        """Empty manifest should return no waves."""
        manifest_path = write_manifest(tmp_path, {"nodes": {}, "sources": {}})
        parser = ManifestParser(manifest_path)

        waves = parser.compute_execution_waves()
        assert waves == []

    def test_single_node(self, tmp_path: Path, minimal_manifest_data: dict[str, Any]):
        """Single node should produce one wave."""
        manifest_path = write_manifest(tmp_path, minimal_manifest_data)
        parser = ManifestParser(manifest_path)

        waves = parser.compute_execution_waves()
        assert len(waves) == 1
        assert waves[0].wave_number == 0
        assert len(waves[0].nodes) == 1
        assert waves[0].nodes[0].name == "my_model"

    def test_diamond_pattern(
        self, tmp_path: Path, diamond_dependency_manifest: dict[str, Any]
    ):
        """Diamond pattern should produce 3 waves."""
        manifest_path = write_manifest(tmp_path, diamond_dependency_manifest)
        parser = ManifestParser(manifest_path)

        waves = parser.compute_execution_waves()

        assert len(waves) == 3

        # Wave 0: root (no dependencies)
        assert waves[0].wave_number == 0
        wave0_names = {n.name for n in waves[0].nodes}
        assert wave0_names == {"root"}

        # Wave 1: left and right (depend on root)
        assert waves[1].wave_number == 1
        wave1_names = {n.name for n in waves[1].nodes}
        assert wave1_names == {"left", "right"}

        # Wave 2: leaf (depends on left and right)
        assert waves[2].wave_number == 2
        wave2_names = {n.name for n in waves[2].nodes}
        assert wave2_names == {"leaf"}

    def test_linear_chain(self, tmp_path: Path):
        """Linear chain a -> b -> c should produce 3 waves."""
        manifest_data = {
            "nodes": {
                "model.test_project.model_a": {
                    "name": "model_a",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                    "relation_name": '"db"."schema"."model_a"',
                    "original_file_path": "models/model_a.sql",
                },
                "model.test_project.model_b": {
                    "name": "model_b",
                    "resource_type": "model",
                    "depends_on": {"nodes": ["model.test_project.model_a"]},
                    "config": {"materialized": "table"},
                    "relation_name": '"db"."schema"."model_b"',
                    "original_file_path": "models/model_b.sql",
                },
                "model.test_project.model_c": {
                    "name": "model_c",
                    "resource_type": "model",
                    "depends_on": {"nodes": ["model.test_project.model_b"]},
                    "config": {"materialized": "table"},
                    "relation_name": '"db"."schema"."model_c"',
                    "original_file_path": "models/model_c.sql",
                },
            },
            "sources": {},
        }
        manifest_path = write_manifest(tmp_path, manifest_data)
        parser = ManifestParser(manifest_path)

        waves = parser.compute_execution_waves()

        assert len(waves) == 3
        assert waves[0].nodes[0].name == "model_a"
        assert waves[1].nodes[0].name == "model_b"
        assert waves[2].nodes[0].name == "model_c"

    def test_parallel_independent_nodes(self, tmp_path: Path):
        """Independent nodes should be in wave 0."""
        manifest_data = {
            "nodes": {
                f"model.test_project.model_{i}": {
                    "name": f"model_{i}",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                    "relation_name": f'"db"."schema"."model_{i}"',
                    "original_file_path": f"models/model_{i}.sql",
                }
                for i in range(5)
            },
            "sources": {},
        }
        manifest_path = write_manifest(tmp_path, manifest_data)
        parser = ManifestParser(manifest_path)

        waves = parser.compute_execution_waves()

        assert len(waves) == 1
        assert waves[0].wave_number == 0
        assert len(waves[0].nodes) == 5

    def test_cycle_detection(self, tmp_path: Path, cyclic_manifest: dict[str, Any]):
        """Should raise ValueError when cycles are detected."""
        manifest_path = write_manifest(tmp_path, cyclic_manifest)
        parser = ManifestParser(manifest_path)

        with pytest.raises(ValueError, match="contains cycles"):
            parser.compute_execution_waves()

    def test_waves_with_ephemeral_resolution(
        self, tmp_path: Path, manifest_with_ephemeral: dict[str, Any]
    ):
        """Waves should respect resolved dependencies through ephemeral."""
        manifest_path = write_manifest(tmp_path, manifest_with_ephemeral)
        parser = ManifestParser(manifest_path)

        waves = parser.compute_execution_waves()

        # Should have 2 waves: source_model, then final_model
        # (ephemeral_model is excluded)
        assert len(waves) == 2

        wave0_names = {n.name for n in waves[0].nodes}
        wave1_names = {n.name for n in waves[1].nodes}

        assert wave0_names == {"source_model"}
        assert wave1_names == {"final_model"}

    def test_source_dependencies_ignored_in_waves(
        self, tmp_path: Path, manifest_with_sources: dict[str, Any]
    ):
        """Source dependencies should not affect wave computation."""
        manifest_path = write_manifest(tmp_path, manifest_with_sources)
        parser = ManifestParser(manifest_path)

        waves = parser.compute_execution_waves()

        # Only executable model should be in wave 0
        assert len(waves) == 1
        assert waves[0].nodes[0].name == "staging_model"


# =============================================================================
# Edge Cases and Integration Tests
# =============================================================================


class TestManifestParserEdgeCases:
    """Edge cases and integration tests for ManifestParser."""

    def test_nested_ephemeral_chain(self, tmp_path: Path):
        """Should resolve through multiple ephemeral models."""
        manifest_data = {
            "nodes": {
                "model.test_project.base": {
                    "name": "base",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                    "relation_name": '"db"."schema"."base"',
                    "original_file_path": "models/base.sql",
                },
                "model.test_project.eph1": {
                    "name": "eph1",
                    "resource_type": "model",
                    "depends_on": {"nodes": ["model.test_project.base"]},
                    "config": {"materialized": "ephemeral"},
                    "relation_name": None,
                    "original_file_path": "models/eph1.sql",
                },
                "model.test_project.eph2": {
                    "name": "eph2",
                    "resource_type": "model",
                    "depends_on": {"nodes": ["model.test_project.eph1"]},
                    "config": {"materialized": "ephemeral"},
                    "relation_name": None,
                    "original_file_path": "models/eph2.sql",
                },
                "model.test_project.final": {
                    "name": "final",
                    "resource_type": "model",
                    "depends_on": {"nodes": ["model.test_project.eph2"]},
                    "config": {"materialized": "table"},
                    "relation_name": '"db"."schema"."final"',
                    "original_file_path": "models/final.sql",
                },
            },
            "sources": {},
        }
        manifest_path = write_manifest(tmp_path, manifest_data)
        parser = ManifestParser(manifest_path)

        nodes = parser.get_executable_nodes()
        final_node = nodes["model.test_project.final"]

        # Should resolve all the way through to base
        assert final_node.depends_on == ("model.test_project.base",)

    def test_multiple_dependency_paths(self, tmp_path: Path):
        """Should handle nodes with multiple dependency paths to same node."""
        manifest_data = {
            "nodes": {
                "model.test_project.base": {
                    "name": "base",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                    "relation_name": '"db"."schema"."base"',
                    "original_file_path": "models/base.sql",
                },
                "model.test_project.eph_a": {
                    "name": "eph_a",
                    "resource_type": "model",
                    "depends_on": {"nodes": ["model.test_project.base"]},
                    "config": {"materialized": "ephemeral"},
                    "relation_name": None,
                    "original_file_path": "models/eph_a.sql",
                },
                "model.test_project.eph_b": {
                    "name": "eph_b",
                    "resource_type": "model",
                    "depends_on": {"nodes": ["model.test_project.base"]},
                    "config": {"materialized": "ephemeral"},
                    "relation_name": None,
                    "original_file_path": "models/eph_b.sql",
                },
                "model.test_project.final": {
                    "name": "final",
                    "resource_type": "model",
                    "depends_on": {
                        "nodes": [
                            "model.test_project.eph_a",
                            "model.test_project.eph_b",
                        ]
                    },
                    "config": {"materialized": "table"},
                    "relation_name": '"db"."schema"."final"',
                    "original_file_path": "models/final.sql",
                },
            },
            "sources": {},
        }
        manifest_path = write_manifest(tmp_path, manifest_data)
        parser = ManifestParser(manifest_path)

        nodes = parser.get_executable_nodes()
        final_node = nodes["model.test_project.final"]

        # Should only include base once (deduplication through visited set)
        assert final_node.depends_on == ("model.test_project.base",)

    def test_source_without_relation_name(self, tmp_path: Path):
        """Sources without relation_name should be skipped in dependency resolution."""
        manifest_data = {
            "nodes": {
                "model.test_project.model": {
                    "name": "model",
                    "resource_type": "model",
                    "depends_on": {"nodes": ["source.test_project.raw.users"]},
                    "config": {"materialized": "table"},
                    "relation_name": '"db"."schema"."model"',
                    "original_file_path": "models/model.sql",
                },
            },
            "sources": {
                "source.test_project.raw.users": {
                    "name": "users",
                    "resource_type": "source",
                    "relation_name": None,  # No relation_name
                    "original_file_path": "models/sources.yml",
                    "config": {},
                },
            },
        }
        manifest_path = write_manifest(tmp_path, manifest_data)
        parser = ManifestParser(manifest_path)

        nodes = parser.get_executable_nodes()
        model_node = nodes["model.test_project.model"]

        # Source without relation_name should be skipped
        assert model_node.depends_on == ()

    def test_unknown_resource_type(self, tmp_path: Path):
        """Should handle unknown resource types gracefully."""
        manifest_data = {
            "nodes": {
                "unknown.test_project.something": {
                    "name": "something",
                    "resource_type": "unknown_type",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                    "relation_name": '"db"."schema"."something"',
                    "original_file_path": "models/something.sql",
                },
            },
            "sources": {},
        }
        manifest_path = write_manifest(tmp_path, manifest_data)
        parser = ManifestParser(manifest_path)

        nodes = parser.get_executable_nodes()
        # Should fall back to Model type
        assert len(nodes) == 1

    def test_caching_of_executable_nodes(
        self, tmp_path: Path, minimal_manifest_data: dict[str, Any]
    ):
        """get_executable_nodes should cache results."""
        manifest_path = write_manifest(tmp_path, minimal_manifest_data)
        parser = ManifestParser(manifest_path)

        nodes1 = parser.get_executable_nodes()
        nodes2 = parser.get_executable_nodes()

        assert nodes1 is nodes2  # Same object (cached)


# =============================================================================
# Filter Nodes Tests
# =============================================================================


class TestFilterNodes:
    """Tests for ManifestParser.filter_nodes()."""

    def test_filter_none_returns_all(
        self, tmp_path: Path, diamond_dependency_manifest: dict[str, Any]
    ):
        """filter_nodes(None) returns all executable nodes."""
        manifest_path = write_manifest(tmp_path, diamond_dependency_manifest)
        parser = ManifestParser(manifest_path)

        filtered = parser.filter_nodes(selected_node_ids=None)
        assert filtered == parser.get_executable_nodes()

    def test_filter_subset(
        self, tmp_path: Path, diamond_dependency_manifest: dict[str, Any]
    ):
        """filter_nodes with a subset of IDs returns only those nodes."""
        manifest_path = write_manifest(tmp_path, diamond_dependency_manifest)
        parser = ManifestParser(manifest_path)

        subset = {"model.test_project.root", "model.test_project.left"}
        filtered = parser.filter_nodes(selected_node_ids=subset)

        assert set(filtered.keys()) == subset
        assert "model.test_project.right" not in filtered
        assert "model.test_project.leaf" not in filtered

    def test_filter_empty_set(
        self, tmp_path: Path, diamond_dependency_manifest: dict[str, Any]
    ):
        """filter_nodes with empty set returns empty dict."""
        manifest_path = write_manifest(tmp_path, diamond_dependency_manifest)
        parser = ManifestParser(manifest_path)

        filtered = parser.filter_nodes(selected_node_ids=set())
        assert filtered == {}

    def test_filter_nonexistent_ids_ignored(
        self, tmp_path: Path, minimal_manifest_data: dict[str, Any]
    ):
        """IDs not in manifest are silently ignored."""
        manifest_path = write_manifest(tmp_path, minimal_manifest_data)
        parser = ManifestParser(manifest_path)

        filtered = parser.filter_nodes(
            selected_node_ids={"model.test_project.my_model", "model.fake.not_real"}
        )
        assert set(filtered.keys()) == {"model.test_project.my_model"}

    def test_filter_preserves_resolved_dependencies(
        self, tmp_path: Path, manifest_with_ephemeral: dict[str, Any]
    ):
        """Filtered nodes retain their resolved (through-ephemeral) deps."""
        manifest_path = write_manifest(tmp_path, manifest_with_ephemeral)
        parser = ManifestParser(manifest_path)

        # final_model depends on source_model (through ephemeral)
        filtered = parser.filter_nodes(
            selected_node_ids={
                "model.test_project.source_model",
                "model.test_project.final_model",
            }
        )

        final = filtered["model.test_project.final_model"]
        # Resolved dependency through ephemeral should be preserved
        assert "model.test_project.source_model" in final.depends_on

    def test_filter_with_diamond_pattern(
        self, tmp_path: Path, diamond_dependency_manifest: dict[str, Any]
    ):
        """Filter a subset of the diamond graph."""
        manifest_path = write_manifest(tmp_path, diamond_dependency_manifest)
        parser = ManifestParser(manifest_path)

        # Select only right and leaf — root and left are excluded
        filtered = parser.filter_nodes(
            selected_node_ids={
                "model.test_project.right",
                "model.test_project.leaf",
            }
        )

        assert set(filtered.keys()) == {
            "model.test_project.right",
            "model.test_project.leaf",
        }
        # leaf still has its original deps (root, left, right) in depends_on
        # but only right is in the filtered set
        leaf = filtered["model.test_project.leaf"]
        assert "model.test_project.left" in leaf.depends_on
        assert "model.test_project.right" in leaf.depends_on


# =============================================================================
# Filtered Execution Waves Tests
# =============================================================================


class TestComputeExecutionWavesFiltered:
    """Tests for ManifestParser.compute_execution_waves() with filtered nodes."""

    def test_waves_from_filtered_nodes(
        self, tmp_path: Path, diamond_dependency_manifest: dict[str, Any]
    ):
        """Compute waves from a filtered subset."""
        manifest_path = write_manifest(tmp_path, diamond_dependency_manifest)
        parser = ManifestParser(manifest_path)

        # Only root and left
        filtered = parser.filter_nodes(
            selected_node_ids={
                "model.test_project.root",
                "model.test_project.left",
            }
        )
        waves = parser.compute_execution_waves(nodes=filtered)

        assert len(waves) == 2
        assert {n.name for n in waves[0].nodes} == {"root"}
        assert {n.name for n in waves[1].nodes} == {"left"}

    def test_waves_filtered_recomputes_dependencies(
        self, tmp_path: Path, diamond_dependency_manifest: dict[str, Any]
    ):
        """Wave computation only considers in-set dependencies."""
        manifest_path = write_manifest(tmp_path, diamond_dependency_manifest)
        parser = ManifestParser(manifest_path)

        # Select leaf and right, but NOT root (which right depends on).
        # Since root is not in the set, right has 0 in-set deps → wave 0.
        # leaf depends on left (not in set) and right (in set) → wave 1.
        filtered = parser.filter_nodes(
            selected_node_ids={
                "model.test_project.right",
                "model.test_project.leaf",
            }
        )
        waves = parser.compute_execution_waves(nodes=filtered)

        assert len(waves) == 2
        wave0_names = {n.name for n in waves[0].nodes}
        wave1_names = {n.name for n in waves[1].nodes}
        assert wave0_names == {"right"}
        assert wave1_names == {"leaf"}

    def test_waves_with_none_uses_all_nodes(
        self, tmp_path: Path, diamond_dependency_manifest: dict[str, Any]
    ):
        """Passing nodes=None uses get_executable_nodes."""
        manifest_path = write_manifest(tmp_path, diamond_dependency_manifest)
        parser = ManifestParser(manifest_path)

        waves_default = parser.compute_execution_waves()
        waves_none = parser.compute_execution_waves(nodes=None)

        assert len(waves_default) == len(waves_none)
        for w1, w2 in zip(waves_default, waves_none):
            assert {n.unique_id for n in w1.nodes} == {n.unique_id for n in w2.nodes}


# =============================================================================
# resolve_selection Tests
# =============================================================================


class TestResolveSelection:
    """Tests for the resolve_selection() standalone function."""

    @patch("prefect_dbt.core._manifest.dbtRunner")
    def test_resolve_with_select(self, mock_runner_cls: MagicMock, tmp_path: Path):
        """Invokes dbt ls with --select flag."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.result = [
            json.dumps({"unique_id": "model.proj.stg_users"}),
            json.dumps({"unique_id": "model.proj.stg_orders"}),
        ]
        mock_runner_cls.return_value.invoke.return_value = mock_result

        result = resolve_selection(
            project_dir=tmp_path / "project",
            profiles_dir=tmp_path / "profiles",
            select="marts",
        )

        assert result == {"model.proj.stg_users", "model.proj.stg_orders"}

        args = mock_runner_cls.return_value.invoke.call_args[0][0]
        assert "--select" in args
        assert "marts" in args

    @patch("prefect_dbt.core._manifest.dbtRunner")
    def test_resolve_with_exclude(self, mock_runner_cls: MagicMock, tmp_path: Path):
        """Invokes dbt ls with --exclude flag."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.result = [
            json.dumps({"unique_id": "model.proj.stg_users"}),
        ]
        mock_runner_cls.return_value.invoke.return_value = mock_result

        result = resolve_selection(
            project_dir=tmp_path / "project",
            profiles_dir=tmp_path / "profiles",
            exclude="stg_legacy_*",
        )

        assert result == {"model.proj.stg_users"}

        args = mock_runner_cls.return_value.invoke.call_args[0][0]
        assert "--exclude" in args
        assert "stg_legacy_*" in args
        assert "--select" not in args

    @patch("prefect_dbt.core._manifest.dbtRunner")
    def test_resolve_with_both(self, mock_runner_cls: MagicMock, tmp_path: Path):
        """Invokes dbt ls with both --select and --exclude."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.result = [
            json.dumps({"unique_id": "model.proj.dim_users"}),
        ]
        mock_runner_cls.return_value.invoke.return_value = mock_result

        result = resolve_selection(
            project_dir=tmp_path / "project",
            profiles_dir=tmp_path / "profiles",
            select="marts",
            exclude="dim_legacy_*",
        )

        assert result == {"model.proj.dim_users"}

        args = mock_runner_cls.return_value.invoke.call_args[0][0]
        assert "--select" in args
        assert "--exclude" in args

    @patch("prefect_dbt.core._manifest.dbtRunner")
    def test_resolve_no_selectors_returns_all(
        self, mock_runner_cls: MagicMock, tmp_path: Path
    ):
        """No select/exclude still invokes dbt ls for all nodes."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.result = [
            json.dumps({"unique_id": "model.proj.a"}),
            json.dumps({"unique_id": "model.proj.b"}),
            json.dumps({"unique_id": "seed.proj.c"}),
        ]
        mock_runner_cls.return_value.invoke.return_value = mock_result

        result = resolve_selection(
            project_dir=tmp_path / "project",
            profiles_dir=tmp_path / "profiles",
        )

        assert result == {"model.proj.a", "model.proj.b", "seed.proj.c"}

        args = mock_runner_cls.return_value.invoke.call_args[0][0]
        assert "--select" not in args
        assert "--exclude" not in args

    @patch("prefect_dbt.core._manifest.dbtRunner")
    def test_resolve_failure_raises_error(
        self, mock_runner_cls: MagicMock, tmp_path: Path
    ):
        """Failed dbt ls raises DbtLsError."""
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.exception = RuntimeError("compilation error")
        mock_runner_cls.return_value.invoke.return_value = mock_result

        with pytest.raises(DbtLsError, match="dbt ls failed"):
            resolve_selection(
                project_dir=tmp_path / "project",
                profiles_dir=tmp_path / "profiles",
                select="nonexistent_model",
            )

    @patch("prefect_dbt.core._manifest.dbtRunner")
    def test_resolve_passes_project_and_profiles_dir(
        self, mock_runner_cls: MagicMock, tmp_path: Path
    ):
        """Verifies correct CLI args are passed to dbtRunner."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.result = []
        mock_runner_cls.return_value.invoke.return_value = mock_result

        project = tmp_path / "my_project"
        profiles = tmp_path / "my_profiles"

        resolve_selection(project_dir=project, profiles_dir=profiles)

        args = mock_runner_cls.return_value.invoke.call_args[0][0]
        assert "ls" in args
        assert "--resource-type" in args
        assert "all" in args
        assert "--project-dir" in args
        assert str(project) in args
        assert "--profiles-dir" in args
        assert str(profiles) in args

    @patch("prefect_dbt.core._manifest.dbtRunner")
    def test_resolve_with_target_path(self, mock_runner_cls: MagicMock, tmp_path: Path):
        """target_path is passed when provided."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.result = [json.dumps({"unique_id": "model.proj.a"})]
        mock_runner_cls.return_value.invoke.return_value = mock_result

        target = tmp_path / "custom_target"

        resolve_selection(
            project_dir=tmp_path / "project",
            profiles_dir=tmp_path / "profiles",
            target_path=target,
        )

        args = mock_runner_cls.return_value.invoke.call_args[0][0]
        assert "--target-path" in args
        assert str(target) in args
