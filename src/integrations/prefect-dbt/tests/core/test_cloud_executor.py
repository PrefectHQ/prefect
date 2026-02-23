"""Tests for DbtCloudExecutor."""

import json
import shlex
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
import respx
from dbt.artifacts.resources.types import NodeType
from prefect_dbt.cloud import DbtCloudExecutor
from prefect_dbt.cloud.runs import DbtCloudJobRunStatus
from prefect_dbt.core._executor import ExecutionResult
from prefect_dbt.core._manifest import DbtNode

# =============================================================================
# Constants
# =============================================================================

_ACCOUNT_ID = 123
_DOMAIN = "cloud.getdbt.com"
_BASE = f"https://{_DOMAIN}/api/v2/accounts/{_ACCOUNT_ID}"

# =============================================================================
# Helpers
# =============================================================================


def _make_node(
    unique_id: str = "model.test.my_model",
    name: str = "my_model",
    resource_type: NodeType = NodeType.Model,
    original_file_path: str | None = "models/my_model.sql",
) -> DbtNode:
    return DbtNode(
        unique_id=unique_id,
        name=name,
        resource_type=resource_type,
        original_file_path=original_file_path,
    )


def _make_mock_credentials() -> MagicMock:
    """Return a credentials mock that satisfies httpx.Client construction."""
    credentials = MagicMock()
    credentials.api_key.get_secret_value.return_value = "test-api-key"
    credentials.account_id = _ACCOUNT_ID
    credentials.domain = _DOMAIN
    return credentials


def _make_executor(
    job_name_prefix: str = "test-orchestrator",
    timeout_seconds: int = 30,
    poll_frequency_seconds: int = 0,
    threads: int | None = None,
    defer_to_job_id: int | None = None,
) -> DbtCloudExecutor:
    return DbtCloudExecutor(
        credentials=_make_mock_credentials(),
        project_id=1,
        environment_id=2,
        job_name_prefix=job_name_prefix,
        timeout_seconds=timeout_seconds,
        poll_frequency_seconds=poll_frequency_seconds,
        threads=threads,
        defer_to_job_id=defer_to_job_id,
    )


@contextmanager
def _mock_ephemeral_job(
    job_id: int = 42,
    run_id: int = 100,
    final_status: int = DbtCloudJobRunStatus.SUCCESS.value,
    run_results: dict | None = None,
    delete_raises: bool = False,
):
    """Register all respx routes for a single ephemeral job execution.

    Yields the `MockRouter`. Assertions on `mock.calls` must be made
    *inside* this context — respx clears calls on exit.
    """
    with respx.mock as mock:
        mock.post(f"{_BASE}/jobs/").mock(
            return_value=httpx.Response(200, json={"data": {"id": job_id}})
        )
        mock.post(f"{_BASE}/jobs/{job_id}/run/").mock(
            return_value=httpx.Response(200, json={"data": {"id": run_id}})
        )
        mock.get(f"{_BASE}/runs/{run_id}/").mock(
            return_value=httpx.Response(200, json={"data": {"status": final_status}})
        )
        mock.get(f"{_BASE}/runs/{run_id}/artifacts/run_results.json").mock(
            return_value=httpx.Response(200, json=run_results or {"results": []})
        )
        mock.delete(f"{_BASE}/jobs/{job_id}/").mock(
            return_value=httpx.Response(500 if delete_raises else 200, json={})
        )
        yield mock


def _create_job_body(mock) -> dict:
    """Return the JSON body sent with the first (create-job) request."""
    return json.loads(mock.calls[0].request.content)


# =============================================================================
# _build_dbt_command
# =============================================================================


