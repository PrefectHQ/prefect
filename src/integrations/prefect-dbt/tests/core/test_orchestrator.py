"""
Tests for PrefectDbtOrchestrator (PER_WAVE and PER_NODE modes).
"""

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from dbt.artifacts.resources.types import NodeType
from prefect_dbt.core._executor import DbtExecutor, ExecutionResult
from prefect_dbt.core._manifest import DbtNode
from prefect_dbt.core._orchestrator import (
    ExecutionMode,
    PrefectDbtOrchestrator,
)


class _ThreadDelegatingRunner:
    """A stand-in for ProcessPoolTaskRunner that delegates to task.submit().

    In unit tests we can't use real subprocesses because the mock executor
    (MagicMock) isn't picklable.  This runner implements the same context-
    manager + submit interface but dispatches via Prefect's default
    ThreadPoolTaskRunner (used by ``task.submit()``).
    """

    def __init__(self, **kwargs):
        self._kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def submit(self, task, parameters, **kwargs):
        return task.submit(**parameters)


# =============================================================================
# Helpers
# =============================================================================


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


# =============================================================================
# Fixtures
# =============================================================================


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


# =============================================================================
# TestOrchestratorInit
# =============================================================================


class TestOrchestratorInit:
    def test_custom_executor_used(self, tmp_path):
        executor = _make_mock_executor()
        manifest = write_manifest(tmp_path, {"nodes": {}, "sources": {}})
        settings = _make_mock_settings()

        orch = PrefectDbtOrchestrator(
            settings=settings,
            manifest_path=manifest,
            executor=executor,
        )

        assert orch._executor is executor

    @patch("prefect_dbt.core._orchestrator.DbtCoreExecutor")
    def test_default_executor_created(self, mock_core_cls):
        settings = _make_mock_settings()
        PrefectDbtOrchestrator(
            settings=settings,
            threads=4,
            state_path=Path("/state"),
            defer=True,
            defer_state_path=Path("/defer"),
            favor_state=True,
        )

        mock_core_cls.assert_called_once_with(
            settings,
            threads=4,
            state_path=Path("/state"),
            defer=True,
            defer_state_path=Path("/defer"),
            favor_state=True,
        )

    @patch("prefect_dbt.core._orchestrator.DbtCoreExecutor")
    def test_default_executor_minimal(self, mock_core_cls):
        settings = _make_mock_settings()
        PrefectDbtOrchestrator(settings=settings)

        mock_core_cls.assert_called_once_with(
            settings,
            threads=None,
            state_path=None,
            defer=False,
            defer_state_path=None,
            favor_state=False,
        )


# =============================================================================
# TestResolveManifestPath
# =============================================================================


class TestResolveManifestPath:
    def test_explicit_path(self, tmp_path):
        manifest = write_manifest(tmp_path, {"nodes": {}, "sources": {}})
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
        )

        assert orch._resolve_manifest_path() == manifest

    def test_auto_detect_from_settings(self, tmp_path):
        # Set up settings so project_dir/target_path/manifest.json exists
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        manifest = target_dir / "manifest.json"
        manifest.write_text("{}")

        settings = _make_mock_settings(
            project_dir=tmp_path,
            target_path=Path("target"),
        )
        orch = PrefectDbtOrchestrator(
            settings=settings,
            executor=_make_mock_executor(),
        )

        assert orch._resolve_manifest_path() == manifest

    def test_missing_raises_file_not_found(self):
        settings = _make_mock_settings(
            project_dir=Path("/nonexistent"),
            target_path=Path("target"),
        )
        orch = PrefectDbtOrchestrator(
            settings=settings,
            executor=_make_mock_executor(),
        )

        with pytest.raises(FileNotFoundError, match="manifest.json"):
            orch._resolve_manifest_path()

    def test_missing_explicit_path_raises(self, tmp_path):
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=tmp_path / "nonexistent" / "manifest.json",
            executor=_make_mock_executor(),
        )

        with pytest.raises(FileNotFoundError, match="manifest.json"):
            orch._resolve_manifest_path()


# =============================================================================
# TestRunBuildBasic
# =============================================================================


class TestRunBuildBasic:
    def test_empty_manifest_returns_empty_dict(self, tmp_path):
        manifest = write_manifest(tmp_path, {"nodes": {}, "sources": {}})
        executor = _make_mock_executor()
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
        )

        result = orch.run_build()

        assert result == {}
        executor.execute_wave.assert_not_called()

    def test_single_wave_success(self, tmp_path):
        data = {
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                }
            },
            "sources": {},
        }
        manifest = write_manifest(tmp_path, data)
        executor = _make_mock_executor()
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
        )

        result = orch.run_build()

        assert "model.test.m1" in result
        assert result["model.test.m1"]["status"] == "success"
        executor.execute_wave.assert_called_once()

    def test_multi_wave_diamond_executes_all_waves(
        self, tmp_path, diamond_manifest_data
    ):
        manifest = write_manifest(tmp_path, diamond_manifest_data)
        executor = _make_mock_executor()
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
        )

        result = orch.run_build()

        # All 4 nodes should succeed
        assert len(result) == 4
        for node_id in [
            "model.test.root",
            "model.test.left",
            "model.test.right",
            "model.test.leaf",
        ]:
            assert result[node_id]["status"] == "success"

        # 3 waves executed
        assert executor.execute_wave.call_count == 3

    def test_full_refresh_forwarded(self, tmp_path):
        data = {
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                }
            },
            "sources": {},
        }
        manifest = write_manifest(tmp_path, data)
        executor = _make_mock_executor()
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
        )

        orch.run_build(full_refresh=True)

        _, kwargs = executor.execute_wave.call_args
        assert kwargs["full_refresh"] is True

    def test_result_has_timing_fields(self, tmp_path):
        data = {
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                }
            },
            "sources": {},
        }
        manifest = write_manifest(tmp_path, data)
        executor = _make_mock_executor()
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
        )

        result = orch.run_build()
        timing = result["model.test.m1"]["timing"]

        assert "started_at" in timing
        assert "completed_at" in timing
        assert "duration_seconds" in timing
        assert isinstance(timing["duration_seconds"], float)

    def test_result_has_invocation_fields(self, tmp_path):
        data = {
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                }
            },
            "sources": {},
        }
        manifest = write_manifest(tmp_path, data)
        executor = _make_mock_executor()
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
        )

        result = orch.run_build()
        invocation = result["model.test.m1"]["invocation"]

        assert invocation["command"] == "build"
        assert "model.test.m1" in invocation["args"]


