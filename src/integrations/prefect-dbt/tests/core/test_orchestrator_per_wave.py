"""Tests for PrefectDbtOrchestrator PER_WAVE mode."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from conftest import (
    _make_mock_executor,
    _make_mock_settings,
    write_manifest,
)
from prefect_dbt.core._executor import DbtExecutor, ExecutionResult
from prefect_dbt.core._orchestrator import (
    ExecutionMode,
    PrefectDbtOrchestrator,
    _emit_log_messages,
)

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

    def test_retries_rejected_in_per_wave(self, tmp_path):
        manifest = write_manifest(tmp_path, {"nodes": {}, "sources": {}})
        with pytest.raises(ValueError, match="Retries are only supported in PER_NODE"):
            PrefectDbtOrchestrator(
                settings=_make_mock_settings(),
                manifest_path=manifest,
                executor=_make_mock_executor(),
                execution_mode=ExecutionMode.PER_WAVE,
                retries=1,
            )

    def test_retries_zero_allowed_in_per_wave(self, tmp_path):
        manifest = write_manifest(tmp_path, {"nodes": {}, "sources": {}})
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
            execution_mode=ExecutionMode.PER_WAVE,
            retries=0,
        )
        assert orch._retries == 0


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

    def test_existing_manifest_does_not_trigger_parse(self, tmp_path):
        manifest = write_manifest(tmp_path, {"nodes": {}, "sources": {}})
        executor = _make_mock_executor()
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
        )

        result = orch._resolve_manifest_path()

        assert result == manifest
        executor.resolve_manifest_path.assert_not_called()

    def test_executor_called_when_no_explicit_path(self, tmp_path):
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        manifest = write_manifest(target_dir, {"nodes": {}, "sources": {}})

        executor = _make_mock_executor()
        executor.resolve_manifest_path.return_value = manifest

        settings = _make_mock_settings(
            project_dir=tmp_path,
            target_path=Path("target"),
        )
        orch = PrefectDbtOrchestrator(
            settings=settings,
            executor=executor,
        )

        result = orch._resolve_manifest_path()

        assert result == manifest
        executor.resolve_manifest_path.assert_called_once()
        # Path and target_path should be cached
        assert orch._manifest_path == manifest
        assert orch._settings.target_path == manifest.parent


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

        def _execute_wave(nodes, full_refresh=False, **kwargs):
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

    def test_error_without_exception_no_artifacts(self, tmp_path):
        """Wave failure with no exception and no artifacts falls back to unknown error."""
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

    def test_error_without_exception_uses_artifact_message(self, tmp_path):
        """Wave failure with no exception extracts error from per-node artifacts."""
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
            success=False,
            node_ids=["model.test.m1"],
            error=None,
            artifacts={
                "model.test.m1": {
                    "status": "error",
                    "message": 'relation "raw.nonexistent_table" does not exist',
                    "execution_time": 0.5,
                }
            },
        )

        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
        )

        result = orch.run_build()

        assert result["model.test.m1"]["status"] == "error"
        assert (
            result["model.test.m1"]["error"]["message"]
            == 'relation "raw.nonexistent_table" does not exist'
        )

    def test_error_artifact_message_preferred_over_exception(self, tmp_path):
        """Per-node artifact message takes precedence over wave-level exception."""
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
            success=False,
            node_ids=["model.test.m1"],
            error=RuntimeError("generic wave error"),
            artifacts={
                "model.test.m1": {
                    "status": "error",
                    "message": 'Database Error: relation "raw.missing" does not exist',
                    "execution_time": 0.3,
                }
            },
        )

        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
        )

        result = orch.run_build()

        assert result["model.test.m1"]["status"] == "error"
        assert (
            result["model.test.m1"]["error"]["message"]
            == 'Database Error: relation "raw.missing" does not exist'
        )
        # type still comes from the exception when present
        assert result["model.test.m1"]["error"]["type"] == "RuntimeError"

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
            target=None,
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
            target=None,
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
        """When no manifest_path, executor.resolve_manifest_path() is called and
        target_path is updated to the manifest's parent directory."""
        # Set up so auto-detected manifest exists
        target_dir = tmp_path / "my_target"
        target_dir.mkdir()
        manifest_path = target_dir / "manifest.json"
        manifest_path.write_text(json.dumps(diamond_manifest_data))
        mock_resolve.return_value = {"model.test.root"}

        settings = _make_mock_settings(
            project_dir=tmp_path,
            target_path=Path("my_target"),
        )
        executor = _make_mock_executor()
        executor.resolve_manifest_path.return_value = manifest_path
        orch = PrefectDbtOrchestrator(
            settings=settings,
            executor=executor,
        )

        orch.run_build(select="tag:daily")

        mock_resolve.assert_called_once()
        assert mock_resolve.call_args.kwargs["target_path"] == target_dir