class TestBuildDbtCommand:
    def test_basic_run(self):
        ex = _make_executor()
        cmd = ex._build_dbt_command("run", ["path:models/my_model.sql"])
        assert cmd == "dbt run --select path:models/my_model.sql"

    def test_full_refresh_run(self):
        ex = _make_executor()
        cmd = ex._build_dbt_command("run", ["path:models/my.sql"], full_refresh=True)
        assert "--full-refresh" in cmd

    def test_full_refresh_ignored_for_test(self):
        ex = _make_executor()
        cmd = ex._build_dbt_command("test", ["some_test"], full_refresh=True)
        assert "--full-refresh" not in cmd

    def test_full_refresh_ignored_for_snapshot(self):
        ex = _make_executor()
        cmd = ex._build_dbt_command("snapshot", ["path:snap.sql"], full_refresh=True)
        assert "--full-refresh" not in cmd

    def test_threads_flag(self):
        ex = _make_executor(threads=4)
        cmd = ex._build_dbt_command("run", ["path:my.sql"])
        assert "--threads 4" in cmd

    def test_no_threads_by_default(self):
        ex = _make_executor()
        cmd = ex._build_dbt_command("run", ["path:my.sql"])
        assert "--threads" not in cmd

    def test_indirect_selection(self):
        ex = _make_executor()
        cmd = ex._build_dbt_command(
            "build", ["path:my.sql"], indirect_selection="empty"
        )
        assert "--indirect-selection empty" in cmd

    def test_multiple_selectors(self):
        ex = _make_executor()
        cmd = ex._build_dbt_command("build", ["sel1", "sel2", "sel3"])
        assert "--select sel1 sel2 sel3" in cmd

    def test_seed_with_full_refresh(self):
        ex = _make_executor()
        cmd = ex._build_dbt_command("seed", ["path:seeds/my.csv"], full_refresh=True)
        assert "--full-refresh" in cmd

    def test_target_flag(self):
        ex = _make_executor()
        cmd = ex._build_dbt_command("run", ["path:my.sql"], target="prod")
        assert "--target prod" in cmd

    def test_target_absent_by_default(self):
        ex = _make_executor()
        cmd = ex._build_dbt_command("run", ["path:my.sql"])
        assert "--target" not in cmd

    def test_extra_cli_args_appended(self):
        ex = _make_executor()
        cmd = ex._build_dbt_command(
            "run", ["path:my.sql"], extra_cli_args=["--store-failures", "--warn-error"]
        )
        assert "--store-failures" in cmd
        assert "--warn-error" in cmd

    def test_extra_cli_args_none_no_effect(self):
        ex = _make_executor()
        cmd = ex._build_dbt_command("run", ["path:my.sql"], extra_cli_args=None)
        assert cmd == "dbt run --select path:my.sql"

    def test_space_in_extra_cli_args_is_shell_quoted(self):
        """Values with spaces must be shell-quoted so Cloud parses them as one token."""
        ex = _make_executor()
        cmd = ex._build_dbt_command(
            "run",
            ["path:my.sql"],
            extra_cli_args=["--vars", "{'my_var': 'hello world'}"],
        )
        tokens = shlex.split(cmd)
        assert "--vars" in tokens
        assert "{'my_var': 'hello world'}" in tokens

    def test_build_with_all_flags(self):
        ex = _make_executor(threads=8)
        cmd = ex._build_dbt_command(
            "build",
            ["path:models/a.sql", "path:models/b.sql"],
            full_refresh=True,
            indirect_selection="empty",
            target="staging",
            extra_cli_args=["--store-failures"],
        )
        assert cmd.startswith("dbt build")
        assert "--threads 8" in cmd
        assert "--full-refresh" in cmd
        assert "--indirect-selection empty" in cmd
        assert "--target staging" in cmd
        assert "path:models/a.sql" in cmd
        assert "path:models/b.sql" in cmd
        assert "--store-failures" in cmd


# =============================================================================
# _parse_run_results
# =============================================================================


class TestParseRunResults:
    def test_none_input(self):
        assert _make_executor()._parse_run_results(None) is None

    def test_empty_dict(self):
        assert _make_executor()._parse_run_results({}) is None

    def test_missing_results_key(self):
        assert _make_executor()._parse_run_results({"metadata": {}}) is None

    def test_empty_results_list(self):
        assert _make_executor()._parse_run_results({"results": []}) is None

    def test_single_result(self):
        run_results = {
            "results": [
                {
                    "unique_id": "model.test.stg_users",
                    "status": "success",
                    "message": "SELECT 100",
                    "execution_time": 1.5,
                }
            ]
        }
        artifacts = _make_executor()._parse_run_results(run_results)
        assert artifacts == {
            "model.test.stg_users": {
                "status": "success",
                "message": "SELECT 100",
                "execution_time": 1.5,
            }
        }

    def test_multiple_results(self):
        run_results = {
            "results": [
                {
                    "unique_id": "model.test.a",
                    "status": "success",
                    "execution_time": 1.0,
                },
                {"unique_id": "model.test.b", "status": "error", "execution_time": 0.5},
            ]
        }
        artifacts = _make_executor()._parse_run_results(run_results)
        assert len(artifacts) == 2
        assert artifacts["model.test.a"]["status"] == "success"
        assert artifacts["model.test.b"]["status"] == "error"

    def test_result_without_unique_id_skipped(self):
        run_results = {
            "results": [
                {"status": "success"},  # no unique_id
                {"unique_id": "model.test.a", "status": "success"},
            ]
        }
        artifacts = _make_executor()._parse_run_results(run_results)
        assert list(artifacts.keys()) == ["model.test.a"]