# =============================================================================
# TestRunBuildFailure
# =============================================================================


class TestRunBuildFailure:
    def test_failed_wave_marks_nodes_as_error(self, tmp_path):
        data = {
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                }
            },
            "sources": {},
        }
        manifest = write_manifest(tmp_path, data)
        executor = _make_mock_executor(success=False, error=RuntimeError("dbt failed"))
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
        )

        result = orch.run_build()

        assert result["model.test.m1"]["status"] == "error"
        assert "dbt failed" in result["model.test.m1"]["error"]["message"]
        assert result["model.test.m1"]["error"]["type"] == "RuntimeError"

    def test_downstream_waves_skipped(self, tmp_path, linear_manifest_data):
        manifest = write_manifest(tmp_path, linear_manifest_data)

        # Executor that fails on every call
        executor = _make_mock_executor(success=False, error=RuntimeError("boom"))
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
        )

        result = orch.run_build()

        # Wave 0 (a) should be error
        assert result["model.test.a"]["status"] == "error"
        # Waves 1 and 2 (b, c) should be skipped
        assert result["model.test.b"]["status"] == "skipped"
        assert result["model.test.b"]["reason"] == "upstream failure"
        assert "model.test.a" in result["model.test.b"]["failed_upstream"]
        assert result["model.test.c"]["status"] == "skipped"

    def test_first_success_second_fails(self, tmp_path, linear_manifest_data):
        manifest = write_manifest(tmp_path, linear_manifest_data)

        call_count = 0

        def _execute_wave(nodes, full_refresh=False):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ExecutionResult(
                    success=True,
                    node_ids=[n.unique_id for n in nodes],
                )
            else:
                return ExecutionResult(
                    success=False,
                    node_ids=[n.unique_id for n in nodes],
                    error=RuntimeError("wave 2 failed"),
                )

        executor = MagicMock(spec=DbtExecutor)
        executor.execute_wave = MagicMock(side_effect=_execute_wave)

        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
        )

        result = orch.run_build()

        assert result["model.test.a"]["status"] == "success"
        assert result["model.test.b"]["status"] == "error"
        assert result["model.test.c"]["status"] == "skipped"
        assert "model.test.b" in result["model.test.c"]["failed_upstream"]

    def test_executor_not_called_for_skipped_waves(
        self, tmp_path, linear_manifest_data
    ):
        manifest = write_manifest(tmp_path, linear_manifest_data)
        executor = _make_mock_executor(success=False, error=RuntimeError("fail"))
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
        )

        orch.run_build()

        # Only wave 0 should be executed (a); b and c skipped
        assert executor.execute_wave.call_count == 1

    def test_error_details_in_result(self, tmp_path):
        data = {
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                }
            },
            "sources": {},
        }
        manifest = write_manifest(tmp_path, data)
        executor = _make_mock_executor(success=False, error=ValueError("bad config"))
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
        )

        result = orch.run_build()
        error = result["model.test.m1"]["error"]

        assert error["message"] == "bad config"
        assert error["type"] == "ValueError"

    def test_error_without_exception(self, tmp_path):
        """Wave failure with no exception object still produces error info."""
        data = {
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                }
            },
            "sources": {},
        }
        manifest = write_manifest(tmp_path, data)

        executor = MagicMock(spec=DbtExecutor)
        executor.execute_wave.return_value = ExecutionResult(
            success=False, node_ids=["model.test.m1"], error=None
        )

        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
        )

        result = orch.run_build()

        assert result["model.test.m1"]["status"] == "error"
        assert result["model.test.m1"]["error"]["message"] == "unknown error"
        assert result["model.test.m1"]["error"]["type"] == "UnknownError"

    def test_executor_exception_caught(self, tmp_path, linear_manifest_data):
        """If execute_wave raises, the wave gets error status and downstream is skipped."""
        manifest = write_manifest(tmp_path, linear_manifest_data)

        executor = MagicMock(spec=DbtExecutor)
        executor.execute_wave.side_effect = RuntimeError("executor exploded")

        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
        )

        result = orch.run_build()

        # Wave 0 (a) should be error with the raised exception details
        assert result["model.test.a"]["status"] == "error"
        assert "executor exploded" in result["model.test.a"]["error"]["message"]
        assert result["model.test.a"]["error"]["type"] == "RuntimeError"

        # Downstream waves (b, c) should be skipped
        assert result["model.test.b"]["status"] == "skipped"
        assert result["model.test.b"]["reason"] == "upstream failure"
        assert "model.test.a" in result["model.test.b"]["failed_upstream"]
        assert result["model.test.c"]["status"] == "skipped"