# =============================================================================
# TestRunBuildArtifacts
# =============================================================================


class TestRunBuildTarget:
    def test_target_forwarded_to_executor(self, tmp_path):
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

        orch.run_build(target="prod")

        _, kwargs = executor.execute_wave.call_args
        assert kwargs["target"] == "prod"

    def test_target_none_by_default(self, tmp_path):
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

        _, kwargs = executor.execute_wave.call_args
        assert kwargs["target"] is None

    @patch("prefect_dbt.core._orchestrator.resolve_selection")
    def test_target_forwarded_to_resolve_selection(
        self, mock_resolve, tmp_path, diamond_manifest_data
    ):
        manifest = write_manifest(tmp_path, diamond_manifest_data)
        mock_resolve.return_value = {"model.test.root"}

        executor = _make_mock_executor()
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
        )

        orch.run_build(select="tag:daily", target="staging")

        mock_resolve.assert_called_once()
        assert mock_resolve.call_args.kwargs["target"] == "staging"


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

        def _execute_wave(nodes, full_refresh=False, **kwargs):
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

        def _execute_wave(nodes, full_refresh=False, **kwargs):
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

        def _execute_wave(nodes, full_refresh=False, **kwargs):
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
# TestEmitLogMessages
# =============================================================================


class TestEmitLogMessages:
    def test_emits_for_given_node_id(self):
        mock_logger = MagicMock()
        log_messages = {
            "model.test.m1": [("info", "1 of 3 OK created view")],
        }
        _emit_log_messages(log_messages, "model.test.m1", mock_logger)
        mock_logger.info.assert_called_once_with("1 of 3 OK created view")

    def test_does_not_emit_other_keys(self):
        mock_logger = MagicMock()
        log_messages = {
            "model.test.m1": [("info", "msg for m1")],
            "model.test.m2": [("info", "msg for m2")],
        }
        _emit_log_messages(log_messages, "model.test.m1", mock_logger)
        mock_logger.info.assert_called_once_with("msg for m1")

    def test_emits_at_correct_levels(self):
        mock_logger = MagicMock()
        log_messages = {
            "n": [
                ("debug", "d"),
                ("info", "i"),
                ("warning", "w"),
                ("error", "e"),
            ],
        }
        _emit_log_messages(log_messages, "n", mock_logger)
        mock_logger.debug.assert_called_once_with("d")
        mock_logger.info.assert_called_once_with("i")
        mock_logger.warning.assert_called_once_with("w")
        mock_logger.error.assert_called_once_with("e")

    def test_none_log_messages_is_noop(self):
        mock_logger = MagicMock()
        _emit_log_messages(None, "model.test.m1", mock_logger)
        mock_logger.info.assert_not_called()

    def test_missing_key_is_noop(self):
        mock_logger = MagicMock()
        log_messages = {"model.test.other": [("info", "msg")]}
        _emit_log_messages(log_messages, "model.test.m1", mock_logger)
        mock_logger.info.assert_not_called()

    def test_unknown_level_falls_back_to_info(self):
        mock_logger = MagicMock()
        log_messages = {"n": [("critical", "boom")]}
        _emit_log_messages(log_messages, "n", mock_logger)
        mock_logger.info.assert_called_once_with("boom")


# =============================================================================
# TestPerWaveLogEmission
# =============================================================================


