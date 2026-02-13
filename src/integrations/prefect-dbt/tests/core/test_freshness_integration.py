"""Integration tests for source freshness features against a real DuckDB dbt project.

These tests exercise source freshness filtering and expiration with real
dbtRunner, real DuckDB, and real manifest parsing.
"""

import shutil
from pathlib import Path

import pytest
import yaml
from dbt.cli.main import dbtRunner

duckdb = pytest.importorskip("duckdb", reason="duckdb required for integration tests")
pytest.importorskip(
    "dbt.adapters.duckdb", reason="dbt-duckdb required for integration tests"
)

from prefect_dbt.core._orchestrator import (  # noqa: E402
    ExecutionMode,
    PrefectDbtOrchestrator,
)
from prefect_dbt.core.settings import PrefectDbtSettings  # noqa: E402

pytestmark = pytest.mark.integration

# Path to the bundled dbt test project
DBT_TEST_PROJECT = Path(__file__).resolve().parent.parent / "dbt_test_project"


@pytest.fixture(scope="session")
def dbt_project(tmp_path_factory):
    """Session-scoped dbt project with DuckDB and parsed manifest."""
    project_dir = tmp_path_factory.mktemp("dbt_freshness_project")

    for item in DBT_TEST_PROJECT.iterdir():
        dest = project_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    profiles = {
        "test": {
            "target": "dev",
            "outputs": {
                "dev": {
                    "type": "duckdb",
                    "path": str(project_dir / "warehouse.duckdb"),
                    "schema": "main",
                    "threads": 1,
                }
            },
        }
    }
    (project_dir / "profiles.yml").write_text(yaml.dump(profiles))

    runner = dbtRunner()
    result = runner.invoke(
        ["parse", "--project-dir", str(project_dir), "--profiles-dir", str(project_dir)]
    )
    assert result.success, f"dbt parse failed: {result.exception}"

    return {
        "project_dir": project_dir,
        "profiles_dir": project_dir,
        "manifest_path": project_dir / "target" / "manifest.json",
    }


@pytest.fixture
def freshness_dbt_project(dbt_project, tmp_path):
    """Factory fixture that creates a dbt project with source freshness config.

    Returns a factory accepting (warn_count, warn_period, error_count, error_period).
    Default: huge thresholds (always fresh).
    """
    call_count = [0]

    def _factory(
        warn_count=99999,
        warn_period="day",
        error_count=99999,
        error_period="day",
    ):
        call_count[0] += 1
        project_dir = tmp_path / f"freshness_{call_count[0]}"
        shutil.copytree(dbt_project["project_dir"], project_dir)

        # Write profiles.yml with new DuckDB path
        profiles = {
            "test": {
                "target": "dev",
                "outputs": {
                    "dev": {
                        "type": "duckdb",
                        "path": str(project_dir / "warehouse.duckdb"),
                        "schema": "main",
                        "threads": 1,
                    }
                },
            }
        }
        (project_dir / "profiles.yml").write_text(yaml.dump(profiles))

        # Remove any existing DuckDB files
        for f in project_dir.glob("warehouse.duckdb*"):
            f.unlink()

        # Run dbt seed first to populate the base tables
        runner = dbtRunner()
        seed_result = runner.invoke(
            [
                "seed",
                "--project-dir",
                str(project_dir),
                "--profiles-dir",
                str(project_dir),
            ]
        )
        assert seed_result.success, f"dbt seed failed: {seed_result.exception}"

        # Create source tables with proper timestamp columns for freshness checks.
        # dbt source freshness requires timestamp columns, but seed CSVs produce
        # date columns.  We create separate "src_*" tables with casted timestamps.
        db_path = project_dir / "warehouse.duckdb"
        conn = duckdb.connect(str(db_path))
        try:
            conn.execute("""
                CREATE OR REPLACE TABLE main.src_customers AS
                SELECT customer_id, name,
                       created_at::timestamp AS loaded_at
                FROM main.customers
            """)
            conn.execute("""
                CREATE OR REPLACE TABLE main.src_orders AS
                SELECT order_id, customer_id, amount,
                       order_date::timestamp AS loaded_at
                FROM main.orders
            """)
        finally:
            conn.close()

        # Write models/sources.yml defining sources on the src_* tables
        sources_yml = {
            "version": 2,
            "sources": [
                {
                    "name": "raw",
                    "schema": "main",
                    "freshness": {
                        "warn_after": {"count": warn_count, "period": warn_period},
                        "error_after": {"count": error_count, "period": error_period},
                    },
                    "loaded_at_field": "loaded_at",
                    "tables": [
                        {
                            "name": "src_customers",
                            "identifier": "src_customers",
                        },
                        {
                            "name": "src_orders",
                            "identifier": "src_orders",
                        },
                    ],
                }
            ],
        }
        sources_dir = project_dir / "models"
        sources_dir.mkdir(exist_ok=True)
        (sources_dir / "sources.yml").write_text(yaml.dump(sources_yml))

        # Write source staging models
        source_staging_dir = project_dir / "models" / "source_staging"
        source_staging_dir.mkdir(parents=True, exist_ok=True)

        (source_staging_dir / "stg_src_customers.sql").write_text(
            "select customer_id, name, loaded_at\n"
            "from {{ source('raw', 'src_customers') }}\n"
        )
        (source_staging_dir / "stg_src_orders.sql").write_text(
            "select order_id, customer_id, amount, loaded_at\n"
            "from {{ source('raw', 'src_orders') }}\n"
        )

        # Run dbt parse to update manifest with source definitions
        parse_result = runner.invoke(
            [
                "parse",
                "--project-dir",
                str(project_dir),
                "--profiles-dir",
                str(project_dir),
            ]
        )
        assert parse_result.success, f"dbt parse failed: {parse_result.exception}"

        manifest_path = project_dir / "target" / "manifest.json"
        assert manifest_path.exists(), "manifest.json not generated"

        return {
            "project_dir": project_dir,
            "profiles_dir": project_dir,
            "manifest_path": manifest_path,
        }

    return _factory