# =============================================================================
# TestRunBuildWithSelectors
# =============================================================================


class TestRunBuildWithSelectors:
    @patch("prefect_dbt.core._orchestrator.resolve_selection")
    def test_select_filters_nodes(self, mock_resolve, tmp_path, diamond_manifest_data):
        manifest = write_manifest(tmp_path, diamond_manifest_data)
        # Only select root and left
        mock_resolve.return_value = {"model.test.root", "model.test.left"}

        executor = _make_mock_executor()
        settings = _make_mock_settings()
        orch = PrefectDbtOrchestrator(
            settings=settings,
            manifest_path=manifest,
            executor=executor,
        )

        result = orch.run_build(select="tag:daily")

        assert "model.test.root" in result
        assert "model.test.left" in result
        assert "model.test.right" not in result
        assert "model.test.leaf" not in result

    @patch("prefect_dbt.core._orchestrator.resolve_selection")
    def test_no_selectors_skips_resolve(self, mock_resolve, tmp_path):
        data = {
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                }
            },
            "sources": {},
        }
        manifest = write_manifest(tmp_path, data)
        executor = _make_mock_executor()
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
        )

        orch.run_build()

        mock_resolve.assert_not_called()

    @patch("prefect_dbt.core._orchestrator.resolve_selection")
    def test_exclude_works(self, mock_resolve, tmp_path, diamond_manifest_data):
        manifest = write_manifest(tmp_path, diamond_manifest_data)
        mock_resolve.return_value = {
            "model.test.root",
            "model.test.left",
            "model.test.right",
        }

        executor = _make_mock_executor()
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
        )

        result = orch.run_build(exclude="model.test.leaf")

        assert "model.test.leaf" not in result
        mock_resolve.assert_called_once()

    @patch("prefect_dbt.core._orchestrator.resolve_selection")
    def test_settings_paths_passed_to_resolve(
        self, mock_resolve, tmp_path, diamond_manifest_data
    ):
        manifest = write_manifest(tmp_path, diamond_manifest_data)
        mock_resolve.return_value = {"model.test.root"}

        settings = _make_mock_settings(
            project_dir=Path("/my/project"),
            profiles_dir=Path("/my/profiles"),
            target_path=Path("custom_target"),
        )
        executor = _make_mock_executor()
        orch = PrefectDbtOrchestrator(
            settings=settings,
            manifest_path=manifest,
            executor=executor,
        )

        orch.run_build(select="tag:nightly")

        # manifest_path is absolute, so target_path is its parent directly.
        # profiles_dir comes from resolve_profiles_yml(), not raw settings.
        mock_resolve.assert_called_once_with(
            project_dir=Path("/my/project"),
            profiles_dir=Path("/resolved/profiles"),
            select="tag:nightly",
            exclude=None,
            target_path=tmp_path,
        )

    @patch("prefect_dbt.core._orchestrator.resolve_selection")
    def test_select_and_exclude_together(
        self, mock_resolve, tmp_path, diamond_manifest_data
    ):
        manifest = write_manifest(tmp_path, diamond_manifest_data)
        mock_resolve.return_value = {"model.test.root", "model.test.left"}

        settings = _make_mock_settings()
        executor = _make_mock_executor()
        orch = PrefectDbtOrchestrator(
            settings=settings,
            manifest_path=manifest,
            executor=executor,
        )

        orch.run_build(select="tag:daily", exclude="model.test.leaf")

        # profiles_dir comes from resolve_profiles_yml(), not raw settings.
        mock_resolve.assert_called_once_with(
            project_dir=settings.project_dir,
            profiles_dir=Path("/resolved/profiles"),
            select="tag:daily",
            exclude="model.test.leaf",
            target_path=tmp_path,
        )

    @patch("prefect_dbt.core._orchestrator.resolve_selection")
    def test_explicit_manifest_infers_target_path(
        self, mock_resolve, tmp_path, diamond_manifest_data
    ):
        """When manifest_path is explicitly set, target_path = manifest's parent."""
        custom_dir = tmp_path / "custom" / "out"
        custom_dir.mkdir(parents=True)
        manifest = write_manifest(custom_dir, diamond_manifest_data)
        mock_resolve.return_value = {"model.test.root"}

        executor = _make_mock_executor()
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
        )

        orch.run_build(select="tag:daily")

        mock_resolve.assert_called_once()
        assert mock_resolve.call_args.kwargs["target_path"] == custom_dir

    @patch("prefect_dbt.core._orchestrator.resolve_selection")
    def test_relative_manifest_path_resolved_against_project_dir(
        self, mock_resolve, tmp_path, diamond_manifest_data
    ):
        """A relative manifest_path is resolved against project_dir, not CWD."""
        # Place manifest inside project_dir/custom_target/
        target_dir = tmp_path / "custom_target"
        target_dir.mkdir()
        write_manifest(target_dir, diamond_manifest_data)

        mock_resolve.return_value = {"model.test.root"}

        settings = _make_mock_settings(project_dir=tmp_path)
        executor = _make_mock_executor()
        orch = PrefectDbtOrchestrator(
            settings=settings,
            manifest_path=Path("custom_target/manifest.json"),
            executor=executor,
        )

        orch.run_build(select="tag:daily")

        mock_resolve.assert_called_once()
        resolved_target = mock_resolve.call_args.kwargs["target_path"]
        # Must be absolute and equal to project_dir/custom_target (resolved)
        assert resolved_target.is_absolute()
        assert resolved_target == (tmp_path / "custom_target").resolve()

    @patch("prefect_dbt.core._orchestrator.resolve_selection")
    def test_default_target_path_from_settings(
        self, mock_resolve, tmp_path, diamond_manifest_data
    ):
        """When no manifest_path, target_path comes from settings."""
        # Set up so auto-detected manifest exists
        target_dir = tmp_path / "my_target"
        target_dir.mkdir()
        (target_dir / "manifest.json").write_text(json.dumps(diamond_manifest_data))
        mock_resolve.return_value = {"model.test.root"}

        settings = _make_mock_settings(
            project_dir=tmp_path,
            target_path=Path("my_target"),
        )
        executor = _make_mock_executor()
        orch = PrefectDbtOrchestrator(
            settings=settings,
            executor=executor,
        )

        orch.run_build(select="tag:daily")

        mock_resolve.assert_called_once()
        assert mock_resolve.call_args.kwargs["target_path"] == Path("my_target")