class TestPerWaveLogEmission:
    def test_log_messages_emitted_per_wave(self, tmp_path):
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
        log_messages = {
            "model.test.m1": [("info", "1 of 1 OK created table")],
            "": [("info", "Finished running 1 table model")],
        }
        executor = _make_mock_executor(log_messages=log_messages)
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
        )

        mock_run_logger = MagicMock()
        with patch(
            "prefect_dbt.core._orchestrator.get_run_logger",
            return_value=mock_run_logger,
        ):
            orch.run_build()
            mock_run_logger.info.assert_any_call("1 of 1 OK created table")
            mock_run_logger.info.assert_any_call("Finished running 1 table model")

    def test_log_messages_fall_back_to_module_logger(self, tmp_path):
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
        log_messages = {
            "model.test.m1": [("info", "1 of 1 OK created table")],
        }
        executor = _make_mock_executor(log_messages=log_messages)
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
        )

        with (
            patch(
                "prefect_dbt.core._orchestrator.get_run_logger",
                side_effect=RuntimeError("no run context"),
            ),
            patch("prefect_dbt.core._orchestrator.logger") as mock_logger,
        ):
            orch.run_build()
            mock_logger.info.assert_any_call("1 of 1 OK created table")

    def test_no_log_messages_no_error(self, tmp_path):
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
        assert result["model.test.m1"]["status"] == "success"


# =============================================================================
# TestExtraCliArgs
# =============================================================================


