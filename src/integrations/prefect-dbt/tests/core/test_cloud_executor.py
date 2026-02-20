"""Tests for DbtCloudExecutor."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from dbt.artifacts.resources.types import NodeType
from prefect_dbt.cloud import DbtCloudExecutor
from prefect_dbt.cloud.runs import DbtCloudJobRunStatus
from prefect_dbt.core._executor import ExecutionResult
from prefect_dbt.core._manifest import DbtNode

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


def _make_response(data: dict) -> MagicMock:
    """Create a mock HTTP response whose .json() returns *data*."""
    resp = MagicMock()
    resp.json.return_value = data
    return resp


def _configure_context_manager(mock_client: AsyncMock) -> AsyncMock:
    """Configure *mock_client* so that ``async with mock_client as c:``
    yields *mock_client* as ``c`` (mirroring the real client's ``__aenter__``
    which returns ``self``)."""
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


def _make_mock_credentials(mock_client: AsyncMock) -> MagicMock:
    """Return a credentials mock that yields *mock_client* from
    get_administrative_client()."""
    credentials = MagicMock()
    credentials.get_administrative_client.return_value = mock_client
    return credentials


def _make_client_mock(
    job_id: int = 42,
    run_id: int = 100,
    final_status: int = DbtCloudJobRunStatus.SUCCESS.value,
    run_results: dict | None = None,
) -> AsyncMock:
    """Build a fully-wired AsyncMock for DbtCloudAdministrativeClient.

    Args:
        job_id: ID returned by create_job.
        run_id: ID returned by trigger_job_run.
        final_status: Status code returned by get_run (immediately terminal).
        run_results: Content returned by get_run_artifact("run_results.json").
    """
    client = AsyncMock()
    # Make ``async with client as c:`` yield the same mock (like the real
    # DbtCloudAdministrativeClient.__aenter__ which returns ``self``).
    _configure_context_manager(client)

    # create_job
    client.create_job.return_value = _make_response({"data": {"id": job_id}})

    # trigger_job_run
    client.trigger_job_run.return_value = _make_response({"data": {"id": run_id}})

    # get_run — immediately terminal
    client.get_run.return_value = _make_response({"data": {"status": final_status}})

    # get_run_artifact (run_results.json)
    if run_results is not None:
        client.get_run_artifact.return_value = _make_response(run_results)
    else:
        client.get_run_artifact.return_value = _make_response({"results": []})

    # delete_job
    client.delete_job.return_value = _make_response({})

    return client


def _make_executor(
    mock_client: AsyncMock,
    job_name_prefix: str = "test-orchestrator",
    timeout_seconds: int = 30,
    poll_frequency_seconds: int = 0,
    threads: int | None = None,
    defer_to_job_id: int | None = None,
) -> DbtCloudExecutor:
    credentials = _make_mock_credentials(mock_client)
    return DbtCloudExecutor(
        credentials=credentials,
        project_id=1,
        environment_id=2,
        job_name_prefix=job_name_prefix,
        timeout_seconds=timeout_seconds,
        poll_frequency_seconds=poll_frequency_seconds,
        threads=threads,
        defer_to_job_id=defer_to_job_id,
    )


# =============================================================================
# _build_dbt_command
# =============================================================================


class TestBuildDbtCommand:
    def test_basic_run(self):
        ex = _make_executor(AsyncMock())
        cmd = ex._build_dbt_command("run", ["path:models/my_model.sql"])
        assert cmd == "dbt run --select path:models/my_model.sql"

    def test_full_refresh_run(self):
        ex = _make_executor(AsyncMock())
        cmd = ex._build_dbt_command("run", ["path:models/my.sql"], full_refresh=True)
        assert "--full-refresh" in cmd

    def test_full_refresh_ignored_for_test(self):
        ex = _make_executor(AsyncMock())
        cmd = ex._build_dbt_command("test", ["some_test"], full_refresh=True)
        assert "--full-refresh" not in cmd

    def test_full_refresh_ignored_for_snapshot(self):
        ex = _make_executor(AsyncMock())
        cmd = ex._build_dbt_command("snapshot", ["path:snap.sql"], full_refresh=True)
        assert "--full-refresh" not in cmd

    def test_threads_flag(self):
        ex = _make_executor(AsyncMock(), threads=4)
        cmd = ex._build_dbt_command("run", ["path:my.sql"])
        assert "--threads 4" in cmd

    def test_no_threads_by_default(self):
        ex = _make_executor(AsyncMock())
        cmd = ex._build_dbt_command("run", ["path:my.sql"])
        assert "--threads" not in cmd

    def test_indirect_selection(self):
        ex = _make_executor(AsyncMock())
        cmd = ex._build_dbt_command(
            "build", ["path:my.sql"], indirect_selection="empty"
        )
        assert "--indirect-selection empty" in cmd

    def test_multiple_selectors(self):
        ex = _make_executor(AsyncMock())
        cmd = ex._build_dbt_command("build", ["sel1", "sel2", "sel3"])
        assert "--select sel1 sel2 sel3" in cmd

    def test_seed_with_full_refresh(self):
        ex = _make_executor(AsyncMock())
        cmd = ex._build_dbt_command("seed", ["path:seeds/my.csv"], full_refresh=True)
        assert "--full-refresh" in cmd

    def test_build_with_all_flags(self):
        ex = _make_executor(AsyncMock(), threads=8)
        cmd = ex._build_dbt_command(
            "build",
            ["path:models/a.sql", "path:models/b.sql"],
            full_refresh=True,
            indirect_selection="empty",
        )
        assert cmd.startswith("dbt build")
        assert "--threads 8" in cmd
        assert "--full-refresh" in cmd
        assert "--indirect-selection empty" in cmd
        assert "path:models/a.sql" in cmd
        assert "path:models/b.sql" in cmd


# =============================================================================
# _parse_run_results
# =============================================================================


class TestParseRunResults:
    def test_none_input(self):
        ex = _make_executor(AsyncMock())
        assert ex._parse_run_results(None) is None

    def test_empty_dict(self):
        ex = _make_executor(AsyncMock())
        assert ex._parse_run_results({}) is None

    def test_missing_results_key(self):
        ex = _make_executor(AsyncMock())
        assert ex._parse_run_results({"metadata": {}}) is None

    def test_empty_results_list(self):
        ex = _make_executor(AsyncMock())
        assert ex._parse_run_results({"results": []}) is None

    def test_single_result(self):
        ex = _make_executor(AsyncMock())
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
        artifacts = ex._parse_run_results(run_results)
        assert artifacts == {
            "model.test.stg_users": {
                "status": "success",
                "message": "SELECT 100",
                "execution_time": 1.5,
            }
        }

    def test_multiple_results(self):
        ex = _make_executor(AsyncMock())
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
        artifacts = ex._parse_run_results(run_results)
        assert len(artifacts) == 2
        assert artifacts["model.test.a"]["status"] == "success"
        assert artifacts["model.test.b"]["status"] == "error"

    def test_result_without_unique_id_skipped(self):
        ex = _make_executor(AsyncMock())
        run_results = {
            "results": [
                {"status": "success"},  # no unique_id
                {"unique_id": "model.test.a", "status": "success"},
            ]
        }
        artifacts = ex._parse_run_results(run_results)
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
        mock_client = _make_client_mock(job_id=10, run_id=200, run_results=run_results)
        ex = _make_executor(mock_client)
        node = _make_node()

        result = ex.execute_node(node, "run")

        assert result.success is True
        assert "model.test.my_model" in result.node_ids
        assert result.error is None
        assert result.artifacts is not None
        assert result.artifacts["model.test.my_model"]["status"] == "success"

    def test_success_creates_and_deletes_job(self):
        mock_client = _make_client_mock(job_id=99, run_id=300)
        ex = _make_executor(mock_client)
        node = _make_node()

        ex.execute_node(node, "run")

        mock_client.create_job.assert_called_once()
        mock_client.delete_job.assert_called_once_with(job_id=99)

    def test_failure_still_deletes_job(self):
        mock_client = _make_client_mock(
            job_id=55, run_id=400, final_status=DbtCloudJobRunStatus.FAILED.value
        )
        ex = _make_executor(mock_client)
        node = _make_node()

        result = ex.execute_node(node, "run")

        assert result.success is False
        assert result.error is not None
        mock_client.delete_job.assert_called_once_with(job_id=55)

    def test_failure_result(self):
        mock_client = _make_client_mock(
            final_status=DbtCloudJobRunStatus.FAILED.value,
            run_results={"results": []},
        )
        ex = _make_executor(mock_client)
        node = _make_node()

        result = ex.execute_node(node, "run")

        assert result.success is False
        assert isinstance(result.error, RuntimeError)
        assert "FAILED" in str(result.error)

    def test_cancelled_run_is_failure(self):
        mock_client = _make_client_mock(
            final_status=DbtCloudJobRunStatus.CANCELLED.value
        )
        ex = _make_executor(mock_client)
        result = ex.execute_node(_make_node(), "run")
        assert result.success is False
        assert "CANCELLED" in str(result.error)

    def test_correct_command_built(self):
        mock_client = _make_client_mock()
        ex = _make_executor(mock_client)
        node = _make_node(original_file_path="models/staging/stg_users.sql")

        ex.execute_node(node, "run")

        create_call = mock_client.create_job.call_args
        steps = create_call.kwargs.get("execute_steps") or create_call.args[3]
        assert len(steps) == 1
        assert steps[0] == "dbt run --select path:models/staging/stg_users.sql"

    def test_full_refresh_flag_in_command(self):
        mock_client = _make_client_mock()
        ex = _make_executor(mock_client)
        node = _make_node()

        ex.execute_node(node, "run", full_refresh=True)

        create_call = mock_client.create_job.call_args
        steps = create_call.kwargs.get("execute_steps") or create_call.args[3]
        assert "--full-refresh" in steps[0]

    def test_seed_command(self):
        mock_client = _make_client_mock()
        ex = _make_executor(mock_client)
        node = _make_node(
            unique_id="seed.test.customers",
            name="customers",
            resource_type=NodeType.Seed,
            original_file_path="seeds/customers.csv",
        )

        ex.execute_node(node, "seed")

        create_call = mock_client.create_job.call_args
        steps = create_call.kwargs.get("execute_steps") or create_call.args[3]
        assert steps[0].startswith("dbt seed")

    def test_job_name_contains_command_and_node_name(self):
        mock_client = _make_client_mock()
        ex = _make_executor(mock_client, job_name_prefix="my-prefix")
        node = _make_node(name="stg_users")

        ex.execute_node(node, "run")

        create_call = mock_client.create_job.call_args
        name = create_call.kwargs.get("name") or create_call.args[2]
        assert "my-prefix" in name
        assert "run" in name
        assert "stg_users" in name

    def test_timeout_raises_error_when_run_stays_non_terminal(self):
        """A run that never reaches a terminal status raises TimeoutError
        regardless of poll_frequency_seconds (including zero)."""
        mock_client = _make_client_mock(
            final_status=DbtCloudJobRunStatus.RUNNING.value,
        )
        # timeout_seconds=0: the first non-terminal poll exhausts the budget
        ex = _make_executor(mock_client, timeout_seconds=0, poll_frequency_seconds=0)

        result = ex.execute_node(_make_node(), "run")

        assert result.success is False
        assert "did not complete within" in str(result.error)

    def test_cleanup_failure_does_not_mask_run_error(self):
        mock_client = _make_client_mock(final_status=DbtCloudJobRunStatus.FAILED.value)
        mock_client.delete_job.side_effect = RuntimeError("delete failed")
        ex = _make_executor(mock_client)

        # Should still return without raising despite cleanup failure
        result = ex.execute_node(_make_node(), "run")
        assert result.success is False
        assert "FAILED" in str(result.error)

    def test_exception_during_trigger_cleans_up(self):
        mock_client = _make_client_mock()
        mock_client.trigger_job_run.side_effect = RuntimeError("network error")
        ex = _make_executor(mock_client)

        result = ex.execute_node(_make_node(), "run")

        assert result.success is False
        # Job was created before trigger failed, so cleanup should run
        mock_client.delete_job.assert_called_once()

    def test_exception_during_create_job_no_cleanup(self):
        mock_client = _make_client_mock()
        mock_client.create_job.side_effect = RuntimeError("create failed")
        ex = _make_executor(mock_client)

        result = ex.execute_node(_make_node(), "run")

        assert result.success is False
        # Job was never created, so no cleanup
        mock_client.delete_job.assert_not_called()

    def test_node_name_truncated_in_job_name(self):
        mock_client = _make_client_mock()
        ex = _make_executor(mock_client)
        node = _make_node(name="a" * 100)

        ex.execute_node(node, "run")

        create_call = mock_client.create_job.call_args
        name = create_call.kwargs.get("name") or create_call.args[2]
        # Job name should not be excessively long
        assert len(name) <= 100


# =============================================================================
# execute_wave
# =============================================================================


class TestExecuteWave:
    def test_empty_wave_raises(self):
        ex = _make_executor(AsyncMock())
        with pytest.raises(ValueError, match="empty wave"):
            ex.execute_wave([])

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
        mock_client = _make_client_mock(run_results=run_results)
        ex = _make_executor(mock_client)
        nodes = [
            _make_node("model.test.a", "a", original_file_path="models/a.sql"),
            _make_node("model.test.b", "b", original_file_path="models/b.sql"),
        ]

        result = ex.execute_wave(nodes)

        assert result.success is True
        assert "model.test.a" in result.node_ids
        assert "model.test.b" in result.node_ids

    def test_uses_dbt_build(self):
        mock_client = _make_client_mock()
        ex = _make_executor(mock_client)
        nodes = [
            _make_node("model.test.a", "a", original_file_path="models/a.sql"),
        ]

        ex.execute_wave(nodes)

        create_call = mock_client.create_job.call_args
        steps = create_call.kwargs.get("execute_steps") or create_call.args[3]
        assert steps[0].startswith("dbt build")

    def test_all_selectors_included(self):
        mock_client = _make_client_mock()
        ex = _make_executor(mock_client)
        nodes = [
            _make_node("model.test.a", "a", original_file_path="models/a.sql"),
            _make_node("model.test.b", "b", original_file_path="models/b.sql"),
            _make_node("model.test.c", "c", original_file_path="models/c.sql"),
        ]

        ex.execute_wave(nodes)

        create_call = mock_client.create_job.call_args
        steps = create_call.kwargs.get("execute_steps") or create_call.args[3]
        cmd = steps[0]
        assert "path:models/a.sql" in cmd
        assert "path:models/b.sql" in cmd
        assert "path:models/c.sql" in cmd

    def test_indirect_selection_passed(self):
        mock_client = _make_client_mock()
        ex = _make_executor(mock_client)
        nodes = [_make_node("model.test.a", "a", original_file_path="models/a.sql")]

        ex.execute_wave(nodes, indirect_selection="empty")

        create_call = mock_client.create_job.call_args
        steps = create_call.kwargs.get("execute_steps") or create_call.args[3]
        assert "--indirect-selection empty" in steps[0]

    def test_failure_deletes_job(self):
        mock_client = _make_client_mock(
            job_id=77, final_status=DbtCloudJobRunStatus.FAILED.value
        )
        ex = _make_executor(mock_client)
        nodes = [_make_node()]

        result = ex.execute_wave(nodes)

        assert result.success is False
        mock_client.delete_job.assert_called_once_with(job_id=77)

    def test_full_refresh_flag(self):
        mock_client = _make_client_mock()
        ex = _make_executor(mock_client)
        nodes = [_make_node("model.test.a", "a", original_file_path="models/a.sql")]

        ex.execute_wave(nodes, full_refresh=True)

        create_call = mock_client.create_job.call_args
        steps = create_call.kwargs.get("execute_steps") or create_call.args[3]
        assert "--full-refresh" in steps[0]


# =============================================================================
# fetch_manifest_from_job
# =============================================================================


class TestFetchManifestFromJob:
    def test_fetches_manifest(self):
        manifest_data = {"metadata": {"dbt_version": "1.7.0"}, "nodes": {}}
        mock_client = _configure_context_manager(AsyncMock())
        mock_client.get_job_artifact.return_value = _make_response(manifest_data)
        credentials = _make_mock_credentials(mock_client)

        ex = DbtCloudExecutor(
            credentials=credentials,
            project_id=1,
            environment_id=2,
        )

        result = ex.fetch_manifest_from_job(job_id=111)

        assert result == manifest_data
        mock_client.get_job_artifact.assert_called_once_with(
            job_id=111, path="manifest.json"
        )

    def test_correct_job_id_used(self):
        mock_client = _configure_context_manager(AsyncMock())
        mock_client.get_job_artifact.return_value = _make_response({"nodes": {}})
        credentials = _make_mock_credentials(mock_client)
        ex = DbtCloudExecutor(credentials=credentials, project_id=1, environment_id=2)

        ex.fetch_manifest_from_job(job_id=999)

        mock_client.get_job_artifact.assert_called_once_with(
            job_id=999, path="manifest.json"
        )


# =============================================================================
# generate_manifest
# =============================================================================


class TestGenerateManifest:
    def test_success_returns_manifest(self):
        manifest_data = {"nodes": {}, "sources": {}}
        mock_client = _configure_context_manager(AsyncMock())
        mock_client.create_job.return_value = _make_response({"data": {"id": 50}})
        mock_client.trigger_job_run.return_value = _make_response({"data": {"id": 500}})
        mock_client.get_run.return_value = _make_response(
            {"data": {"status": DbtCloudJobRunStatus.SUCCESS.value}}
        )
        mock_client.get_run_artifact.return_value = _make_response(manifest_data)
        mock_client.delete_job.return_value = _make_response({})

        credentials = _make_mock_credentials(mock_client)
        ex = DbtCloudExecutor(
            credentials=credentials,
            project_id=1,
            environment_id=2,
            poll_frequency_seconds=0,
        )

        result = ex.generate_manifest()

        assert result == manifest_data
        # Verify compile step was used
        create_call = mock_client.create_job.call_args
        steps = create_call.kwargs.get("execute_steps") or create_call.args[3]
        assert steps == ["dbt compile"]

    def test_compile_job_deleted_on_success(self):
        mock_client = _configure_context_manager(AsyncMock())
        mock_client.create_job.return_value = _make_response({"data": {"id": 60}})
        mock_client.trigger_job_run.return_value = _make_response({"data": {"id": 600}})
        mock_client.get_run.return_value = _make_response(
            {"data": {"status": DbtCloudJobRunStatus.SUCCESS.value}}
        )
        mock_client.get_run_artifact.return_value = _make_response({"nodes": {}})
        mock_client.delete_job.return_value = _make_response({})

        credentials = _make_mock_credentials(mock_client)
        ex = DbtCloudExecutor(
            credentials=credentials,
            project_id=1,
            environment_id=2,
            poll_frequency_seconds=0,
        )

        ex.generate_manifest()

        mock_client.delete_job.assert_called_once_with(job_id=60)

    def test_compile_job_deleted_on_failure(self):
        mock_client = _configure_context_manager(AsyncMock())
        mock_client.create_job.return_value = _make_response({"data": {"id": 70}})
        mock_client.trigger_job_run.return_value = _make_response({"data": {"id": 700}})
        mock_client.get_run.return_value = _make_response(
            {"data": {"status": DbtCloudJobRunStatus.FAILED.value}}
        )
        mock_client.delete_job.return_value = _make_response({})

        credentials = _make_mock_credentials(mock_client)
        ex = DbtCloudExecutor(
            credentials=credentials,
            project_id=1,
            environment_id=2,
            poll_frequency_seconds=0,
        )

        with pytest.raises(RuntimeError, match="FAILED"):
            ex.generate_manifest()

        mock_client.delete_job.assert_called_once_with(job_id=70)

    def test_job_name_contains_compile(self):
        mock_client = _configure_context_manager(AsyncMock())
        mock_client.create_job.return_value = _make_response({"data": {"id": 80}})
        mock_client.trigger_job_run.return_value = _make_response({"data": {"id": 800}})
        mock_client.get_run.return_value = _make_response(
            {"data": {"status": DbtCloudJobRunStatus.SUCCESS.value}}
        )
        mock_client.get_run_artifact.return_value = _make_response({"nodes": {}})
        mock_client.delete_job.return_value = _make_response({})

        credentials = _make_mock_credentials(mock_client)
        ex = DbtCloudExecutor(
            credentials=credentials,
            project_id=1,
            environment_id=2,
            job_name_prefix="my-prefix",
            poll_frequency_seconds=0,
        )

        ex.generate_manifest()

        create_call = mock_client.create_job.call_args
        name = create_call.kwargs.get("name") or create_call.args[2]
        assert "my-prefix" in name
        assert "compile" in name


# =============================================================================
# resolve_manifest_path
# =============================================================================


class TestResolveManifestPath:
    def test_uses_defer_to_job_id(self, tmp_path):
        manifest_data = {"nodes": {}, "sources": {}}
        mock_client = _configure_context_manager(AsyncMock())
        mock_client.get_job_artifact.return_value = _make_response(manifest_data)
        credentials = _make_mock_credentials(mock_client)

        ex = DbtCloudExecutor(
            credentials=credentials,
            project_id=1,
            environment_id=2,
            defer_to_job_id=111,
        )

        path = ex.resolve_manifest_path()

        assert path.exists()
        assert path.name == "manifest.json"
        with open(path) as f:
            loaded = json.load(f)
        assert loaded == manifest_data
        mock_client.get_job_artifact.assert_called_once_with(
            job_id=111, path="manifest.json"
        )

    def test_generates_manifest_when_no_defer(self, tmp_path):
        manifest_data = {"nodes": {}, "sources": {}}
        mock_client = _configure_context_manager(AsyncMock())
        mock_client.create_job.return_value = _make_response({"data": {"id": 90}})
        mock_client.trigger_job_run.return_value = _make_response({"data": {"id": 900}})
        mock_client.get_run.return_value = _make_response(
            {"data": {"status": DbtCloudJobRunStatus.SUCCESS.value}}
        )
        mock_client.get_run_artifact.return_value = _make_response(manifest_data)
        mock_client.delete_job.return_value = _make_response({})

        credentials = _make_mock_credentials(mock_client)
        ex = DbtCloudExecutor(
            credentials=credentials,
            project_id=1,
            environment_id=2,
            poll_frequency_seconds=0,
        )

        path = ex.resolve_manifest_path()

        assert path.exists()
        assert path.name == "manifest.json"
        with open(path) as f:
            loaded = json.load(f)
        assert loaded == manifest_data

    def test_isolated_target_dir_per_run(self):
        """Each call to resolve_manifest_path() creates a distinct temp directory
        so concurrent orchestrations don't share a dbt target path."""
        manifest_data = {"nodes": {}}
        mock_client = _configure_context_manager(AsyncMock())
        mock_client.get_job_artifact.return_value = _make_response(manifest_data)
        credentials = _make_mock_credentials(mock_client)
        ex = DbtCloudExecutor(
            credentials=credentials,
            project_id=1,
            environment_id=2,
            defer_to_job_id=1,
        )

        path_a = ex.resolve_manifest_path()
        mock_client.get_job_artifact.return_value = _make_response(manifest_data)
        ex2 = DbtCloudExecutor(
            credentials=credentials,
            project_id=1,
            environment_id=2,
            defer_to_job_id=1,
        )
        path_b = ex2.resolve_manifest_path()

        assert path_a.parent != path_b.parent, (
            "Two runs share the same target directory — concurrent writes will collide"
        )

    def test_temp_dir_cleaned_up_on_executor_gc(self):
        """Temp directory is removed when the executor is garbage collected."""
        manifest_data = {"nodes": {}}
        mock_client = _configure_context_manager(AsyncMock())
        mock_client.get_job_artifact.return_value = _make_response(manifest_data)
        credentials = _make_mock_credentials(mock_client)
        ex = DbtCloudExecutor(
            credentials=credentials,
            project_id=1,
            environment_id=2,
            defer_to_job_id=1,
        )

        path = ex.resolve_manifest_path()
        assert path.exists()

        # Explicitly clean up the TemporaryDirectory and verify the path is gone.
        ex._manifest_temp_dir.cleanup()
        assert not path.exists()

    def test_returns_absolute_path_object(self):
        manifest_data = {"nodes": {}}
        mock_client = _configure_context_manager(AsyncMock())
        mock_client.get_job_artifact.return_value = _make_response(manifest_data)
        credentials = _make_mock_credentials(mock_client)
        ex = DbtCloudExecutor(
            credentials=credentials,
            project_id=1,
            environment_id=2,
            defer_to_job_id=1,
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
        """Orchestrator delegates manifest resolution to executor when
        resolve_manifest_path() returns non-None and manifest_path is None."""
        from prefect_dbt.core._orchestrator import PrefectDbtOrchestrator

        # Build a minimal manifest that ManifestParser can parse.
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

        # Mock executor with resolve_manifest_path
        mock_executor = MagicMock()
        mock_executor.resolve_manifest_path.return_value = manifest_path
        mock_executor.execute_wave.return_value = ExecutionResult(
            success=True,
            node_ids=["model.test.my_model"],
        )

        orch = PrefectDbtOrchestrator(executor=mock_executor)
        # Calling _resolve_manifest_path should hit the executor
        resolved = orch._resolve_manifest_path()

        assert resolved == manifest_path
        mock_executor.resolve_manifest_path.assert_called_once()

    def test_settings_target_path_synced_after_executor_manifest(self, tmp_path):
        """settings.target_path must be updated to the executor manifest's
        parent so that _create_artifacts() and compiled-code lookup write/read
        artifacts in the same directory as the manifest, not the stale default."""
        from prefect_dbt.core._orchestrator import PrefectDbtOrchestrator

        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps({"nodes": {}, "sources": {}}))

        mock_executor = MagicMock()
        mock_executor.resolve_manifest_path.return_value = manifest_path

        orch = PrefectDbtOrchestrator(executor=mock_executor)
        original_target_path = orch._settings.target_path

        orch._resolve_manifest_path()

        # settings.target_path must now point at the manifest's directory
        assert orch._settings.target_path == manifest_path.parent
        assert orch._settings.target_path != original_target_path

    def test_executor_manifest_path_persisted_for_target_resolution(self, tmp_path):
        """After _resolve_manifest_path() delegates to the executor,
        _resolve_target_path() must return the manifest's parent directory so
        that resolve_selection() uses the same target context."""
        from prefect_dbt.core._orchestrator import PrefectDbtOrchestrator

        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps({"nodes": {}, "sources": {}}))

        mock_executor = MagicMock()
        mock_executor.resolve_manifest_path.return_value = manifest_path

        orch = PrefectDbtOrchestrator(executor=mock_executor)
        # _manifest_path starts as None
        assert orch._manifest_path is None

        orch._resolve_manifest_path()

        # Absolute path is cached as-is
        assert orch._manifest_path == manifest_path
        # _resolve_target_path now returns the manifest's parent
        assert orch._resolve_target_path() == manifest_path.parent
        # A second call returns the cached path without hitting the executor
        assert orch._resolve_manifest_path() == manifest_path
        assert mock_executor.resolve_manifest_path.call_count == 1

    def test_orchestrator_skips_executor_when_manifest_path_provided(self, tmp_path):
        """Orchestrator uses explicit manifest_path without calling executor."""
        from prefect_dbt.core._orchestrator import PrefectDbtOrchestrator

        manifest_path = tmp_path / "manifest.json"
        manifest_data = {"nodes": {}, "sources": {}}
        manifest_path.write_text(json.dumps(manifest_data))

        mock_executor = MagicMock()
        mock_executor.resolve_manifest_path.return_value = Path("/should/not/be/called")

        orch = PrefectDbtOrchestrator(
            executor=mock_executor,
            manifest_path=manifest_path,
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

        mock_client = AsyncMock()
        credentials = _make_mock_credentials(mock_client)
        ex = DbtCloudExecutor(credentials=credentials, project_id=1, environment_id=2)
        assert isinstance(ex, DbtExecutor)

    def test_has_execute_node(self):
        ex = _make_executor(AsyncMock())
        assert callable(getattr(ex, "execute_node", None))

    def test_has_execute_wave(self):
        ex = _make_executor(AsyncMock())
        assert callable(getattr(ex, "execute_wave", None))

    def test_has_resolve_manifest_path(self):
        ex = _make_executor(AsyncMock())
        assert callable(getattr(ex, "resolve_manifest_path", None))