# =============================================================================
# TestRunBuildArtifacts
# =============================================================================


class TestRunBuildArtifacts:
    def test_execution_time_from_artifacts_enriches_timing(self, tmp_path):
        data = {
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                }
            },
            "sources": {},
        }
        manifest = write_manifest(tmp_path, data)
        executor = _make_mock_executor(
            success=True,
            artifacts={
                "model.test.m1": {
                    "status": "success",
                    "message": "OK",
                    "execution_time": 3.14,
                }
            },
        )
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
        )

        result = orch.run_build()

        assert result["model.test.m1"]["timing"]["execution_time"] == 3.14

    def test_no_artifacts_no_execution_time(self, tmp_path):
        data = {
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                }
            },
            "sources": {},
        }
        manifest = write_manifest(tmp_path, data)
        executor = _make_mock_executor(success=True, artifacts=None)
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
        )

        result = orch.run_build()

        assert "execution_time" not in result["model.test.m1"]["timing"]

    def test_artifact_for_missing_node_ignored(self, tmp_path):
        """Artifacts for nodes not in wave are harmlessly ignored."""
        data = {
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                }
            },
            "sources": {},
        }
        manifest = write_manifest(tmp_path, data)
        executor = _make_mock_executor(
            success=True,
            artifacts={
                "model.test.other": {
                    "status": "success",
                    "execution_time": 1.0,
                }
            },
        )
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
        )

        result = orch.run_build()

        assert result["model.test.m1"]["status"] == "success"
        assert "execution_time" not in result["model.test.m1"]["timing"]


# =============================================================================
# TestRunBuildWaveOrder
# =============================================================================


class TestRunBuildWaveOrder:
    def test_diamond_wave_ordering(self, tmp_path, diamond_manifest_data):
        """Verify root -> left/right -> leaf wave ordering."""
        manifest = write_manifest(tmp_path, diamond_manifest_data)

        wave_calls: list[set[str]] = []

        def _execute_wave(nodes, full_refresh=False):
            wave_calls.append({n.unique_id for n in nodes})
            return ExecutionResult(
                success=True,
                node_ids=[n.unique_id for n in nodes],
            )

        executor = MagicMock(spec=DbtExecutor)
        executor.execute_wave = MagicMock(side_effect=_execute_wave)

        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
        )

        orch.run_build()

        assert len(wave_calls) == 3
        # Wave 0: root
        assert wave_calls[0] == {"model.test.root"}
        # Wave 1: left and right (order within wave doesn't matter)
        assert wave_calls[1] == {"model.test.left", "model.test.right"}
        # Wave 2: leaf
        assert wave_calls[2] == {"model.test.leaf"}

    def test_linear_wave_ordering(self, tmp_path, linear_manifest_data):
        """Verify a -> b -> c wave ordering."""
        manifest = write_manifest(tmp_path, linear_manifest_data)

        wave_calls: list[set[str]] = []

        def _execute_wave(nodes, full_refresh=False):
            wave_calls.append({n.unique_id for n in nodes})
            return ExecutionResult(
                success=True,
                node_ids=[n.unique_id for n in nodes],
            )

        executor = MagicMock(spec=DbtExecutor)
        executor.execute_wave = MagicMock(side_effect=_execute_wave)

        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
        )

        orch.run_build()

        assert len(wave_calls) == 3
        assert wave_calls[0] == {"model.test.a"}
        assert wave_calls[1] == {"model.test.b"}
        assert wave_calls[2] == {"model.test.c"}

    def test_single_node_single_wave(self, tmp_path):
        data = {
            "nodes": {
                "model.test.solo": {
                    "name": "solo",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                }
            },
            "sources": {},
        }
        manifest = write_manifest(tmp_path, data)

        wave_calls: list[set[str]] = []

        def _execute_wave(nodes, full_refresh=False):
            wave_calls.append({n.unique_id for n in nodes})
            return ExecutionResult(
                success=True,
                node_ids=[n.unique_id for n in nodes],
            )

        executor = MagicMock(spec=DbtExecutor)
        executor.execute_wave = MagicMock(side_effect=_execute_wave)

        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
        )

        orch.run_build()

        assert len(wave_calls) == 1
        assert wave_calls[0] == {"model.test.solo"}