# =============================================================================
# execute_node
# =============================================================================


class TestExecuteNode:
    def test_success(self):
        run_results = {
            "results": [
                {
                    "unique_id": "model.test.my_model",
                    "status": "success",
                    "message": "SELECT 50",
                    "execution_time": 2.0,
                }
            ]
        }
        ex = _make_executor()
        with _mock_ephemeral_job(run_results=run_results):
            result = ex.execute_node(_make_node(), "run")

        assert result.success is True
        assert "model.test.my_model" in result.node_ids
        assert result.error is None
        assert result.artifacts["model.test.my_model"]["status"] == "success"

    def test_success_creates_and_deletes_job(self):
        ex = _make_executor()
        with _mock_ephemeral_job(job_id=99) as mock:
            ex.execute_node(_make_node(), "run")
            # First request: POST /jobs/ — Last request: DELETE /jobs/99/
            assert mock.calls[0].request.method == "POST"
            assert mock.calls[0].request.url.path.endswith("/jobs/")
            assert mock.calls[-1].request.method == "DELETE"
            assert mock.calls[-1].request.url.path.endswith("/jobs/99/")

    def test_failure_still_deletes_job(self):
        ex = _make_executor()
        with _mock_ephemeral_job(
            job_id=55, final_status=DbtCloudJobRunStatus.FAILED.value
        ) as mock:
            result = ex.execute_node(_make_node(), "run")
            assert mock.calls[-1].request.method == "DELETE"
            assert mock.calls[-1].request.url.path.endswith("/jobs/55/")

        assert result.success is False
        assert result.error is not None

    def test_failure_result(self):
        ex = _make_executor()
        with _mock_ephemeral_job(
            final_status=DbtCloudJobRunStatus.FAILED.value,
            run_results={"results": []},
        ):
            result = ex.execute_node(_make_node(), "run")

        assert result.success is False
        assert isinstance(result.error, RuntimeError)
        assert "FAILED" in str(result.error)

    def test_cancelled_run_is_failure(self):
        ex = _make_executor()
        with _mock_ephemeral_job(final_status=DbtCloudJobRunStatus.CANCELLED.value):
            result = ex.execute_node(_make_node(), "run")

        assert result.success is False
        assert "CANCELLED" in str(result.error)

    def test_correct_command_built(self):
        ex = _make_executor()
        node = _make_node(original_file_path="models/staging/stg_users.sql")

        with _mock_ephemeral_job() as mock:
            ex.execute_node(node, "run")
            steps = _create_job_body(mock)["execute_steps"]

        assert len(steps) == 1
        assert steps[0] == "dbt run --select path:models/staging/stg_users.sql"

    def test_full_refresh_flag_in_command(self):
        ex = _make_executor()
        with _mock_ephemeral_job() as mock:
            ex.execute_node(_make_node(), "run", full_refresh=True)
            step = _create_job_body(mock)["execute_steps"][0]

        assert "--full-refresh" in step

    def test_seed_command(self):
        ex = _make_executor()
        node = _make_node(
            unique_id="seed.test.customers",
            name="customers",
            resource_type=NodeType.Seed,
            original_file_path="seeds/customers.csv",
        )
        with _mock_ephemeral_job() as mock:
            ex.execute_node(node, "seed")
            step = _create_job_body(mock)["execute_steps"][0]

        assert step.startswith("dbt seed")

    def test_job_name_contains_command_and_node_name(self):
        ex = _make_executor(job_name_prefix="my-prefix")
        with _mock_ephemeral_job() as mock:
            ex.execute_node(_make_node(name="stg_users"), "run")
            name = _create_job_body(mock)["name"]

        assert "my-prefix" in name
        assert "run" in name
        assert "stg_users" in name

    def test_timeout_raises_error_when_run_stays_non_terminal(self):
        ex = _make_executor(timeout_seconds=0, poll_frequency_seconds=0)
        with respx.mock:
            respx.post(f"{_BASE}/jobs/").mock(
                return_value=httpx.Response(200, json={"data": {"id": 42}})
            )
            respx.post(f"{_BASE}/jobs/42/run/").mock(
                return_value=httpx.Response(200, json={"data": {"id": 100}})
            )
            respx.get(f"{_BASE}/runs/100/").mock(
                return_value=httpx.Response(
                    200, json={"data": {"status": DbtCloudJobRunStatus.RUNNING.value}}
                )
            )
            respx.delete(f"{_BASE}/jobs/42/").mock(
                return_value=httpx.Response(200, json={})
            )
            result = ex.execute_node(_make_node(), "run")

        assert result.success is False
        assert "did not complete within" in str(result.error)

    def test_cleanup_failure_does_not_mask_run_error(self):
        ex = _make_executor()
        with _mock_ephemeral_job(
            final_status=DbtCloudJobRunStatus.FAILED.value, delete_raises=True
        ):
            result = ex.execute_node(_make_node(), "run")

        assert result.success is False
        assert "FAILED" in str(result.error)

    def test_exception_during_trigger_cleans_up(self):
        ex = _make_executor()
        with respx.mock as mock:
            respx.post(f"{_BASE}/jobs/").mock(
                return_value=httpx.Response(200, json={"data": {"id": 42}})
            )
            respx.post(f"{_BASE}/jobs/42/run/").mock(
                return_value=httpx.Response(500, text="network error")
            )
            respx.delete(f"{_BASE}/jobs/42/").mock(
                return_value=httpx.Response(200, json={})
            )
            result = ex.execute_node(_make_node(), "run")
            # Job was created so cleanup DELETE must have been called.
            assert mock.calls[-1].request.method == "DELETE"

        assert result.success is False

    def test_exception_during_create_job_no_cleanup(self):
        """If create_job fails, job_id is never set, so DELETE is never called."""
        ex = _make_executor()
        with respx.mock as mock:
            # Only register POST /jobs/ with 500.
            # Strict mode means any extra (DELETE) call would also raise,
            # giving automatic verification that cleanup was skipped.
            respx.post(f"{_BASE}/jobs/").mock(
                return_value=httpx.Response(500, text="error")
            )
            result = ex.execute_node(_make_node(), "run")
            assert len(mock.calls) == 1

        assert result.success is False

    def test_node_name_truncated_in_job_name(self):
        ex = _make_executor()
        with _mock_ephemeral_job() as mock:
            ex.execute_node(_make_node(name="a" * 100), "run")
            name = _create_job_body(mock)["name"]

        assert len(name) <= 100

    def test_target_forwarded_to_command(self):
        ex = _make_executor()
        with _mock_ephemeral_job() as mock:
            ex.execute_node(_make_node(), "run", target="prod")
            step = _create_job_body(mock)["execute_steps"][0]

        assert "--target prod" in step

    def test_extra_cli_args_forwarded_to_command(self):
        ex = _make_executor()
        with _mock_ephemeral_job() as mock:
            ex.execute_node(_make_node(), "run", extra_cli_args=["--store-failures"])
            step = _create_job_body(mock)["execute_steps"][0]

        assert "--store-failures" in step


