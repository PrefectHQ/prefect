"""Tests for Phase 9: Artifacts and Asset Tracking."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from conftest import (
    _make_mock_executor_per_node,
    _make_mock_settings,
    _make_node,
    write_manifest,
)
from dbt.artifacts.resources.types import NodeType
from prefect_dbt.core._artifacts import (
    ASSET_NODE_TYPES,
    create_asset_for_node,
    create_run_results_dict,
    create_summary_markdown,
    get_compiled_code_for_node,
    get_upstream_assets_for_node,
    write_run_results_json,
)
from prefect_dbt.core._manifest import DbtNode
from prefect_dbt.core._orchestrator import (
    ExecutionMode,
    PrefectDbtOrchestrator,
)

from prefect import flow

# ============================================================
# Fixtures
# ============================================================


SAMPLE_RESULTS: dict[str, Any] = {
    "model.test.stg_users": {
        "status": "success",
        "timing": {
            "started_at": "2024-01-15T10:30:00+00:00",
            "completed_at": "2024-01-15T10:30:05+00:00",
            "duration_seconds": 5.0,
        },
        "invocation": {"command": "run", "args": ["model.test.stg_users"]},
    },
    "model.test.stg_orders": {
        "status": "error",
        "timing": {
            "started_at": "2024-01-15T10:30:00+00:00",
            "completed_at": "2024-01-15T10:30:03+00:00",
            "duration_seconds": 3.0,
        },
        "invocation": {"command": "run", "args": ["model.test.stg_orders"]},
        "error": {
            "message": 'Database error: relation "raw.orders" does not exist',
            "type": "DatabaseError",
        },
    },
    "model.test.order_summary": {
        "status": "skipped",
        "reason": "upstream failure",
        "failed_upstream": ["model.test.stg_orders"],
    },
}


MANIFEST_WITH_ASSETS = {
    "metadata": {
        "adapter_type": "postgres",
        "project_name": "test_project",
    },
    "nodes": {
        "model.test.root": {
            "name": "root",
            "resource_type": "model",
            "depends_on": {"nodes": []},
            "config": {"materialized": "table"},
            "relation_name": '"main"."public"."root"',
            "description": "Root model",
            "original_file_path": "models/root.sql",
        },
        "model.test.child": {
            "name": "child",
            "resource_type": "model",
            "depends_on": {"nodes": ["model.test.root"]},
            "config": {"materialized": "table"},
            "relation_name": '"main"."public"."child"',
            "description": "Child model",
            "original_file_path": "models/child.sql",
        },
    },
    "sources": {
        "source.test.raw.users": {
            "name": "users",
            "resource_type": "source",
            "fqn": ["test", "raw", "users"],
            "relation_name": '"main"."raw"."users"',
            "config": {},
            "description": "Raw users source",
        },
    },
}


# ============================================================
# create_summary_markdown
# ============================================================


class TestCreateSummaryMarkdown:
    def test_basic_summary(self):
        md = create_summary_markdown(SAMPLE_RESULTS)

        assert "## dbt build Task Summary" in md
        assert "| 1 | 1 | 1 | 3 |" in md

    def test_error_section(self):
        md = create_summary_markdown(SAMPLE_RESULTS)

        assert "### Unsuccessful Nodes" in md
        assert "**stg_orders**" in md
        assert "Database error" in md

    def test_skipped_section(self):
        md = create_summary_markdown(SAMPLE_RESULTS)

        assert "### Skipped Nodes" in md
        assert "order_summary (upstream failure)" in md

    def test_success_section(self):
        md = create_summary_markdown(SAMPLE_RESULTS)

        assert "### Successful Nodes" in md
        assert "stg_users" in md

    def test_all_success(self):
        results = {
            "model.test.a": {"status": "success"},
            "model.test.b": {"status": "success"},
        }
        md = create_summary_markdown(results)

        assert "| 2 | 0 | 0 | 2 |" in md
        assert "### Unsuccessful Nodes" not in md
        assert "### Skipped Nodes" not in md

    def test_empty_results(self):
        md = create_summary_markdown({})

        assert "| 0 | 0 | 0 | 0 |" in md

    def test_cached_status_counted(self):
        results = {
            "model.test.a": {"status": "cached"},
            "model.test.b": {"status": "success"},
        }
        md = create_summary_markdown(results)

        # Cached nodes show in successful list
        assert "* a" in md
        assert "* b" in md
        # Cached nodes count toward the Successes column (1 cached + 1 success = 2)
        assert "| 2 | 0 | 0 | 2 |" in md


# ============================================================
# create_run_results_dict / write_run_results_json
# ============================================================


class TestRunResults:
    def test_basic_structure(self):
        data = create_run_results_dict(SAMPLE_RESULTS, elapsed_time=8.0)

        assert "metadata" in data
        assert "results" in data
        assert data["elapsed_time"] == 8.0
        assert len(data["results"]) == 3

    def test_metadata_has_dbt_schema_version(self):
        data = create_run_results_dict(SAMPLE_RESULTS, elapsed_time=1.0)

        metadata = data["metadata"]
        assert metadata["dbt_schema_version"] == (
            "https://schemas.getdbt.com/dbt/run-results/v6.json"
        )
        assert "dbt_version" in metadata
        assert "generated_at" in metadata

    def test_result_has_mandatory_fields(self):
        data = create_run_results_dict(SAMPLE_RESULTS, elapsed_time=1.0)

        for result in data["results"]:
            assert "unique_id" in result
            assert "status" in result
            assert "timing" in result
            assert isinstance(result["timing"], list)
            assert "thread_id" in result
            assert "execution_time" in result
            assert "adapter_response" in result
            assert isinstance(result["adapter_response"], dict)
            assert "message" in result
            assert "failures" in result
            assert "compiled" in result
            assert "compiled_code" in result
            assert "relation_name" in result
            assert "batch_results" in result

    def test_success_mapping(self):
        data = create_run_results_dict(SAMPLE_RESULTS, elapsed_time=1.0)
        by_id = {r["unique_id"]: r for r in data["results"]}

        assert by_id["model.test.stg_users"]["status"] == "success"
        assert by_id["model.test.stg_users"]["execution_time"] == 5.0

    def test_error_mapping(self):
        data = create_run_results_dict(SAMPLE_RESULTS, elapsed_time=1.0)
        by_id = {r["unique_id"]: r for r in data["results"]}

        assert by_id["model.test.stg_orders"]["status"] == "error"
        assert "Database error" in by_id["model.test.stg_orders"]["message"]

    def test_skipped_mapping(self):
        data = create_run_results_dict(SAMPLE_RESULTS, elapsed_time=1.0)
        by_id = {r["unique_id"]: r for r in data["results"]}

        assert by_id["model.test.order_summary"]["status"] == "skipped"

    def test_cached_maps_to_success(self):
        results = {"model.test.a": {"status": "cached"}}
        data = create_run_results_dict(results, elapsed_time=0.0)

        assert data["results"][0]["status"] == "success"

    def test_timing_included(self):
        data = create_run_results_dict(SAMPLE_RESULTS, elapsed_time=1.0)
        by_id = {r["unique_id"]: r for r in data["results"]}

        timing = by_id["model.test.stg_users"]["timing"]
        assert len(timing) == 1
        assert timing[0]["name"] == "execute"
        assert "2024-01-15T10:30:00" in timing[0]["started_at"]

    def test_timing_empty_list_when_no_data(self):
        results = {"model.test.a": {"status": "skipped"}}
        data = create_run_results_dict(results, elapsed_time=0.0)

        assert data["results"][0]["timing"] == []

    def test_write_to_disk(self, tmp_path):
        path = write_run_results_json(SAMPLE_RESULTS, 8.0, tmp_path)

        assert path.exists()
        assert path.name == "run_results.json"
        data = json.loads(path.read_text())
        assert len(data["results"]) == 3

    def test_write_creates_directory(self, tmp_path):
        target = tmp_path / "nested" / "target"
        path = write_run_results_json(SAMPLE_RESULTS, 1.0, target)

        assert path.exists()


# ============================================================
# Asset helpers
# ============================================================


class TestCreateAssetForNode:
    def test_basic_asset(self):
        node = _make_node(
            name="my_model",
            relation_name='"main"."public"."my_model"',
        )
        asset = create_asset_for_node(node, "postgres")

        assert "postgres://" in asset.key
        assert "my_model" in asset.key
        assert asset.properties.name == "my_model"

    def test_with_description(self):
        node = DbtNode(
            unique_id="model.test.m1",
            name="m1",
            resource_type=NodeType.Model,
            materialization="table",
            relation_name='"main"."public"."m1"',
            description="A useful model",
        )
        asset = create_asset_for_node(node, "postgres")

        assert asset.properties.description == "A useful model"

    def test_with_none_description_omits_field(self):
        node = DbtNode(
            unique_id="model.test.m1",
            name="m1",
            resource_type=NodeType.Model,
            materialization="table",
            relation_name='"main"."public"."m1"',
            description=None,
        )
        asset = create_asset_for_node(node, "postgres")

        assert asset.properties.description is None
        assert "description" not in asset.properties.model_dump(exclude_unset=True)

    def test_with_description_suffix(self):
        node = DbtNode(
            unique_id="model.test.m1",
            name="m1",
            resource_type=NodeType.Model,
            materialization="table",
            relation_name='"main"."public"."m1"',
            description="Base desc",
        )
        asset = create_asset_for_node(
            node, "postgres", description_suffix="\n### Compiled\n```sql\nSELECT 1\n```"
        )

        assert "Base desc" in asset.properties.description
        assert "SELECT 1" in asset.properties.description

    def test_with_owner(self):
        node = DbtNode(
            unique_id="model.test.m1",
            name="m1",
            resource_type=NodeType.Model,
            materialization="table",
            relation_name='"main"."public"."m1"',
            config={"meta": {"owner": "data-team"}},
        )
        asset = create_asset_for_node(node, "postgres")

        assert asset.properties.owners == ["data-team"]

    def test_description_truncated_when_combined_exceeds_limit(self):
        from prefect.assets.core import MAX_ASSET_DESCRIPTION_LENGTH

        base_desc = "A" * 200
        suffix = "B" * MAX_ASSET_DESCRIPTION_LENGTH  # Suffix that exceeds limit
        node = DbtNode(
            unique_id="model.test.m1",
            name="m1",
            resource_type=NodeType.Model,
            materialization="table",
            relation_name='"main"."public"."m1"',
            description=base_desc,
        )
        asset = create_asset_for_node(node, "postgres", description_suffix=suffix)

        assert asset.properties.description is not None
        assert len(asset.properties.description) <= MAX_ASSET_DESCRIPTION_LENGTH
        # Falls back to just the base description (truncated if needed)
        assert asset.properties.description == base_desc

    def test_long_base_description_truncated(self):
        from prefect.assets.core import MAX_ASSET_DESCRIPTION_LENGTH

        base_desc = "X" * (MAX_ASSET_DESCRIPTION_LENGTH + 500)
        node = DbtNode(
            unique_id="model.test.m1",
            name="m1",
            resource_type=NodeType.Model,
            materialization="table",
            relation_name='"main"."public"."m1"',
            description=base_desc,
        )
        asset = create_asset_for_node(node, "postgres")

        assert len(asset.properties.description) <= MAX_ASSET_DESCRIPTION_LENGTH

    def test_no_relation_name_raises(self):
        node = _make_node(name="ephemeral", materialization="ephemeral")

        with pytest.raises(ValueError, match="no relation_name"):
            create_asset_for_node(node, "postgres")


class TestGetUpstreamAssets:
    def test_finds_upstream_models(self):
        root = DbtNode(
            unique_id="model.test.root",
            name="root",
            resource_type=NodeType.Model,
            materialization="table",
            relation_name='"main"."public"."root"',
        )
        child = DbtNode(
            unique_id="model.test.child",
            name="child",
            resource_type=NodeType.Model,
            depends_on=("model.test.root",),
            materialization="table",
            relation_name='"main"."public"."child"',
        )
        all_nodes = {root.unique_id: root, child.unique_id: child}

        assets = get_upstream_assets_for_node(child, all_nodes, "postgres")

        assert len(assets) == 1
        assert "root" in assets[0].key

    def test_finds_upstream_sources(self):
        source = DbtNode(
            unique_id="source.test.raw.users",
            name="users",
            resource_type=NodeType.Source,
            relation_name='"main"."raw"."users"',
        )
        model = DbtNode(
            unique_id="model.test.stg_users",
            name="stg_users",
            resource_type=NodeType.Model,
            depends_on=("source.test.raw.users",),
            materialization="view",
            relation_name='"main"."public"."stg_users"',
        )
        all_nodes = {source.unique_id: source, model.unique_id: model}

        assets = get_upstream_assets_for_node(model, all_nodes, "postgres")

        assert len(assets) == 1
        assert "users" in assets[0].key

    def test_skips_nodes_without_relation_name(self):
        parent = DbtNode(
            unique_id="model.test.ephemeral",
            name="ephemeral",
            resource_type=NodeType.Model,
            materialization="ephemeral",
        )
        child = DbtNode(
            unique_id="model.test.child",
            name="child",
            resource_type=NodeType.Model,
            depends_on=("model.test.ephemeral",),
            materialization="table",
            relation_name='"main"."public"."child"',
        )
        all_nodes = {parent.unique_id: parent, child.unique_id: child}

        assets = get_upstream_assets_for_node(child, all_nodes, "postgres")

        assert len(assets) == 0

    def test_finds_sources_stripped_by_dependency_resolution(self):
        """After dependency resolution, source deps are stripped from
        depends_on.  get_upstream_assets_for_node should recover them
        by looking up the original node in all_nodes."""
        source = DbtNode(
            unique_id="source.test.raw.users",
            name="users",
            resource_type=NodeType.Source,
            relation_name='"main"."raw"."users"',
        )
        # Original node (before resolution) depends on the source.
        original_model = DbtNode(
            unique_id="model.test.stg_users",
            name="stg_users",
            resource_type=NodeType.Model,
            depends_on=("source.test.raw.users",),
            materialization="view",
            relation_name='"main"."public"."stg_users"',
        )
        # Resolved node (from get_executable_nodes) has source stripped.
        resolved_model = DbtNode(
            unique_id="model.test.stg_users",
            name="stg_users",
            resource_type=NodeType.Model,
            depends_on=(),  # Source stripped during resolution
            materialization="view",
            relation_name='"main"."public"."stg_users"',
        )
        all_nodes = {
            source.unique_id: source,
            original_model.unique_id: original_model,
        }

        assets = get_upstream_assets_for_node(resolved_model, all_nodes, "postgres")

        assert len(assets) == 1
        assert "users" in assets[0].key

    def test_traverses_ephemeral_to_find_source(self):
        """Model → ephemeral → source: the ephemeral should be walked
        through so the source asset edge is emitted."""
        source = DbtNode(
            unique_id="source.test.raw.events",
            name="events",
            resource_type=NodeType.Source,
            relation_name='"main"."raw"."events"',
        )
        ephemeral = DbtNode(
            unique_id="model.test.stg_events_eph",
            name="stg_events_eph",
            resource_type=NodeType.Model,
            depends_on=("source.test.raw.events",),
            materialization="ephemeral",
        )
        # Original node depends on the ephemeral.
        original_model = DbtNode(
            unique_id="model.test.fct_events",
            name="fct_events",
            resource_type=NodeType.Model,
            depends_on=("model.test.stg_events_eph",),
            materialization="table",
            relation_name='"main"."public"."fct_events"',
        )
        # Resolved node (ephemeral resolved away, source also stripped).
        resolved_model = DbtNode(
            unique_id="model.test.fct_events",
            name="fct_events",
            resource_type=NodeType.Model,
            depends_on=(),
            materialization="table",
            relation_name='"main"."public"."fct_events"',
        )
        all_nodes = {
            source.unique_id: source,
            ephemeral.unique_id: ephemeral,
            original_model.unique_id: original_model,
        }

        assets = get_upstream_assets_for_node(resolved_model, all_nodes, "postgres")

        assert len(assets) == 1
        assert "events" in assets[0].key

    def test_empty_when_no_deps(self):
        node = DbtNode(
            unique_id="model.test.root",
            name="root",
            resource_type=NodeType.Model,
            materialization="table",
            relation_name='"main"."public"."root"',
        )

        assets = get_upstream_assets_for_node(node, {node.unique_id: node}, "postgres")

        assert assets == []


class TestGetCompiledCode:
    def test_from_node_field(self, tmp_path):
        node = DbtNode(
            unique_id="model.test.m1",
            name="m1",
            resource_type=NodeType.Model,
            materialization="table",
            compiled_code="SELECT 1 AS id",
        )

        result = get_compiled_code_for_node(node, tmp_path, Path("target"), "proj")

        assert "SELECT 1 AS id" in result
        assert "```sql" in result

    def test_from_disk(self, tmp_path):
        # Create compiled file on disk
        compiled_dir = tmp_path / "target" / "compiled" / "proj" / "models"
        compiled_dir.mkdir(parents=True)
        (compiled_dir / "m1.sql").write_text("SELECT 2 AS id")

        node = DbtNode(
            unique_id="model.test.m1",
            name="m1",
            resource_type=NodeType.Model,
            materialization="table",
            original_file_path="models/m1.sql",
        )

        result = get_compiled_code_for_node(node, tmp_path, Path("target"), "proj")

        assert "SELECT 2 AS id" in result

    def test_returns_empty_when_unavailable(self, tmp_path):
        node = DbtNode(
            unique_id="model.test.m1",
            name="m1",
            resource_type=NodeType.Model,
            materialization="table",
        )

        result = get_compiled_code_for_node(node, tmp_path, Path("target"), "proj")

        assert result == ""

    def test_prefers_node_field_over_disk(self, tmp_path):
        compiled_dir = tmp_path / "target" / "compiled" / "proj" / "models"
        compiled_dir.mkdir(parents=True)
        (compiled_dir / "m1.sql").write_text("SELECT disk")

        node = DbtNode(
            unique_id="model.test.m1",
            name="m1",
            resource_type=NodeType.Model,
            materialization="table",
            compiled_code="SELECT manifest",
            original_file_path="models/m1.sql",
        )

        result = get_compiled_code_for_node(node, tmp_path, Path("target"), "proj")

        assert "SELECT manifest" in result
        assert "disk" not in result


# ============================================================
# ManifestParser metadata properties
# ============================================================


class TestManifestParserMetadata:
    def test_adapter_type(self, tmp_path):
        from prefect_dbt.core._manifest import ManifestParser

        path = write_manifest(tmp_path, MANIFEST_WITH_ASSETS)
        parser = ManifestParser(path)

        assert parser.adapter_type == "postgres"

    def test_project_name(self, tmp_path):
        from prefect_dbt.core._manifest import ManifestParser

        path = write_manifest(tmp_path, MANIFEST_WITH_ASSETS)
        parser = ManifestParser(path)

        assert parser.project_name == "test_project"

    def test_missing_metadata(self, tmp_path):
        from prefect_dbt.core._manifest import ManifestParser

        path = write_manifest(tmp_path, {"nodes": {}, "sources": {}})
        parser = ManifestParser(path)

        assert parser.adapter_type is None
        assert parser.project_name is None


class TestDbtNodeNewFields:
    def test_description_parsed(self, tmp_path):
        from prefect_dbt.core._manifest import ManifestParser

        path = write_manifest(tmp_path, MANIFEST_WITH_ASSETS)
        parser = ManifestParser(path)
        nodes = parser.get_executable_nodes()

        assert nodes["model.test.root"].description == "Root model"
        assert nodes["model.test.child"].description == "Child model"

    def test_source_description_parsed(self, tmp_path):
        from prefect_dbt.core._manifest import ManifestParser

        path = write_manifest(tmp_path, MANIFEST_WITH_ASSETS)
        parser = ManifestParser(path)

        source = parser.all_nodes["source.test.raw.users"]
        assert source.description == "Raw users source"

    def test_compiled_code_parsed(self, tmp_path):
        from prefect_dbt.core._manifest import ManifestParser

        manifest = {
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                    "compiled_code": "SELECT 1",
                },
            },
            "sources": {},
        }
        path = write_manifest(tmp_path, manifest)
        parser = ManifestParser(path)
        nodes = parser.get_executable_nodes()

        assert nodes["model.test.m1"].compiled_code == "SELECT 1"

    def test_defaults_to_none(self):
        node = _make_node()

        assert node.description is None
        assert node.compiled_code is None


# ============================================================
# Orchestrator artifact integration
# ============================================================


class TestOrchestratorSummaryArtifact:
    """Test that run_build() creates a summary artifact when enabled."""

    def test_summary_artifact_created(self, tmp_path, caplog):
        manifest_path = write_manifest(
            tmp_path,
            {
                "nodes": {
                    "model.test.m1": {
                        "name": "m1",
                        "resource_type": "model",
                        "depends_on": {"nodes": []},
                        "config": {"materialized": "table"},
                    },
                },
                "sources": {},
            },
        )
        settings = _make_mock_settings(project_dir=tmp_path)
        executor = _make_mock_executor_per_node()

        with (
            patch("prefect_dbt.core._orchestrator.ManifestParser") as MockParser,
            patch(
                "prefect_dbt.core._orchestrator.create_markdown_artifact"
            ) as mock_create,
            patch("prefect.context.FlowRunContext.get", return_value=MagicMock()),
        ):
            parser_instance = MockParser.return_value
            parser_instance.filter_nodes.return_value = {
                "model.test.m1": _make_node("model.test.m1", "m1"),
            }
            parser_instance.all_nodes = parser_instance.filter_nodes.return_value
            parser_instance.adapter_type = "duckdb"
            parser_instance.project_name = "test"
            parser_instance.compute_execution_waves.return_value = [
                MagicMock(nodes=[_make_node("model.test.m1", "m1")]),
            ]
            parser_instance.get_macro_paths.return_value = {}

            orchestrator = PrefectDbtOrchestrator(
                settings=settings,
                executor=executor,
                manifest_path=manifest_path,
                create_summary_artifact=True,
            )
            with caplog.at_level("INFO"):
                orchestrator.run_build()

            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args
            assert "dbt build Task Summary" in call_kwargs.kwargs.get(
                "markdown", call_kwargs.args[0] if call_kwargs.args else ""
            )

        assert any("dbt-orchestrator-summary" in msg for msg in caplog.messages)

    def test_summary_artifact_skipped_without_flow_context(self, tmp_path):
        """When there is no active flow run context, the summary artifact
        should NOT be created even when create_summary_artifact=True."""
        manifest_path = write_manifest(
            tmp_path,
            {"nodes": {}, "sources": {}},
        )
        settings = _make_mock_settings(project_dir=tmp_path)
        executor = _make_mock_executor_per_node()

        with (
            patch("prefect_dbt.core._orchestrator.ManifestParser") as MockParser,
            patch(
                "prefect_dbt.core._orchestrator.create_markdown_artifact"
            ) as mock_create,
            patch("prefect.context.FlowRunContext.get", return_value=None),
        ):
            parser_instance = MockParser.return_value
            parser_instance.filter_nodes.return_value = {}
            parser_instance.all_nodes = {}
            parser_instance.adapter_type = None
            parser_instance.project_name = None
            parser_instance.compute_execution_waves.return_value = []

            orchestrator = PrefectDbtOrchestrator(
                settings=settings,
                executor=executor,
                manifest_path=manifest_path,
                create_summary_artifact=True,
            )
            orchestrator.run_build()

            mock_create.assert_not_called()

    def test_summary_artifact_disabled(self, tmp_path):
        manifest_path = write_manifest(
            tmp_path,
            {"nodes": {}, "sources": {}},
        )
        settings = _make_mock_settings(project_dir=tmp_path)
        executor = _make_mock_executor_per_node()

        with (
            patch("prefect_dbt.core._orchestrator.ManifestParser") as MockParser,
            patch(
                "prefect_dbt.core._orchestrator.create_markdown_artifact"
            ) as mock_create,
        ):
            parser_instance = MockParser.return_value
            parser_instance.filter_nodes.return_value = {}
            parser_instance.all_nodes = {}
            parser_instance.adapter_type = None
            parser_instance.project_name = None
            parser_instance.compute_execution_waves.return_value = []

            orchestrator = PrefectDbtOrchestrator(
                settings=settings,
                executor=executor,
                manifest_path=manifest_path,
                create_summary_artifact=False,
            )
            orchestrator.run_build()

            mock_create.assert_not_called()


class TestOrchestratorWriteRunResults:
    """Test that run_build() writes run_results.json when enabled."""

    def test_run_results_written(self, tmp_path, caplog):
        # Write manifest into target/ so _resolve_target_path returns tmp_path/target
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        manifest_path = write_manifest(
            target_dir,
            {
                "nodes": {
                    "model.test.m1": {
                        "name": "m1",
                        "resource_type": "model",
                        "depends_on": {"nodes": []},
                        "config": {"materialized": "table"},
                    },
                },
                "sources": {},
            },
        )
        settings = _make_mock_settings(project_dir=tmp_path)
        executor = _make_mock_executor_per_node()

        with patch("prefect_dbt.core._orchestrator.ManifestParser") as MockParser:
            parser_instance = MockParser.return_value
            parser_instance.filter_nodes.return_value = {
                "model.test.m1": _make_node("model.test.m1", "m1"),
            }
            parser_instance.all_nodes = parser_instance.filter_nodes.return_value
            parser_instance.adapter_type = "duckdb"
            parser_instance.project_name = "test"
            parser_instance.compute_execution_waves.return_value = [
                MagicMock(nodes=[_make_node("model.test.m1", "m1")]),
            ]
            parser_instance.get_macro_paths.return_value = {}

            orchestrator = PrefectDbtOrchestrator(
                settings=settings,
                executor=executor,
                manifest_path=manifest_path,
                write_run_results=True,
                create_summary_artifact=False,
            )
            with caplog.at_level("INFO"):
                orchestrator.run_build()

        run_results_path = tmp_path / "target" / "run_results.json"
        assert run_results_path.exists()
        data = json.loads(run_results_path.read_text())
        assert len(data["results"]) == 1
        assert data["results"][0]["unique_id"] == "model.test.m1"
        assert data["results"][0]["status"] == "success"
        assert any(
            "run_results.json" in msg and str(run_results_path) in msg
            for msg in caplog.messages
        )

    def test_run_results_not_written_by_default(self, tmp_path):
        manifest_path = write_manifest(
            tmp_path,
            {"nodes": {}, "sources": {}},
        )
        settings = _make_mock_settings(project_dir=tmp_path)
        executor = _make_mock_executor_per_node()

        with patch("prefect_dbt.core._orchestrator.ManifestParser") as MockParser:
            parser_instance = MockParser.return_value
            parser_instance.filter_nodes.return_value = {}
            parser_instance.all_nodes = {}
            parser_instance.adapter_type = None
            parser_instance.project_name = None
            parser_instance.compute_execution_waves.return_value = []

            orchestrator = PrefectDbtOrchestrator(
                settings=settings,
                executor=executor,
                manifest_path=manifest_path,
                create_summary_artifact=False,
            )
            orchestrator.run_build()

        assert not (tmp_path / "target" / "run_results.json").exists()


# ============================================================
# Orchestrator MaterializingTask integration (PER_NODE)
# ============================================================


class _ThreadDelegatingRunner:
    """Lightweight task runner stand-in for unit tests.

    Delegates `submit()` to `task.submit()` (Prefect's default
    thread-based execution) so that mock executors (which are
    not picklable) work without a real process pool.
    """

    def __init__(self, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def submit(self, task, parameters=None, wait_for=None):
        return task.submit(**(parameters or {}))


class TestOrchestratorAssetTracking:
    """Verify MaterializingTask is used for asset-eligible nodes in PER_NODE mode."""

    def test_materializing_task_created_for_asset_nodes(self, tmp_path):
        """When adapter_type is available and nodes have relation_name,
        _build_asset_task should return a MaterializingTask."""
        manifest_path = write_manifest(tmp_path, MANIFEST_WITH_ASSETS)
        settings = _make_mock_settings(project_dir=tmp_path)
        executor = _make_mock_executor_per_node()

        with (
            patch("prefect_dbt.core._orchestrator.ManifestParser") as MockParser,
            patch(
                "prefect_dbt.core._orchestrator.create_asset_for_node"
            ) as mock_create_asset,
            patch(
                "prefect_dbt.core._orchestrator.get_upstream_assets_for_node"
            ) as mock_get_upstream,
        ):
            from prefect.assets import Asset, AssetProperties

            mock_asset = Asset(
                key="postgres://main/public/root",
                properties=AssetProperties(name="root"),
            )
            mock_create_asset.return_value = mock_asset
            mock_get_upstream.return_value = []

            root_node = _make_node(
                "model.test.root",
                "root",
                materialization="table",
            )
            # We need to set relation_name but _make_node doesn't support it.
            # Create a proper DbtNode instead.
            root_node = DbtNode(
                unique_id="model.test.root",
                name="root",
                resource_type=NodeType.Model,
                materialization="table",
                relation_name='"main"."public"."root"',
                description="Root model",
                original_file_path="models/root.sql",
            )

            parser_instance = MockParser.return_value
            parser_instance.filter_nodes.return_value = {
                "model.test.root": root_node,
            }
            parser_instance.all_nodes = {
                "model.test.root": root_node,
            }
            parser_instance.adapter_type = "postgres"
            parser_instance.project_name = "test_project"
            parser_instance.compute_execution_waves.return_value = [
                MagicMock(nodes=[root_node]),
            ]
            parser_instance.get_macro_paths.return_value = {}

            @flow
            def test_flow():
                orchestrator = PrefectDbtOrchestrator(
                    settings=settings,
                    executor=executor,
                    manifest_path=manifest_path,
                    execution_mode=ExecutionMode.PER_NODE,
                    task_runner_type=_ThreadDelegatingRunner,
                    create_summary_artifact=False,
                )
                return orchestrator.run_build()

            results = test_flow()

            assert results["model.test.root"]["status"] == "success"
            mock_create_asset.assert_called_once()

    def test_no_asset_for_nodes_without_relation_name(self, tmp_path):
        """Nodes without relation_name should NOT get MaterializingTask."""
        manifest = {
            "metadata": {"adapter_type": "postgres", "project_name": "test"},
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                    # No relation_name!
                },
            },
            "sources": {},
        }
        manifest_path = write_manifest(tmp_path, manifest)
        settings = _make_mock_settings(project_dir=tmp_path)
        executor = _make_mock_executor_per_node()

        with (
            patch("prefect_dbt.core._orchestrator.ManifestParser") as MockParser,
            patch(
                "prefect_dbt.core._orchestrator.create_asset_for_node"
            ) as mock_create_asset,
        ):
            node = _make_node("model.test.m1", "m1")

            parser_instance = MockParser.return_value
            parser_instance.filter_nodes.return_value = {
                "model.test.m1": node,
            }
            parser_instance.all_nodes = {"model.test.m1": node}
            parser_instance.adapter_type = "postgres"
            parser_instance.project_name = "test"
            parser_instance.compute_execution_waves.return_value = [
                MagicMock(nodes=[node]),
            ]
            parser_instance.get_macro_paths.return_value = {}

            @flow
            def test_flow():
                orchestrator = PrefectDbtOrchestrator(
                    settings=settings,
                    executor=executor,
                    manifest_path=manifest_path,
                    execution_mode=ExecutionMode.PER_NODE,
                    task_runner_type=_ThreadDelegatingRunner,
                    create_summary_artifact=False,
                )
                return orchestrator.run_build()

            results = test_flow()

            assert results["model.test.m1"]["status"] == "success"
            # create_asset_for_node should NOT be called since no relation_name
            mock_create_asset.assert_not_called()

    def test_no_asset_without_adapter_type(self, tmp_path):
        """When adapter_type is None, no assets should be created."""
        manifest = {
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                    "relation_name": '"main"."public"."m1"',
                },
            },
            "sources": {},
        }
        manifest_path = write_manifest(tmp_path, manifest)
        settings = _make_mock_settings(project_dir=tmp_path)
        executor = _make_mock_executor_per_node()

        with (
            patch("prefect_dbt.core._orchestrator.ManifestParser") as MockParser,
            patch(
                "prefect_dbt.core._orchestrator.create_asset_for_node"
            ) as mock_create_asset,
        ):
            node = DbtNode(
                unique_id="model.test.m1",
                name="m1",
                resource_type=NodeType.Model,
                materialization="table",
                relation_name='"main"."public"."m1"',
            )

            parser_instance = MockParser.return_value
            parser_instance.filter_nodes.return_value = {"model.test.m1": node}
            parser_instance.all_nodes = {"model.test.m1": node}
            parser_instance.adapter_type = None  # No adapter type!
            parser_instance.project_name = None
            parser_instance.compute_execution_waves.return_value = [
                MagicMock(nodes=[node]),
            ]
            parser_instance.get_macro_paths.return_value = {}

            @flow
            def test_flow():
                orchestrator = PrefectDbtOrchestrator(
                    settings=settings,
                    executor=executor,
                    manifest_path=manifest_path,
                    execution_mode=ExecutionMode.PER_NODE,
                    task_runner_type=_ThreadDelegatingRunner,
                    create_summary_artifact=False,
                )
                return orchestrator.run_build()

            results = test_flow()

            assert results["model.test.m1"]["status"] == "success"
            mock_create_asset.assert_not_called()


class TestOrchestratorDisableAssets:
    """Verify disable_assets flag suppresses asset creation."""

    def test_disable_assets_skips_materializing_task(self, tmp_path):
        """When disable_assets=True, create_asset_for_node should NOT be called
        even for nodes that would normally produce assets."""
        manifest_path = write_manifest(tmp_path, MANIFEST_WITH_ASSETS)
        settings = _make_mock_settings(project_dir=tmp_path)
        executor = _make_mock_executor_per_node()

        with (
            patch("prefect_dbt.core._orchestrator.ManifestParser") as MockParser,
            patch(
                "prefect_dbt.core._orchestrator.create_asset_for_node"
            ) as mock_create_asset,
        ):
            root_node = DbtNode(
                unique_id="model.test.root",
                name="root",
                resource_type=NodeType.Model,
                materialization="table",
                relation_name='"main"."public"."root"',
                description="Root model",
                original_file_path="models/root.sql",
            )

            parser_instance = MockParser.return_value
            parser_instance.filter_nodes.return_value = {
                "model.test.root": root_node,
            }
            parser_instance.all_nodes = {"model.test.root": root_node}
            parser_instance.adapter_type = "postgres"
            parser_instance.project_name = "test_project"
            parser_instance.compute_execution_waves.return_value = [
                MagicMock(nodes=[root_node]),
            ]
            parser_instance.get_macro_paths.return_value = {}

            @flow
            def test_flow():
                orchestrator = PrefectDbtOrchestrator(
                    settings=settings,
                    executor=executor,
                    manifest_path=manifest_path,
                    execution_mode=ExecutionMode.PER_NODE,
                    task_runner_type=_ThreadDelegatingRunner,
                    create_summary_artifact=False,
                    disable_assets=True,
                )
                return orchestrator.run_build()

            results = test_flow()

            assert results["model.test.root"]["status"] == "success"
            mock_create_asset.assert_not_called()

    def test_disable_assets_defaults_false(self, tmp_path):
        """When disable_assets is not set, assets should be created as usual."""
        manifest_path = write_manifest(tmp_path, MANIFEST_WITH_ASSETS)
        settings = _make_mock_settings(project_dir=tmp_path)
        executor = _make_mock_executor_per_node()

        with (
            patch("prefect_dbt.core._orchestrator.ManifestParser") as MockParser,
            patch(
                "prefect_dbt.core._orchestrator.create_asset_for_node"
            ) as mock_create_asset,
            patch(
                "prefect_dbt.core._orchestrator.get_upstream_assets_for_node"
            ) as mock_get_upstream,
        ):
            from prefect.assets import Asset, AssetProperties

            mock_asset = Asset(
                key="postgres://main/public/root",
                properties=AssetProperties(name="root"),
            )
            mock_create_asset.return_value = mock_asset
            mock_get_upstream.return_value = []

            root_node = DbtNode(
                unique_id="model.test.root",
                name="root",
                resource_type=NodeType.Model,
                materialization="table",
                relation_name='"main"."public"."root"',
                description="Root model",
                original_file_path="models/root.sql",
            )

            parser_instance = MockParser.return_value
            parser_instance.filter_nodes.return_value = {
                "model.test.root": root_node,
            }
            parser_instance.all_nodes = {"model.test.root": root_node}
            parser_instance.adapter_type = "postgres"
            parser_instance.project_name = "test_project"
            parser_instance.compute_execution_waves.return_value = [
                MagicMock(nodes=[root_node]),
            ]
            parser_instance.get_macro_paths.return_value = {}

            @flow
            def test_flow():
                orchestrator = PrefectDbtOrchestrator(
                    settings=settings,
                    executor=executor,
                    manifest_path=manifest_path,
                    execution_mode=ExecutionMode.PER_NODE,
                    task_runner_type=_ThreadDelegatingRunner,
                    create_summary_artifact=False,
                )
                return orchestrator.run_build()

            results = test_flow()

            assert results["model.test.root"]["status"] == "success"
            mock_create_asset.assert_called_once()


class TestOrchestratorCompiledCode:
    """Test include_compiled_code option."""

    def test_compiled_code_included_in_asset(self, tmp_path):
        """When include_compiled_code=True, compiled SQL should be in asset description."""
        manifest_path = write_manifest(tmp_path, MANIFEST_WITH_ASSETS)
        settings = _make_mock_settings(project_dir=tmp_path)
        executor = _make_mock_executor_per_node()

        with (
            patch("prefect_dbt.core._orchestrator.ManifestParser") as MockParser,
            patch(
                "prefect_dbt.core._orchestrator.get_compiled_code_for_node",
                return_value="\n### Compiled code\n```sql\nSELECT 1\n```",
            ) as mock_compiled,
            patch(
                "prefect_dbt.core._orchestrator.get_upstream_assets_for_node",
                return_value=[],
            ),
        ):
            root_node = DbtNode(
                unique_id="model.test.root",
                name="root",
                resource_type=NodeType.Model,
                materialization="table",
                relation_name='"main"."public"."root"',
                description="Root model",
                original_file_path="models/root.sql",
            )

            parser_instance = MockParser.return_value
            parser_instance.filter_nodes.return_value = {
                "model.test.root": root_node,
            }
            parser_instance.all_nodes = {"model.test.root": root_node}
            parser_instance.adapter_type = "postgres"
            parser_instance.project_name = "test_project"
            parser_instance.compute_execution_waves.return_value = [
                MagicMock(nodes=[root_node]),
            ]
            parser_instance.get_macro_paths.return_value = {}

            @flow
            def test_flow():
                orchestrator = PrefectDbtOrchestrator(
                    settings=settings,
                    executor=executor,
                    manifest_path=manifest_path,
                    execution_mode=ExecutionMode.PER_NODE,
                    task_runner_type=_ThreadDelegatingRunner,
                    include_compiled_code=True,
                    create_summary_artifact=False,
                )
                return orchestrator.run_build()

            results = test_flow()

            assert results["model.test.root"]["status"] == "success"
            mock_compiled.assert_called_once()


# ============================================================
# ASSET_NODE_TYPES constant
# ============================================================


class TestAssetNodeTypes:
    def test_model_seed_snapshot_included(self):
        assert NodeType.Model in ASSET_NODE_TYPES
        assert NodeType.Seed in ASSET_NODE_TYPES
        assert NodeType.Snapshot in ASSET_NODE_TYPES

    def test_test_not_included(self):
        assert NodeType.Test not in ASSET_NODE_TYPES
        assert NodeType.Source not in ASSET_NODE_TYPES