# =============================================================================
# PER_NODE mode fixtures
# =============================================================================


@pytest.fixture
def mixed_resource_manifest_data() -> dict[str, Any]:
    """Manifest with seeds, models, and a snapshot.

    Wave 0: seed_users (seed)
    Wave 1: stg_users (model, depends on seed_users)
    Wave 1: snap_users (snapshot, depends on seed_users)
    """
    return {
        "nodes": {
            "seed.test.seed_users": {
                "name": "seed_users",
                "resource_type": "seed",
                "depends_on": {"nodes": []},
                "config": {"materialized": "seed"},
                "original_file_path": "seeds/seed_users.csv",
            },
            "model.test.stg_users": {
                "name": "stg_users",
                "resource_type": "model",
                "depends_on": {"nodes": ["seed.test.seed_users"]},
                "config": {"materialized": "view"},
                "original_file_path": "models/stg_users.sql",
            },
            "snapshot.test.snap_users": {
                "name": "snap_users",
                "resource_type": "snapshot",
                "depends_on": {"nodes": ["seed.test.seed_users"]},
                "config": {"materialized": "snapshot"},
                "original_file_path": "snapshots/snap_users.sql",
            },
        },
        "sources": {},
    }


@pytest.fixture(autouse=True)
def _use_thread_runner_for_per_node(monkeypatch):
    """Replace ProcessPoolTaskRunner with a thread-delegating stand-in.

    Unit tests use MagicMock executors that aren't picklable, so we can't
    send them to real subprocesses.  This fixture swaps in a lightweight
    runner that delegates to Prefect's default ThreadPoolTaskRunner via
    ``task.submit()``.
    """
    monkeypatch.setattr(
        "prefect.task_runners.ProcessPoolTaskRunner",
        _ThreadDelegatingRunner,
    )


# =============================================================================
# TestPerNodeInit
# =============================================================================


class TestPerNodeInit:
    def test_execution_mode_stored(self, tmp_path):
        manifest = write_manifest(tmp_path, {"nodes": {}, "sources": {}})
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
            execution_mode=ExecutionMode.PER_NODE,
        )
        assert orch._execution_mode == ExecutionMode.PER_NODE

    def test_retries_stored(self, tmp_path):
        manifest = write_manifest(tmp_path, {"nodes": {}, "sources": {}})
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
            retries=3,
            retry_delay_seconds=60,
        )
        assert orch._retries == 3
        assert orch._retry_delay_seconds == 60

    def test_int_concurrency_stored(self, tmp_path):
        manifest = write_manifest(tmp_path, {"nodes": {}, "sources": {}})
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
            concurrency=4,
        )
        assert orch._concurrency == 4

    def test_str_concurrency_stored(self, tmp_path):
        manifest = write_manifest(tmp_path, {"nodes": {}, "sources": {}})
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
            concurrency="dbt-warehouse",
        )
        assert orch._concurrency == "dbt-warehouse"

    def test_no_concurrency_default(self, tmp_path):
        manifest = write_manifest(tmp_path, {"nodes": {}, "sources": {}})
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
        )
        assert orch._concurrency is None

    def test_default_execution_mode_is_per_wave(self, tmp_path):
        manifest = write_manifest(tmp_path, {"nodes": {}, "sources": {}})
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
        )
        assert orch._execution_mode == ExecutionMode.PER_WAVE


# =============================================================================
# TestPerNodeBasic
# =============================================================================


class TestPerNodeBasic:
    def test_empty_manifest_returns_empty_dict(self, tmp_path):
        from prefect import flow

        manifest = write_manifest(tmp_path, {"nodes": {}, "sources": {}})
        executor = _make_mock_executor_per_node()
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
            execution_mode=ExecutionMode.PER_NODE,
        )

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()
        assert result == {}
        executor.execute_node.assert_not_called()

    def test_single_node_success(self, tmp_path):
        from prefect import flow

        data = {
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                }
            },
            "sources": {},
        }
        manifest = write_manifest(tmp_path, data)
        executor = _make_mock_executor_per_node()
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
            execution_mode=ExecutionMode.PER_NODE,
        )

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        assert "model.test.m1" in result
        assert result["model.test.m1"]["status"] == "success"
        executor.execute_node.assert_called_once()

    def test_multi_wave_diamond_all_succeed(self, tmp_path, diamond_manifest_data):
        from prefect import flow

        manifest = write_manifest(tmp_path, diamond_manifest_data)
        executor = _make_mock_executor_per_node()
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
            execution_mode=ExecutionMode.PER_NODE,
        )

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        assert len(result) == 4
        for node_id in [
            "model.test.root",
            "model.test.left",
            "model.test.right",
            "model.test.leaf",
        ]:
            assert result[node_id]["status"] == "success"

        # One execute_node call per node
        assert executor.execute_node.call_count == 4

    def test_execute_node_called_not_execute_wave(self, tmp_path):
        """PER_NODE uses execute_node, not execute_wave."""
        from prefect import flow

        data = {
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                }
            },
            "sources": {},
        }
        manifest = write_manifest(tmp_path, data)
        executor = _make_mock_executor_per_node()
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
            execution_mode=ExecutionMode.PER_NODE,
        )

        @flow
        def test_flow():
            return orch.run_build()

        test_flow()

        executor.execute_node.assert_called_once()
        executor.execute_wave.assert_not_called()

    def test_full_refresh_forwarded(self, tmp_path):
        from prefect import flow

        data = {
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                }
            },
            "sources": {},
        }
        manifest = write_manifest(tmp_path, data)
        executor = _make_mock_executor_per_node()
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
            execution_mode=ExecutionMode.PER_NODE,
        )

        @flow
        def test_flow():
            return orch.run_build(full_refresh=True)

        test_flow()

        # full_refresh is the 3rd positional arg to execute_node(node, command, full_refresh)
        args, kwargs = executor.execute_node.call_args
        assert args[2] is True or kwargs.get("full_refresh") is True


