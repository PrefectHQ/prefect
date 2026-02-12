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
    materialization: str = "table",
) -> DbtNode:
    return DbtNode(
        unique_id=unique_id,
        name=name,
        resource_type=resource_type,
        depends_on=depends_on,
        materialization=materialization,
    )


def _make_mock_executor(
    success: bool = True,
    artifacts: dict[str, Any] | None = None,
    error: Exception | None = None,
) -> MagicMock:
    """Create a mock DbtExecutor that returns the given result for execute_wave."""
    executor = MagicMock(spec=DbtExecutor)

    def _execute_wave(nodes, full_refresh=False):
        return ExecutionResult(
            success=success,
            node_ids=[n.unique_id for n in nodes],
            error=error if not success else None,
            artifacts=artifacts,
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
        )

    executor.execute_node = MagicMock(side_effect=_execute_node)
    return executor


def write_manifest(tmp_path: Path, data: dict[str, Any]) -> Path:
    """Write manifest data as JSON and return the path."""
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(data))
    return manifest_path


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
