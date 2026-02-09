"""Integration tests for PrefectDbtOrchestrator against a real DuckDB dbt project.

These tests exercise the full orchestrator pipeline (manifest parsing,
selector resolution, wave execution) with no mocks — real dbtRunner,
real DuckDB, real manifest.
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

from prefect_dbt.core._orchestrator import PrefectDbtOrchestrator  # noqa: E402
from prefect_dbt.core.settings import PrefectDbtSettings  # noqa: E402

pytestmark = pytest.mark.integration

# Path to the bundled dbt test project
DBT_TEST_PROJECT = Path(__file__).resolve().parent.parent / "dbt_test_project"

# Node unique_ids we expect from the test project
SEED_CUSTOMERS = "seed.test_project.customers"
SEED_ORDERS = "seed.test_project.orders"
STG_CUSTOMERS = "model.test_project.stg_customers"
STG_ORDERS = "model.test_project.stg_orders"
INT_ORDERS_ENRICHED = "model.test_project.int_orders_enriched"
CUSTOMER_SUMMARY = "model.test_project.customer_summary"

ALL_EXECUTABLE = {
    SEED_CUSTOMERS,
    SEED_ORDERS,
    STG_CUSTOMERS,
    STG_ORDERS,
    CUSTOMER_SUMMARY,
}


@pytest.fixture(scope="session")
def dbt_project(tmp_path_factory):
    """Set up a real dbt project with DuckDB and a parsed manifest.

    Session-scoped: copies the test project to a temp directory, writes a
    profiles.yml pointing DuckDB at a local file, and runs ``dbt parse``
    to generate ``target/manifest.json``.
    """
    project_dir = tmp_path_factory.mktemp("dbt_project")

    # Copy the test project into the temp directory
    for item in DBT_TEST_PROJECT.iterdir():
        dest = project_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    # Write profiles.yml with DuckDB pointing at a local file
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
    profiles_path = project_dir / "profiles.yml"
    profiles_path.write_text(yaml.dump(profiles))

    # Run dbt parse to generate manifest.json
    runner = dbtRunner()
    result = runner.invoke(
        [
            "parse",
            "--project-dir",
            str(project_dir),
            "--profiles-dir",
            str(project_dir),
        ]
    )
    assert result.success, f"dbt parse failed: {result.exception}"

    manifest_path = project_dir / "target" / "manifest.json"
    assert manifest_path.exists(), "manifest.json not generated"

    return {
        "project_dir": project_dir,
        "profiles_dir": project_dir,
        "manifest_path": manifest_path,
    }


def _make_orchestrator(dbt_project, **kwargs):
    """Create a PrefectDbtOrchestrator pointed at the test project."""
    settings = PrefectDbtSettings(
        project_dir=dbt_project["project_dir"],
        profiles_dir=dbt_project["profiles_dir"],
    )
    return PrefectDbtOrchestrator(
        settings=settings,
        manifest_path=dbt_project["manifest_path"],
        **kwargs,
    )


class TestOrchestratorIntegration:
    """Integration tests that run the full orchestrator against DuckDB."""

    def test_full_build_all_nodes_succeed(self, dbt_project):
        """run_build() with no selectors executes all 5 executable nodes successfully."""
        orchestrator = _make_orchestrator(dbt_project)
        results = orchestrator.run_build()

        assert set(results.keys()) == ALL_EXECUTABLE
        for node_id, result in results.items():
            assert result["status"] == "success", (
                f"{node_id} failed: {result.get('error')}"
            )

    def test_build_wave_ordering(self, dbt_project):
        """Builds execute in 3 waves: seeds -> staging -> marts."""
        orchestrator = _make_orchestrator(dbt_project)
        results = orchestrator.run_build()

        # All nodes succeeded — verify via timing that seeds started first,
        # then staging, then marts. We check by comparing started_at timestamps.
        seed_started = max(
            results[SEED_CUSTOMERS]["timing"]["started_at"],
            results[SEED_ORDERS]["timing"]["started_at"],
        )
        staging_started = min(
            results[STG_CUSTOMERS]["timing"]["started_at"],
            results[STG_ORDERS]["timing"]["started_at"],
        )
        mart_started = results[CUSTOMER_SUMMARY]["timing"]["started_at"]

        # Seeds wave must start before or at staging wave
        assert seed_started <= staging_started
        # Staging wave must start before or at mart wave
        assert staging_started <= mart_started

    def test_build_with_select(self, dbt_project):
        """run_build(select='staging') returns only staging models."""
        orchestrator = _make_orchestrator(dbt_project)
        results = orchestrator.run_build(select="staging")

        # Should only contain the two staging models
        assert set(results.keys()) == {STG_CUSTOMERS, STG_ORDERS}
        for result in results.values():
            assert result["status"] == "success"

    def test_build_with_graph_selector(self, dbt_project):
        """run_build(select='+customer_summary') includes all upstream nodes."""
        orchestrator = _make_orchestrator(dbt_project)
        results = orchestrator.run_build(select="+customer_summary")

        # +customer_summary means customer_summary and all its ancestors.
        # The ephemeral int_orders_enriched is resolved through, so we get:
        # seeds + staging + customer_summary = all executable nodes
        assert set(results.keys()) == ALL_EXECUTABLE
        for result in results.values():
            assert result["status"] == "success"

    def test_build_result_has_timing_and_artifacts(self, dbt_project):
        """Results include timing fields and execution_time from artifacts."""
        orchestrator = _make_orchestrator(dbt_project)
        results = orchestrator.run_build()

        nodes_with_execution_time = []
        for node_id, result in results.items():
            timing = result["timing"]
            assert "started_at" in timing
            assert "completed_at" in timing
            assert "duration_seconds" in timing
            assert isinstance(timing["duration_seconds"], float)
            assert timing["duration_seconds"] >= 0

            # execution_time comes from dbt artifacts — track which nodes have it
            if "execution_time" in timing:
                assert isinstance(timing["execution_time"], float)
                nodes_with_execution_time.append(node_id)

        # At least the model nodes should have execution_time from artifacts
        assert len(nodes_with_execution_time) > 0

    def test_full_refresh_build(self, dbt_project):
        """run_build(full_refresh=True) succeeds."""
        orchestrator = _make_orchestrator(dbt_project)
        results = orchestrator.run_build(full_refresh=True)

        assert len(results) == len(ALL_EXECUTABLE)
        for result in results.values():
            assert result["status"] == "success"

    def test_build_creates_database_objects(self, dbt_project):
        """After build, DuckDB contains the expected tables/views with correct row counts."""
        orchestrator = _make_orchestrator(dbt_project)
        results = orchestrator.run_build()

        # Verify the build succeeded before querying the database
        for node_id, result in results.items():
            assert result["status"] == "success", (
                f"{node_id} failed: {result.get('error')}"
            )

        db_path = dbt_project["project_dir"] / "warehouse.duckdb"
        conn = duckdb.connect(str(db_path))
        try:
            # Seeds should exist as tables
            customers = conn.execute("select count(*) from main.customers").fetchone()
            assert customers[0] == 5

            orders = conn.execute("select count(*) from main.orders").fetchone()
            assert orders[0] == 10

            # Staging views
            stg_customers = conn.execute(
                "select count(*) from main.stg_customers"
            ).fetchone()
            assert stg_customers[0] == 5

            stg_orders = conn.execute("select count(*) from main.stg_orders").fetchone()
            assert stg_orders[0] == 10

            # Mart table
            summary = conn.execute(
                "select count(*) from main.customer_summary"
            ).fetchone()
            assert summary[0] == 5  # 5 distinct customers

            # Verify aggregation correctness for a specific customer
            alice = conn.execute(
                "select order_count, total_amount from main.customer_summary "
                "where customer_name = 'alice'"
            ).fetchone()
            assert alice[0] == 2  # alice has 2 orders
            assert alice[1] == 300  # 100 + 200
        finally:
            conn.close()

    def test_ephemeral_model_not_in_results(self, dbt_project):
        """The ephemeral int_orders_enriched does not appear in build results."""
        orchestrator = _make_orchestrator(dbt_project)
        results = orchestrator.run_build()

        assert INT_ORDERS_ENRICHED not in results