class TestFreshnessIntegration:
    def test_fresh_sources_all_models_execute(self, freshness_dbt_project):
        """With huge warn_after, all sources pass freshness -> all models run."""
        proj = freshness_dbt_project(
            warn_count=99999,
            warn_period="day",
            error_count=99999,
            error_period="day",
        )
        settings = PrefectDbtSettings(
            project_dir=proj["project_dir"],
            profiles_dir=proj["profiles_dir"],
        )
        orch = PrefectDbtOrchestrator(
            settings=settings,
            manifest_path=proj["manifest_path"],
            execution_mode=ExecutionMode.PER_WAVE,
        )

        results = orch.run_build(only_fresh_sources=True)

        # Find source staging models
        src_models = {k: v for k, v in results.items() if "stg_src" in k}
        assert len(src_models) >= 2
        for node_id, result in src_models.items():
            assert result["status"] == "success", (
                f"{node_id} failed: {result.get('error')}"
            )

    def test_stale_sources_skip_dependent_models(self, freshness_dbt_project):
        """With tiny warn_after, sources are stale -> source_staging models skipped."""
        proj = freshness_dbt_project(
            warn_count=1,
            warn_period="minute",
            error_count=1,
            error_period="minute",
        )
        settings = PrefectDbtSettings(
            project_dir=proj["project_dir"],
            profiles_dir=proj["profiles_dir"],
        )
        orch = PrefectDbtOrchestrator(
            settings=settings,
            manifest_path=proj["manifest_path"],
            execution_mode=ExecutionMode.PER_WAVE,
        )

        results = orch.run_build(only_fresh_sources=True)

        # Source staging models should be skipped
        src_models = {k: v for k, v in results.items() if "stg_src" in k}
        assert len(src_models) >= 2
        for node_id, result in src_models.items():
            assert result["status"] == "skipped", (
                f"{node_id} should be skipped but got: {result}"
            )
            assert "stale source" in result["reason"]

        # Non-source models (seeds, ref-based staging, marts) should still execute
        # Seeds should succeed
        seed_results = {k: v for k, v in results.items() if k.startswith("seed.")}
        for node_id, result in seed_results.items():
            assert result["status"] == "success", (
                f"{node_id} failed: {result.get('error')}"
            )

    def test_stale_sources_cascade_downstream(self, freshness_dbt_project):
        """Models downstream of stale-skipped models are also skipped."""
        proj = freshness_dbt_project(
            warn_count=1,
            warn_period="minute",
            error_count=1,
            error_period="minute",
        )

        # Add a mart model that depends on stg_src_customers
        mart_dir = proj["project_dir"] / "models" / "marts"
        mart_dir.mkdir(parents=True, exist_ok=True)
        (mart_dir / "src_based_mart.sql").write_text(
            "select customer_id, name\nfrom {{ ref('stg_src_customers') }}\n"
        )

        # Also write a stg_src_customers model in source_staging for the mart to ref
        source_staging_dir = proj["project_dir"] / "models" / "source_staging"
        source_staging_dir.mkdir(parents=True, exist_ok=True)
        # (Already exists from fixture, just need the mart model)

        # Re-parse to pick up the new model
        runner = dbtRunner()
        parse_result = runner.invoke(
            [
                "parse",
                "--project-dir",
                str(proj["project_dir"]),
                "--profiles-dir",
                str(proj["profiles_dir"]),
            ]
        )
        assert parse_result.success, f"dbt parse failed: {parse_result.exception}"

        settings = PrefectDbtSettings(
            project_dir=proj["project_dir"],
            profiles_dir=proj["profiles_dir"],
        )
        orch = PrefectDbtOrchestrator(
            settings=settings,
            manifest_path=proj["manifest_path"],
            execution_mode=ExecutionMode.PER_WAVE,
        )

        results = orch.run_build(only_fresh_sources=True)

        # The new mart should be skipped due to cascade
        mart_result = results.get("model.test_project.src_based_mart")
        assert mart_result is not None, (
            f"src_based_mart not found in results. Keys: {list(results.keys())}"
        )
        assert mart_result["status"] == "skipped"

    def test_only_fresh_sources_false_runs_everything(self, freshness_dbt_project):
        """Default only_fresh_sources=False executes all models regardless."""
        proj = freshness_dbt_project(
            warn_count=1,
            warn_period="minute",
            error_count=1,
            error_period="minute",
        )
        settings = PrefectDbtSettings(
            project_dir=proj["project_dir"],
            profiles_dir=proj["profiles_dir"],
        )
        orch = PrefectDbtOrchestrator(
            settings=settings,
            manifest_path=proj["manifest_path"],
            execution_mode=ExecutionMode.PER_WAVE,
        )

        # only_fresh_sources=False (default) -> run everything
        results = orch.run_build(only_fresh_sources=False)

        src_models = {k: v for k, v in results.items() if "stg_src" in k}
        for node_id, result in src_models.items():
            assert result["status"] == "success", (
                f"{node_id} failed: {result.get('error')}"
            )

    def test_freshness_expiration_with_caching(self, freshness_dbt_project):
        """use_source_freshness_expiration computes cache_expiration from freshness data."""
        from prefect import flow
        from prefect.task_runners import ThreadPoolTaskRunner

        proj = freshness_dbt_project(
            warn_count=99999,
            warn_period="day",
            error_count=99999,
            error_period="day",
        )

        result_dir = proj["project_dir"] / "result_storage"
        result_dir.mkdir()
        key_dir = proj["project_dir"] / "cache_key_storage"
        key_dir.mkdir()

        settings = PrefectDbtSettings(
            project_dir=proj["project_dir"],
            profiles_dir=proj["profiles_dir"],
        )
        orch = PrefectDbtOrchestrator(
            settings=settings,
            manifest_path=proj["manifest_path"],
            execution_mode=ExecutionMode.PER_NODE,
            enable_caching=True,
            use_source_freshness_expiration=True,
            concurrency=1,
            task_runner_type=ThreadPoolTaskRunner,
            result_storage=result_dir,
            cache_key_storage=str(key_dir),
        )

        @flow
        def test_flow():
            return orch.run_build()

        results = test_flow()

        for node_id, result in results.items():
            assert result["status"] == "success", (
                f"{node_id} failed: {result.get('error')}"
            )
