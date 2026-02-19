"""Shared helpers and fixtures for orchestrator tests."""

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from dbt.artifacts.resources.types import NodeType
from prefect_dbt.core._executor import DbtExecutor, ExecutionResult
from prefect_dbt.core._manifest import DbtNode


def _make_node(
    unique_id: str = "model.test.my_model",
    name: str = "my_model",
    resource_type: NodeType = NodeType.Model,
    depends_on: tuple[str, ...] = (),
    depends_on_macros: tuple[str, ...] = (),
    materialization: str = "table",
    relation_name: str | None = None,
    description: str | None = None,
    compiled_code: str | None = None,
    config: dict | None = None,
    original_file_path: str | None = None,
) -> DbtNode:
    return DbtNode(
        unique_id=unique_id,
        name=name,
        resource_type=resource_type,
        depends_on=depends_on,
        depends_on_macros=depends_on_macros,
        materialization=materialization,
        relation_name=relation_name,
        description=description,
        compiled_code=compiled_code,
        config=config or {},
        original_file_path=original_file_path,
    )


def _make_mock_executor(
    success: bool = True,
    artifacts: dict[str, Any] | None = None,
    error: Exception | None = None,
    log_messages: dict[str, list[tuple[str, str]]] | None = None,
) -> MagicMock:
    """Create a mock DbtExecutor that returns the given result for execute_wave."""
    executor = MagicMock(spec=DbtExecutor)

    def _execute_wave(nodes, full_refresh=False, indirect_selection=None):
        return ExecutionResult(
            success=success,
            node_ids=[n.unique_id for n in nodes],
            error=error if not success else None,
            artifacts=artifacts,
            log_messages=log_messages,
        )

    executor.execute_wave = MagicMock(side_effect=_execute_wave)
    return executor


def _make_mock_settings(**overrides: object) -> MagicMock:
    """Create a mock PrefectDbtSettings."""
    settings = MagicMock()
    settings.project_dir = overrides.get("project_dir", Path("/proj"))
    settings.profiles_dir = overrides.get("profiles_dir", Path("/profiles"))
    settings.target_path = overrides.get("target_path", Path("target"))
    # model_copy() is called in __init__ to avoid mutating the caller's object
    settings.model_copy.return_value = settings

    # resolve_profiles_yml() is a context manager that yields a resolved
    # temp directory path string (see PrefectDbtSettings.resolve_profiles_yml).
    resolved_dir = str(overrides.get("resolved_profiles_dir", "/resolved/profiles"))

    @contextmanager
    def _resolve():
        yield resolved_dir

    settings.resolve_profiles_yml = _resolve
    return settings


def _make_mock_executor_per_node(
    success: bool = True,
    artifacts: dict[str, Any] | None = None,
    error: Exception | None = None,
    fail_nodes: set[str] | None = None,
    log_messages: dict[str, list[tuple[str, str]]] | None = None,
) -> MagicMock:
    """Create a mock DbtExecutor for PER_NODE tests (execute_node)."""
    executor = MagicMock(spec=DbtExecutor)
    fail_nodes = fail_nodes or set()

    def _execute_node(node, command, full_refresh=False):
        should_fail = (not success and not fail_nodes) or node.unique_id in fail_nodes
        if should_fail:
            return ExecutionResult(
                success=False,
                node_ids=[node.unique_id],
                error=error or RuntimeError(f"{node.unique_id} failed"),
            )
        node_artifacts = None
        if artifacts and node.unique_id in artifacts:
            node_artifacts = {node.unique_id: artifacts[node.unique_id]}
        return ExecutionResult(
            success=True,
            node_ids=[node.unique_id],
            artifacts=node_artifacts,
            log_messages=log_messages,
        )

    executor.execute_node = MagicMock(side_effect=_execute_node)
    return executor


def write_manifest(tmp_path: Path, data: dict[str, Any]) -> Path:
    """Write manifest data as JSON and return the path."""
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(data))
    return manifest_path


def write_sql_files(project_dir: Path, file_map: dict[str, str]) -> None:
    """Create SQL/CSV files relative to *project_dir* for cache tests.

    ``file_map`` maps relative paths (e.g. ``"models/my_model.sql"``) to
    file content strings.
    """
    for rel_path, content in file_map.items():
        full_path = project_dir / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)


def _make_test_node(
    unique_id: str = "test.test.not_null_my_model_id",
    name: str = "not_null_my_model_id",
    depends_on: tuple[str, ...] = (),
) -> DbtNode:
    return DbtNode(
        unique_id=unique_id,
        name=name,
        resource_type=NodeType.Test,
        depends_on=depends_on,
        materialization=None,
    )


def _make_source_node(
    unique_id: str = "source.test.raw.my_source",
    name: str = "my_source",
    depends_on: tuple[str, ...] = (),
    relation_name: str | None = '"main"."raw"."my_source"',
) -> DbtNode:
    return DbtNode(
        unique_id=unique_id,
        name=name,
        resource_type=NodeType.Source,
        depends_on=depends_on,
        materialization=None,
        relation_name=relation_name,
    )


def write_sources_json(path: Path, results: list[dict[str, Any]]) -> Path:
    """Write a sources.json file at the given path.

    Args:
        path: Directory to write sources.json into
        results: List of source freshness result dicts

    Returns:
        Path to the written sources.json file
    """
    sources_json_path = path / "sources.json"
    sources_json_path.write_text(
        json.dumps({"metadata": {}, "results": results, "elapsed_time": 0.0})
    )
    return sources_json_path