# =============================================================================
# execute_wave
# =============================================================================


class TestExecuteWave:
    def test_empty_wave_raises(self):
        with pytest.raises(ValueError, match="empty wave"):
            _make_executor().execute_wave([])

    def test_success(self):
        run_results = {
            "results": [
                {
                    "unique_id": "model.test.a",
                    "status": "success",
                    "execution_time": 1.0,
                },
                {
                    "unique_id": "model.test.b",
                    "status": "success",
                    "execution_time": 2.0,
                },
            ]
        }
        ex = _make_executor()
        nodes = [
            _make_node("model.test.a", "a", original_file_path="models/a.sql"),
            _make_node("model.test.b", "b", original_file_path="models/b.sql"),
        ]
        with _mock_ephemeral_job(run_results=run_results):
            result = ex.execute_wave(nodes)

        assert result.success is True
        assert "model.test.a" in result.node_ids
        assert "model.test.b" in result.node_ids

    def test_uses_dbt_build(self):
        ex = _make_executor()
        with _mock_ephemeral_job() as mock:
            ex.execute_wave(
                [_make_node("model.test.a", "a", original_file_path="models/a.sql")]
            )
            step = _create_job_body(mock)["execute_steps"][0]

        assert step.startswith("dbt build")

    def test_all_selectors_included(self):
        ex = _make_executor()
        nodes = [
            _make_node("model.test.a", "a", original_file_path="models/a.sql"),
            _make_node("model.test.b", "b", original_file_path="models/b.sql"),
            _make_node("model.test.c", "c", original_file_path="models/c.sql"),
        ]
        with _mock_ephemeral_job() as mock:
            ex.execute_wave(nodes)
            cmd = _create_job_body(mock)["execute_steps"][0]

        assert "path:models/a.sql" in cmd
        assert "path:models/b.sql" in cmd
        assert "path:models/c.sql" in cmd

    def test_indirect_selection_passed(self):
        ex = _make_executor()
        with _mock_ephemeral_job() as mock:
            ex.execute_wave(
                [_make_node("model.test.a", "a", original_file_path="models/a.sql")],
                indirect_selection="empty",
            )
            step = _create_job_body(mock)["execute_steps"][0]

        assert "--indirect-selection empty" in step

    def test_failure_deletes_job(self):
        ex = _make_executor()
        with _mock_ephemeral_job(
            job_id=77, final_status=DbtCloudJobRunStatus.FAILED.value
        ) as mock:
            result = ex.execute_wave([_make_node()])
            assert mock.calls[-1].request.method == "DELETE"
            assert mock.calls[-1].request.url.path.endswith("/jobs/77/")

        assert result.success is False

    def test_full_refresh_flag(self):
        ex = _make_executor()
        with _mock_ephemeral_job() as mock:
            ex.execute_wave(
                [_make_node("model.test.a", "a", original_file_path="models/a.sql")],
                full_refresh=True,
            )
            step = _create_job_body(mock)["execute_steps"][0]

        assert "--full-refresh" in step

    def test_target_forwarded_to_command(self):
        ex = _make_executor()
        with _mock_ephemeral_job() as mock:
            ex.execute_wave(
                [_make_node("model.test.a", "a", original_file_path="models/a.sql")],
                target="prod",
            )
            step = _create_job_body(mock)["execute_steps"][0]

        assert "--target prod" in step

    def test_extra_cli_args_forwarded_to_command(self):
        ex = _make_executor()
        with _mock_ephemeral_job() as mock:
            ex.execute_wave(
                [_make_node("model.test.a", "a", original_file_path="models/a.sql")],
                extra_cli_args=["--store-failures"],
            )
            step = _create_job_body(mock)["execute_steps"][0]

        assert "--store-failures" in step