# =============================================================================
# TestPerNodeCommandMapping
# =============================================================================


class TestPerNodeCommandMapping:
    def test_model_uses_run_command(self, tmp_path):
        from prefect import flow

        data = {
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                }
            },
            "sources": {},
        }
        manifest = write_manifest(tmp_path, data)
        executor = _make_mock_executor_per_node()
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
            execution_mode=ExecutionMode.PER_NODE,
        )

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        # Invocation should show "run" command for models
        assert result["model.test.m1"]["invocation"]["command"] == "run"

    def test_seed_uses_seed_command(self, tmp_path):
        from prefect import flow

        data = {
            "nodes": {
                "seed.test.users": {
                    "name": "users",
                    "resource_type": "seed",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "seed"},
                    "original_file_path": "seeds/users.csv",
                }
            },
            "sources": {},
        }
        manifest = write_manifest(tmp_path, data)
        executor = _make_mock_executor_per_node()
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
            execution_mode=ExecutionMode.PER_NODE,
        )

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        assert result["seed.test.users"]["invocation"]["command"] == "seed"

    def test_snapshot_uses_snapshot_command(self, tmp_path):
        from prefect import flow

        data = {
            "nodes": {
                "snapshot.test.snap_users": {
                    "name": "snap_users",
                    "resource_type": "snapshot",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "snapshot"},
                    "original_file_path": "snapshots/snap_users.sql",
                }
            },
            "sources": {},
        }
        manifest = write_manifest(tmp_path, data)
        executor = _make_mock_executor_per_node()
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
            execution_mode=ExecutionMode.PER_NODE,
        )

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        assert result["snapshot.test.snap_users"]["invocation"]["command"] == "snapshot"

    def test_mixed_resource_types(self, tmp_path, mixed_resource_manifest_data):
        """Each resource type gets the correct dbt command."""
        from prefect import flow

        manifest = write_manifest(tmp_path, mixed_resource_manifest_data)
        executor = _make_mock_executor_per_node()
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
            execution_mode=ExecutionMode.PER_NODE,
        )

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        assert result["seed.test.seed_users"]["invocation"]["command"] == "seed"
        assert result["model.test.stg_users"]["invocation"]["command"] == "run"
        assert result["snapshot.test.snap_users"]["invocation"]["command"] == "snapshot"

    def test_executor_receives_correct_command(self, tmp_path):
        """Verify execute_node is called with the right command string."""
        from prefect import flow

        data = {
            "nodes": {
                "seed.test.users": {
                    "name": "users",
                    "resource_type": "seed",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "seed"},
                    "original_file_path": "seeds/users.csv",
                }
            },
            "sources": {},
        }
        manifest = write_manifest(tmp_path, data)
        executor = _make_mock_executor_per_node()
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
            execution_mode=ExecutionMode.PER_NODE,
        )

        @flow
        def test_flow():
            return orch.run_build()

        test_flow()

        args, kwargs = executor.execute_node.call_args
        # command should be "seed"
        assert args[1] == "seed" or kwargs.get("command") == "seed"


# =============================================================================
# TestPerNodeFailure
# =============================================================================