@pytest.fixture
def source_manifest_data() -> dict[str, Any]:
    """Graph with sources -> staging -> marts.

    sources: raw.customers, raw.orders
    staging: stg_src_customers (depends on source.test.raw.customers)
             stg_src_orders (depends on source.test.raw.orders)
    marts:   src_customer_summary (depends on both stg_src models)
    """
    return {
        "nodes": {
            "model.test.stg_src_customers": {
                "name": "stg_src_customers",
                "resource_type": "model",
                "depends_on": {"nodes": ["source.test.raw.customers"]},
                "config": {"materialized": "view"},
            },
            "model.test.stg_src_orders": {
                "name": "stg_src_orders",
                "resource_type": "model",
                "depends_on": {"nodes": ["source.test.raw.orders"]},
                "config": {"materialized": "view"},
            },
            "model.test.src_customer_summary": {
                "name": "src_customer_summary",
                "resource_type": "model",
                "depends_on": {
                    "nodes": [
                        "model.test.stg_src_customers",
                        "model.test.stg_src_orders",
                    ]
                },
                "config": {"materialized": "table"},
            },
        },
        "sources": {
            "source.test.raw.customers": {
                "name": "customers",
                "resource_type": "source",
                "fqn": ["test", "raw", "customers"],
                "relation_name": '"main"."raw"."customers"',
                "config": {},
            },
            "source.test.raw.orders": {
                "name": "orders",
                "resource_type": "source",
                "fqn": ["test", "raw", "orders"],
                "relation_name": '"main"."raw"."orders"',
                "config": {},
            },
        },
    }


@pytest.fixture
def diamond_manifest_data() -> dict[str, Any]:
    """Diamond graph: root -> left/right -> leaf.

    Wave 0: root
    Wave 1: left, right
    Wave 2: leaf
    """
    return {
        "nodes": {
            "model.test.root": {
                "name": "root",
                "resource_type": "model",
                "depends_on": {"nodes": []},
                "config": {"materialized": "table"},
            },
            "model.test.left": {
                "name": "left",
                "resource_type": "model",
                "depends_on": {"nodes": ["model.test.root"]},
                "config": {"materialized": "table"},
            },
            "model.test.right": {
                "name": "right",
                "resource_type": "model",
                "depends_on": {"nodes": ["model.test.root"]},
                "config": {"materialized": "table"},
            },
            "model.test.leaf": {
                "name": "leaf",
                "resource_type": "model",
                "depends_on": {"nodes": ["model.test.left", "model.test.right"]},
                "config": {"materialized": "table"},
            },
        },
        "sources": {},
    }


@pytest.fixture
def linear_manifest_data() -> dict[str, Any]:
    """Linear chain: a -> b -> c.

    Wave 0: a
    Wave 1: b
    Wave 2: c
    """
    return {
        "nodes": {
            "model.test.a": {
                "name": "a",
                "resource_type": "model",
                "depends_on": {"nodes": []},
                "config": {"materialized": "table"},
            },
            "model.test.b": {
                "name": "b",
                "resource_type": "model",
                "depends_on": {"nodes": ["model.test.a"]},
                "config": {"materialized": "table"},
            },
            "model.test.c": {
                "name": "c",
                "resource_type": "model",
                "depends_on": {"nodes": ["model.test.b"]},
                "config": {"materialized": "table"},
            },
        },
        "sources": {},
    }


@pytest.fixture
def diamond_with_tests_manifest_data() -> dict[str, Any]:
    """Diamond model graph + test nodes.

    Models:
        Wave 0: root
        Wave 1: left, right
        Wave 2: leaf

    Tests:
        test_not_null_root_id: depends on root (single-model test)
        test_not_null_leaf_id: depends on leaf (single-model test)
        test_rel_leaf_to_left: depends on leaf AND left (multi-model relationship test)
    """
    return {
        "nodes": {
            "model.test.root": {
                "name": "root",
                "resource_type": "model",
                "depends_on": {"nodes": []},
                "config": {"materialized": "table"},
            },
            "model.test.left": {
                "name": "left",
                "resource_type": "model",
                "depends_on": {"nodes": ["model.test.root"]},
                "config": {"materialized": "table"},
            },
            "model.test.right": {
                "name": "right",
                "resource_type": "model",
                "depends_on": {"nodes": ["model.test.root"]},
                "config": {"materialized": "table"},
            },
            "model.test.leaf": {
                "name": "leaf",
                "resource_type": "model",
                "depends_on": {"nodes": ["model.test.left", "model.test.right"]},
                "config": {"materialized": "table"},
            },
            "test.test.not_null_root_id": {
                "name": "not_null_root_id",
                "resource_type": "test",
                "depends_on": {"nodes": ["model.test.root"]},
                "config": {},
            },
            "test.test.not_null_leaf_id": {
                "name": "not_null_leaf_id",
                "resource_type": "test",
                "depends_on": {"nodes": ["model.test.leaf"]},
                "config": {},
            },
            "test.test.rel_leaf_to_left": {
                "name": "rel_leaf_to_left",
                "resource_type": "test",
                "depends_on": {"nodes": ["model.test.leaf", "model.test.left"]},
                "config": {},
            },
        },
        "sources": {},
    }