# =============================================================================
# fetch_manifest_from_job
# =============================================================================


class TestFetchManifestFromJob:
    def test_fetches_manifest(self):
        manifest_data = {"metadata": {"dbt_version": "1.7.0"}, "nodes": {}}
        ex = _make_executor()
        with respx.mock:
            respx.get(f"{_BASE}/jobs/111/artifacts/manifest.json").mock(
                return_value=httpx.Response(200, json=manifest_data)
            )
            result = ex.fetch_manifest_from_job(job_id=111)

        assert result == manifest_data

    def test_correct_endpoint_called(self):
        ex = _make_executor()
        with respx.mock as mock:
            respx.get(f"{_BASE}/jobs/999/artifacts/manifest.json").mock(
                return_value=httpx.Response(200, json={"nodes": {}})
            )
            ex.fetch_manifest_from_job(job_id=999)
            call = mock.calls[0]
            assert call.request.method == "GET"
            assert "/jobs/999/artifacts/manifest.json" in str(call.request.url)


# =============================================================================
# generate_manifest
# =============================================================================


@contextmanager
def _mock_generate_manifest(
    job_id: int = 50,
    run_id: int = 500,
    final_status: int = DbtCloudJobRunStatus.SUCCESS.value,
    manifest_data: dict | None = None,
):
    """Register respx routes for a generate_manifest (dbt compile) call.

    Yields the `MockRouter`. Assertions on `mock.calls` must be made inside.
    """
    with respx.mock as mock:
        mock.post(f"{_BASE}/jobs/").mock(
            return_value=httpx.Response(200, json={"data": {"id": job_id}})
        )
        mock.post(f"{_BASE}/jobs/{job_id}/run/").mock(
            return_value=httpx.Response(200, json={"data": {"id": run_id}})
        )
        mock.get(f"{_BASE}/runs/{run_id}/").mock(
            return_value=httpx.Response(200, json={"data": {"status": final_status}})
        )
        if final_status == DbtCloudJobRunStatus.SUCCESS.value:
            mock.get(f"{_BASE}/runs/{run_id}/artifacts/manifest.json").mock(
                return_value=httpx.Response(
                    200, json=manifest_data or {"nodes": {}, "sources": {}}
                )
            )
        mock.delete(f"{_BASE}/jobs/{job_id}/").mock(
            return_value=httpx.Response(200, json={})
        )
        yield mock