class TestPerNodeFailure:
    def test_failed_node_marked_as_error(self, tmp_path):
        from prefect import flow

        data = {
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                }
            },
            "sources": {},
        }
        manifest = write_manifest(tmp_path, data)
        executor = _make_mock_executor_per_node(
            success=False, error=RuntimeError("dbt failed")
        )
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
            execution_mode=ExecutionMode.PER_NODE,
        )

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        assert result["model.test.m1"]["status"] == "error"
        assert "dbt failed" in result["model.test.m1"]["error"]["message"]
        assert result["model.test.m1"]["error"]["type"] == "RuntimeError"

    def test_downstream_skip_on_failure(self, tmp_path, linear_manifest_data):
        """In a linear chain a->b->c, if a fails, b and c are skipped."""
        from prefect import flow

        manifest = write_manifest(tmp_path, linear_manifest_data)
        executor = _make_mock_executor_per_node(
            fail_nodes={"model.test.a"},
            error=RuntimeError("a failed"),
        )
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
            execution_mode=ExecutionMode.PER_NODE,
        )

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        assert result["model.test.a"]["status"] == "error"
        assert result["model.test.b"]["status"] == "skipped"
        assert result["model.test.b"]["reason"] == "upstream failure"
        assert "model.test.a" in result["model.test.b"]["failed_upstream"]
        assert result["model.test.c"]["status"] == "skipped"

    def test_partial_wave_failure_diamond(self, tmp_path, diamond_manifest_data):
        """In diamond graph, if 'right' fails, 'left' succeeds and 'leaf' is skipped."""
        from prefect import flow

        manifest = write_manifest(tmp_path, diamond_manifest_data)
        executor = _make_mock_executor_per_node(
            fail_nodes={"model.test.right"},
            error=RuntimeError("right failed"),
        )
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
            execution_mode=ExecutionMode.PER_NODE,
        )

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        assert result["model.test.root"]["status"] == "success"
        assert result["model.test.left"]["status"] == "success"
        assert result["model.test.right"]["status"] == "error"
        # Leaf depends on both left and right; right failed, so leaf is skipped
        assert result["model.test.leaf"]["status"] == "skipped"
        assert "model.test.right" in result["model.test.leaf"]["failed_upstream"]

    def test_independent_nodes_not_affected(self, tmp_path):
        """Nodes in the same wave are independent — failure of one doesn't affect others."""
        from prefect import flow

        data = {
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
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                },
                "model.test.c": {
                    "name": "c",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                },
            },
            "sources": {},
        }
        manifest = write_manifest(tmp_path, data)
        # Only 'b' fails
        executor = _make_mock_executor_per_node(
            fail_nodes={"model.test.b"},
            error=RuntimeError("b failed"),
        )
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
            execution_mode=ExecutionMode.PER_NODE,
        )

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        # a and c are independent and should succeed
        assert result["model.test.a"]["status"] == "success"
        assert result["model.test.b"]["status"] == "error"
        assert result["model.test.c"]["status"] == "success"

    def test_error_without_exception(self, tmp_path):
        """Node failure with no exception object still produces error info."""
        from prefect import flow

        data = {
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                }
            },
            "sources": {},
        }
        manifest = write_manifest(tmp_path, data)

        executor = MagicMock(spec=DbtExecutor)
        executor.execute_node.return_value = ExecutionResult(
            success=False, node_ids=["model.test.m1"], error=None
        )

        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
            execution_mode=ExecutionMode.PER_NODE,
        )

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        assert result["model.test.m1"]["status"] == "error"
        assert result["model.test.m1"]["error"]["message"] == "unknown error"
        assert result["model.test.m1"]["error"]["type"] == "UnknownError"

    def test_transitive_skip_propagation(self, tmp_path, linear_manifest_data):
        """Skipped nodes also cause their dependents to be skipped."""
        from prefect import flow

        manifest = write_manifest(tmp_path, linear_manifest_data)
        # 'a' fails, so 'b' is skipped, and 'c' should also be skipped
        executor = _make_mock_executor_per_node(
            fail_nodes={"model.test.a"},
            error=RuntimeError("a failed"),
        )
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
            execution_mode=ExecutionMode.PER_NODE,
        )

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        assert result["model.test.a"]["status"] == "error"
        assert result["model.test.b"]["status"] == "skipped"
        assert result["model.test.c"]["status"] == "skipped"
        # c's failed_upstream should be 'b' (its direct dependency that was skipped)
        assert "model.test.b" in result["model.test.c"]["failed_upstream"]

    def test_executor_not_called_for_skipped_nodes(
        self, tmp_path, linear_manifest_data
    ):
        """Skipped nodes don't invoke the executor."""
        from prefect import flow

        manifest = write_manifest(tmp_path, linear_manifest_data)
        executor = _make_mock_executor_per_node(
            fail_nodes={"model.test.a"},
            error=RuntimeError("a failed"),
        )
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
            execution_mode=ExecutionMode.PER_NODE,
        )

        @flow
        def test_flow():
            return orch.run_build()

        test_flow()

        # Only 'a' should have been executed (b and c skipped)
        assert executor.execute_node.call_count == 1


# =============================================================================
# TestPerNodeResults
# =============================================================================


class TestPerNodeResults:
    def test_result_has_timing_fields(self, tmp_path):
        from prefect import flow

        data = {
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                }
            },
            "sources": {},
        }
        manifest = write_manifest(tmp_path, data)
        executor = _make_mock_executor_per_node()
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
            execution_mode=ExecutionMode.PER_NODE,
        )

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()
        timing = result["model.test.m1"]["timing"]

        assert "started_at" in timing
        assert "completed_at" in timing
        assert "duration_seconds" in timing
        assert isinstance(timing["duration_seconds"], float)

    def test_result_has_per_node_invocation(self, tmp_path):
        """PER_NODE invocation shows the specific command, not 'build'."""
        from prefect import flow

        data = {
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                }
            },
            "sources": {},
        }
        manifest = write_manifest(tmp_path, data)
        executor = _make_mock_executor_per_node()
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
            execution_mode=ExecutionMode.PER_NODE,
        )

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()
        invocation = result["model.test.m1"]["invocation"]

        # PER_NODE uses specific command, not "build"
        assert invocation["command"] == "run"
        assert "model.test.m1" in invocation["args"]

    def test_artifacts_enrich_timing(self, tmp_path):
        from prefect import flow

        data = {
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                }
            },
            "sources": {},
        }
        manifest = write_manifest(tmp_path, data)
        executor = _make_mock_executor_per_node(
            artifacts={
                "model.test.m1": {
                    "status": "success",
                    "message": "OK",
                    "execution_time": 2.71,
                }
            },
        )
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
            execution_mode=ExecutionMode.PER_NODE,
        )

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        assert result["model.test.m1"]["timing"]["execution_time"] == 2.71

    def test_failed_node_has_timing_and_invocation(self, tmp_path):
        """Error results include timing and invocation from the last attempt."""
        from prefect import flow

        data = {
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                }
            },
            "sources": {},
        }
        manifest = write_manifest(tmp_path, data)
        executor = _make_mock_executor_per_node(
            success=False, error=RuntimeError("boom")
        )
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
            execution_mode=ExecutionMode.PER_NODE,
        )

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        assert result["model.test.m1"]["status"] == "error"
        assert "timing" in result["model.test.m1"]
        assert "invocation" in result["model.test.m1"]