class TestExtraCliArgs:
    """Tests for extra_cli_args validation and forwarding in run_build."""

    def _single_node_manifest(self, tmp_path):
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
        return write_manifest(tmp_path, data)

    # --- Blocked flags ---

    @pytest.mark.parametrize(
        "flag",
        [
            "--select",
            "--models",
            "--exclude",
            "--selector",
            "--indirect-selection",
            "--project-dir",
            "--target-path",
            "--profiles-dir",
            "--log-level",
        ],
    )
    def test_blocked_flag_raises(self, tmp_path, flag):
        manifest = self._single_node_manifest(tmp_path)
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
        )

        with pytest.raises(
            ValueError, match=f"Cannot pass '{flag}' via extra_cli_args"
        ):
            orch.run_build(extra_cli_args=[flag, "some_value"])

    @pytest.mark.parametrize(
        "short_flag,canonical",
        [
            ("-s", "--select"),
            ("-m", "--models"),
        ],
    )
    def test_blocked_short_flag_raises_with_canonical_name(
        self, tmp_path, short_flag, canonical
    ):
        manifest = self._single_node_manifest(tmp_path)
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
        )

        with pytest.raises(
            ValueError, match=f"Cannot pass '{canonical}' via extra_cli_args"
        ):
            orch.run_build(extra_cli_args=[short_flag, "some_value"])

    # --- First-class flags ---

    @pytest.mark.parametrize(
        "flag,api_hint",
        [
            ("--full-refresh", "run_build"),
            ("--target", "run_build"),
            ("--threads", "DbtCoreExecutor"),
            ("--defer", "DbtCoreExecutor"),
            ("--defer-state", "DbtCoreExecutor"),
            ("--favor-state", "DbtCoreExecutor"),
            ("--state", "DbtCoreExecutor"),
        ],
    )
    def test_first_class_flag_raises_with_hint(self, tmp_path, flag, api_hint):
        manifest = self._single_node_manifest(tmp_path)
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
        )

        with pytest.raises(ValueError, match=f"Cannot pass '{flag}'") as exc_info:
            orch.run_build(extra_cli_args=[flag])
        assert api_hint in str(exc_info.value)

    def test_first_class_short_flag_raises_with_canonical_name(self, tmp_path):
        manifest = self._single_node_manifest(tmp_path)
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
        )

        with pytest.raises(ValueError, match="Cannot pass '--target'") as exc_info:
            orch.run_build(extra_cli_args=["-t", "prod"])
        assert "run_build" in str(exc_info.value)

    # --- Caveat flags produce warnings ---

    @pytest.mark.parametrize(
        "flag",
        ["--resource-type", "--exclude-resource-type", "--fail-fast"],
    )
    def test_caveat_flag_warns(self, tmp_path, flag):
        manifest = self._single_node_manifest(tmp_path)
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
        )

        with patch("prefect_dbt.core._orchestrator.logger") as mock_logger:
            orch.run_build(extra_cli_args=[flag, "model"])

        mock_logger.warning.assert_called_once()
        assert flag in mock_logger.warning.call_args[0][1]

    def test_caveat_short_flag_warns_with_canonical_name(self, tmp_path):
        manifest = self._single_node_manifest(tmp_path)
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
        )

        with patch("prefect_dbt.core._orchestrator.logger") as mock_logger:
            orch.run_build(extra_cli_args=["-x"])

        mock_logger.warning.assert_called_once()
        assert "--fail-fast" in mock_logger.warning.call_args[0][1]

    # --- Forwarding ---

    def test_extra_cli_args_forwarded_to_executor(self, tmp_path):
        manifest = self._single_node_manifest(tmp_path)
        executor = _make_mock_executor()
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
        )

        orch.run_build(extra_cli_args=["--store-failures", "--vars", "{'x': 1}"])

        _, kwargs = executor.execute_wave.call_args
        assert kwargs["extra_cli_args"] == ["--store-failures", "--vars", "{'x': 1}"]

    def test_none_extra_cli_args_forwarded(self, tmp_path):
        manifest = self._single_node_manifest(tmp_path)
        executor = _make_mock_executor()
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
        )

        orch.run_build()

        _, kwargs = executor.execute_wave.call_args
        assert kwargs["extra_cli_args"] is None

    def test_safe_flags_pass_through(self, tmp_path):
        manifest = self._single_node_manifest(tmp_path)
        executor = _make_mock_executor()
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
        )

        safe_args = ["--store-failures", "--warn-error", "--no-partial-parse"]
        orch.run_build(extra_cli_args=safe_args)

        _, kwargs = executor.execute_wave.call_args
        assert kwargs["extra_cli_args"] == safe_args

    def test_extra_cli_args_with_select(self, tmp_path):
        """extra_cli_args works alongside the select parameter."""
        manifest = self._single_node_manifest(tmp_path)
        executor = _make_mock_executor()
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
        )

        with patch("prefect_dbt.core._orchestrator.resolve_selection") as mock_resolve:
            mock_resolve.return_value = {"model.test.m1"}
            orch.run_build(
                select="tag:daily",
                extra_cli_args=["--store-failures"],
            )

        _, kwargs = executor.execute_wave.call_args
        assert kwargs["extra_cli_args"] == ["--store-failures"]

    # --- equals-sign syntax (--flag=value) ---

    @pytest.mark.parametrize(
        "token",
        [
            "--select=tag:daily",
            "--project-dir=/tmp/proj",
            "--profiles-dir=/tmp/profiles",
            "--log-level=debug",
            "--exclude=model.foo",
        ],
    )
    def test_blocked_flag_equals_syntax_raises(self, tmp_path, token):
        manifest = self._single_node_manifest(tmp_path)
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
        )
        flag = token.split("=", 1)[0]

        with pytest.raises(
            ValueError, match=f"Cannot pass '{flag}' via extra_cli_args"
        ):
            orch.run_build(extra_cli_args=[token])

    @pytest.mark.parametrize(
        "token,api_hint",
        [
            ("--target=prod", "run_build"),
            ("--threads=4", "DbtCoreExecutor"),
        ],
    )
    def test_first_class_flag_equals_syntax_raises(self, tmp_path, token, api_hint):
        manifest = self._single_node_manifest(tmp_path)
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
        )
        flag = token.split("=", 1)[0]

        with pytest.raises(ValueError, match=f"Cannot pass '{flag}'") as exc_info:
            orch.run_build(extra_cli_args=[token])
        assert api_hint in str(exc_info.value)

    # --- space-separated syntax (--flag value as separate tokens) ---

    def test_blocked_flag_space_separated_raises(self, tmp_path):
        manifest = self._single_node_manifest(tmp_path)
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
        )

        with pytest.raises(
            ValueError, match="Cannot pass '--select' via extra_cli_args"
        ):
            orch.run_build(extra_cli_args=["--select", "tag:daily"])

    def test_first_class_flag_space_separated_raises(self, tmp_path):
        manifest = self._single_node_manifest(tmp_path)
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
        )

        with pytest.raises(ValueError, match="Cannot pass '--target'") as exc_info:
            orch.run_build(extra_cli_args=["--target", "prod"])
        assert "run_build" in str(exc_info.value)