class TestGenerateManifest:
    def test_success_returns_manifest(self):
        manifest_data = {"nodes": {}, "sources": {}}
        ex = _make_executor()
        with _mock_generate_manifest(manifest_data=manifest_data):
            result = ex.generate_manifest()

        assert result == manifest_data

    def test_uses_dbt_compile_step(self):
        ex = _make_executor()
        with _mock_generate_manifest() as mock:
            ex.generate_manifest()
            assert _create_job_body(mock)["execute_steps"] == ["dbt compile"]

    def test_compile_job_deleted_on_success(self):
        ex = _make_executor()
        with _mock_generate_manifest(job_id=60) as mock:
            ex.generate_manifest()
            assert mock.calls[-1].request.method == "DELETE"
            assert mock.calls[-1].request.url.path.endswith("/jobs/60/")

    def test_compile_job_deleted_on_failure(self):
        ex = _make_executor()
        with _mock_generate_manifest(
            job_id=70, final_status=DbtCloudJobRunStatus.FAILED.value
        ) as mock:
            with pytest.raises(RuntimeError, match="FAILED"):
                ex.generate_manifest()
            assert mock.calls[-1].request.method == "DELETE"
            assert mock.calls[-1].request.url.path.endswith("/jobs/70/")

    def test_job_name_contains_compile_and_prefix(self):
        ex = _make_executor(job_name_prefix="my-prefix")
        with _mock_generate_manifest() as mock:
            ex.generate_manifest()
            name = _create_job_body(mock)["name"]

        assert "my-prefix" in name
        assert "compile" in name


# =============================================================================
# resolve_manifest_path
# =============================================================================


class TestResolveManifestPath:
    def test_uses_defer_to_job_id(self):
        manifest_data = {"nodes": {}, "sources": {}}
        ex = _make_executor(defer_to_job_id=111)
        with respx.mock as mock:
            respx.get(f"{_BASE}/jobs/111/artifacts/manifest.json").mock(
                return_value=httpx.Response(200, json=manifest_data)
            )
            path = ex.resolve_manifest_path()
            assert "/jobs/111/" in str(mock.calls[0].request.url)

        assert path.exists()
        assert path.name == "manifest.json"
        with open(path) as f:
            assert json.load(f) == manifest_data

    def test_generates_manifest_when_no_defer(self):
        manifest_data = {"nodes": {}, "sources": {}}
        ex = _make_executor()
        with _mock_generate_manifest(manifest_data=manifest_data):
            path = ex.resolve_manifest_path()

        assert path.exists()
        assert path.name == "manifest.json"
        with open(path) as f:
            assert json.load(f) == manifest_data

    def test_isolated_target_dir_per_executor(self):
        """Each executor instance gets its own temp directory."""
        manifest_data = {"nodes": {}}
        ex1 = _make_executor(defer_to_job_id=1)
        ex2 = _make_executor(defer_to_job_id=1)

        with respx.mock:
            respx.get(f"{_BASE}/jobs/1/artifacts/manifest.json").mock(
                return_value=httpx.Response(200, json=manifest_data)
            )
            path_a = ex1.resolve_manifest_path()
            path_b = ex2.resolve_manifest_path()

        assert path_a.parent != path_b.parent

    def test_temp_dir_cleaned_up_on_executor_gc(self):
        manifest_data = {"nodes": {}}
        ex = _make_executor(defer_to_job_id=1)
        with respx.mock:
            respx.get(f"{_BASE}/jobs/1/artifacts/manifest.json").mock(
                return_value=httpx.Response(200, json=manifest_data)
            )
            path = ex.resolve_manifest_path()

        assert path.exists()
        ex._manifest_temp_dir.cleanup()
        assert not path.exists()

    def test_returns_absolute_path_object(self):
        manifest_data = {"nodes": {}}
        ex = _make_executor(defer_to_job_id=1)
        with respx.mock:
            respx.get(f"{_BASE}/jobs/1/artifacts/manifest.json").mock(
                return_value=httpx.Response(200, json=manifest_data)
            )
            path = ex.resolve_manifest_path()

        assert isinstance(path, Path)
        assert path.is_absolute()
        assert path.name == "manifest.json"