# =============================================================================
# TestPerNodeRetries
# =============================================================================


class TestPerNodeRetries:
    def test_retry_succeeds_on_second_attempt(self, tmp_path):
        """Node fails once, then succeeds on retry."""
        from prefect import flow

        data = {
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                }
            },
            "sources": {},
        }
        manifest = write_manifest(tmp_path, data)

        call_count = 0

        def _execute_node(node, command, full_refresh=False):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ExecutionResult(
                    success=False,
                    node_ids=[node.unique_id],
                    error=RuntimeError("transient error"),
                )
            return ExecutionResult(
                success=True,
                node_ids=[node.unique_id],
            )

        executor = MagicMock(spec=DbtExecutor)
        executor.execute_node = MagicMock(side_effect=_execute_node)

        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
            execution_mode=ExecutionMode.PER_NODE,
            retries=1,
            retry_delay_seconds=0,
        )

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        assert result["model.test.m1"]["status"] == "success"
        # Called twice: first fail, then retry success
        assert executor.execute_node.call_count == 2

    def test_retries_exhausted_marks_error(self, tmp_path):
        """Node fails after all retries and is marked as error."""
        from prefect import flow

        data = {
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                }
            },
            "sources": {},
        }
        manifest = write_manifest(tmp_path, data)
        executor = _make_mock_executor_per_node(
            success=False, error=RuntimeError("persistent error")
        )
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
            execution_mode=ExecutionMode.PER_NODE,
            retries=2,
            retry_delay_seconds=0,
        )

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        assert result["model.test.m1"]["status"] == "error"
        # 1 original + 2 retries = 3 calls
        assert executor.execute_node.call_count == 3


# =============================================================================
# TestPerNodeConcurrency
# =============================================================================


class TestPerNodeConcurrency:
    def test_int_concurrency_sets_max_workers(self, monkeypatch, tmp_path):
        """With concurrency=2, ProcessPoolTaskRunner is created with max_workers=2."""
        from prefect import flow

        data = {
            "nodes": {
                f"model.test.m{i}": {
                    "name": f"m{i}",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                }
                for i in range(4)
            },
            "sources": {},
        }
        manifest = write_manifest(tmp_path, data)
        executor = _make_mock_executor_per_node()

        # Track the max_workers passed to the runner
        captured_kwargs: list[dict] = []

        class _TrackingRunner(_ThreadDelegatingRunner):
            def __init__(self, **kwargs):
                captured_kwargs.append(kwargs)
                super().__init__(**kwargs)

        monkeypatch.setattr(
            "prefect.task_runners.ProcessPoolTaskRunner", _TrackingRunner
        )

        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
            execution_mode=ExecutionMode.PER_NODE,
            concurrency=2,
        )

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        # ProcessPoolTaskRunner should have been created with max_workers=2
        assert len(captured_kwargs) == 1
        assert captured_kwargs[0]["max_workers"] == 2

        # All nodes should succeed
        for node_id in data["nodes"]:
            assert result[node_id]["status"] == "success"

    def test_no_concurrency_uses_wave_size(self, monkeypatch, tmp_path):
        """Without int concurrency, max_workers = max wave size."""
        from prefect import flow

        # Diamond: wave sizes are 1, 2, 1 -> max_workers should be 2
        data = {
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
        manifest = write_manifest(tmp_path, data)
        executor = _make_mock_executor_per_node()

        captured_kwargs: list[dict] = []

        class _TrackingRunner(_ThreadDelegatingRunner):
            def __init__(self, **kwargs):
                captured_kwargs.append(kwargs)
                super().__init__(**kwargs)

        monkeypatch.setattr(
            "prefect.task_runners.ProcessPoolTaskRunner", _TrackingRunner
        )

        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
            execution_mode=ExecutionMode.PER_NODE,
        )

        @flow
        def test_flow():
            return orch.run_build()

        test_flow()

        # max wave size is 2 (left + right)
        assert len(captured_kwargs) == 1
        assert captured_kwargs[0]["max_workers"] == 2


# =============================================================================
# TestPerNodeWithSelectors
# =============================================================================


class TestPerNodeWithSelectors:
    @patch("prefect_dbt.core._orchestrator.resolve_selection")
    def test_select_filters_nodes(self, mock_resolve, tmp_path, diamond_manifest_data):
        from prefect import flow

        manifest = write_manifest(tmp_path, diamond_manifest_data)
        mock_resolve.return_value = {"model.test.root", "model.test.left"}

        executor = _make_mock_executor_per_node()
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
            execution_mode=ExecutionMode.PER_NODE,
        )

        @flow
        def test_flow():
            return orch.run_build(select="tag:daily")

        result = test_flow()

        assert "model.test.root" in result
        assert "model.test.left" in result
        assert "model.test.right" not in result
        assert "model.test.leaf" not in result