# =============================================================================
# Orchestrator integration: manifest from DbtCloudExecutor
# =============================================================================


class TestOrchestratorManifestResolution:
    def test_orchestrator_uses_executor_resolve_manifest_path(self, tmp_path):
        from prefect_dbt.core._orchestrator import PrefectDbtOrchestrator

        manifest_path = tmp_path / "manifest.json"
        manifest_data = {
            "nodes": {
                "model.test.my_model": {
                    "name": "my_model",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                }
            },
            "sources": {},
            "metadata": {"adapter_type": "postgres"},
        }
        manifest_path.write_text(json.dumps(manifest_data))

        mock_executor = MagicMock()
        mock_executor.resolve_manifest_path.return_value = manifest_path
        mock_executor.execute_wave.return_value = ExecutionResult(
            success=True, node_ids=["model.test.my_model"]
        )

        orch = PrefectDbtOrchestrator(executor=mock_executor)
        resolved = orch._resolve_manifest_path()

        assert resolved == manifest_path
        mock_executor.resolve_manifest_path.assert_called_once()

    def test_settings_target_path_synced_after_executor_manifest(self, tmp_path):
        from prefect_dbt.core._orchestrator import PrefectDbtOrchestrator

        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps({"nodes": {}, "sources": {}}))

        mock_executor = MagicMock()
        mock_executor.resolve_manifest_path.return_value = manifest_path

        orch = PrefectDbtOrchestrator(executor=mock_executor)
        original_target_path = orch._settings.target_path

        orch._resolve_manifest_path()

        assert orch._settings.target_path == manifest_path.parent
        assert orch._settings.target_path != original_target_path

    def test_executor_manifest_path_persisted_for_target_resolution(self, tmp_path):
        from prefect_dbt.core._orchestrator import PrefectDbtOrchestrator

        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps({"nodes": {}, "sources": {}}))

        mock_executor = MagicMock()
        mock_executor.resolve_manifest_path.return_value = manifest_path

        orch = PrefectDbtOrchestrator(executor=mock_executor)
        assert orch._manifest_path is None

        orch._resolve_manifest_path()

        assert orch._manifest_path == manifest_path
        assert orch._resolve_target_path() == manifest_path.parent
        assert orch._resolve_manifest_path() == manifest_path
        assert mock_executor.resolve_manifest_path.call_count == 1

    def test_orchestrator_skips_executor_when_manifest_path_provided(self, tmp_path):
        from prefect_dbt.core._orchestrator import PrefectDbtOrchestrator

        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps({"nodes": {}, "sources": {}}))

        mock_executor = MagicMock()
        mock_executor.resolve_manifest_path.return_value = Path("/should/not/be/called")

        orch = PrefectDbtOrchestrator(
            executor=mock_executor, manifest_path=manifest_path
        )
        resolved = orch._resolve_manifest_path()

        assert resolved == manifest_path
        mock_executor.resolve_manifest_path.assert_not_called()


# =============================================================================
# DbtExecutor protocol compliance
# =============================================================================


class TestProtocolCompliance:
    def test_implements_dbt_executor_protocol(self):
        from prefect_dbt.core._executor import DbtExecutor

        ex = DbtCloudExecutor(
            credentials=_make_mock_credentials(), project_id=1, environment_id=2
        )
        assert isinstance(ex, DbtExecutor)

    def test_has_execute_node(self):
        assert callable(getattr(_make_executor(), "execute_node", None))

    def test_has_execute_wave(self):
        assert callable(getattr(_make_executor(), "execute_wave", None))

    def test_has_resolve_manifest_path(self):
        assert callable(getattr(_make_executor(), "resolve_manifest_path", None))
