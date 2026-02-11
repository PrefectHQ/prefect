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

from prefect_dbt.core._orchestrator import (  # noqa: E402
    ExecutionMode,
    PrefectDbtOrchestrator,
)
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
    profiles.yml pointing DuckDB at a local file, and runs `dbt parse`
    to generate `target/manifest.json`.
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


@pytest.fixture
def orchestrator(dbt_project):
    """Factory fixture that creates a PrefectDbtOrchestrator for the test project."""

    def _factory(**kwargs):
        settings = PrefectDbtSettings(
            project_dir=dbt_project["project_dir"],
            profiles_dir=dbt_project["profiles_dir"],
        )
        return PrefectDbtOrchestrator(
            settings=settings,
            manifest_path=dbt_project["manifest_path"],
            **kwargs,
        )

    return _factory


class TestOrchestratorIntegration:
    """Integration tests that run the full orchestrator against DuckDB."""

    def test_full_build_all_nodes_succeed(self, orchestrator):
        """run_build() with no selectors executes all 5 executable nodes successfully."""
        orch = orchestrator()
        results = orch.run_build()

        assert set(results.keys()) == ALL_EXECUTABLE
        for node_id, result in results.items():
            assert result["status"] == "success", (
                f"{node_id} failed: {result.get('error')}"
            )

    def test_build_wave_ordering(self, orchestrator):
        """Builds execute in 3 waves: seeds -> staging -> marts."""
        orch = orchestrator()
        results = orch.run_build()

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

    def test_build_with_select(self, orchestrator):
        """run_build(select='staging') returns only staging models."""
        orch = orchestrator()
        results = orch.run_build(select="staging")

        # Should only contain the two staging models
        assert set(results.keys()) == {STG_CUSTOMERS, STG_ORDERS}
        for result in results.values():
            assert result["status"] == "success"

    def test_build_with_graph_selector(self, orchestrator):
        """run_build(select='+customer_summary') includes all upstream nodes."""
        orch = orchestrator()
        results = orch.run_build(select="+customer_summary")

        # +customer_summary means customer_summary and all its ancestors.
        # The ephemeral int_orders_enriched is resolved through, so we get:
        # seeds + staging + customer_summary = all executable nodes
        assert set(results.keys()) == ALL_EXECUTABLE
        for result in results.values():
            assert result["status"] == "success"

    def test_build_result_has_timing_and_artifacts(self, orchestrator):
        """Results include timing fields and execution_time from artifacts."""
        orch = orchestrator()
        results = orch.run_build()

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

    def test_full_refresh_build(self, orchestrator):
        """run_build(full_refresh=True) succeeds."""
        orch = orchestrator()
        results = orch.run_build(full_refresh=True)

        assert len(results) == len(ALL_EXECUTABLE)
        for result in results.values():
            assert result["status"] == "success"

    def test_build_creates_database_objects(self, orchestrator, dbt_project):
        """After build, DuckDB contains the expected tables/views with correct row counts."""
        orch = orchestrator()
        results = orch.run_build()

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

    def test_ephemeral_model_not_in_results(self, orchestrator):
        """The ephemeral int_orders_enriched does not appear in build results."""
        orch = orchestrator()
        results = orch.run_build()

        assert INT_ORDERS_ENRICHED not in results


@pytest.fixture
def per_node_dbt_project(dbt_project, tmp_path):
    """Function-scoped copy of the dbt project for PER_NODE tests.

    PER_WAVE tests run dbt in-process and the dbt-duckdb adapter keeps
    an OS-level file lock on the `.duckdb` file that persists even
    after `reset_adapters()` / `cleanup_connections()`.  PER_NODE
    tests run dbt in subprocesses that need their own file locks.

    This fixture copies the session-scoped project to a fresh temp
    directory so each PER_NODE test gets its own `.duckdb` file with
    no lock conflicts from the parent process.
    """
    project_dir = tmp_path / "dbt_project"
    shutil.copytree(dbt_project["project_dir"], project_dir)

    # Update profiles.yml to point at the new DuckDB path
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

    # Remove any existing DuckDB files from the copy so each test
    # starts with a clean database.
    for f in project_dir.glob("warehouse.duckdb*"):
        f.unlink()

    # Pre-load seed data so tests that select only models (e.g.
    # `select="staging"`) find the underlying seed tables.
    # Run in a subprocess to avoid the parent process acquiring a
    # DuckDB file lock that would block PER_NODE subprocesses.
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from dbt.cli.main import dbtRunner; "
                f'dbtRunner().invoke(["seed", "--project-dir", "{project_dir}", '
                f'"--profiles-dir", "{project_dir}"])'
            ),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"dbt seed failed: {result.stderr}"

    return {
        "project_dir": project_dir,
        "profiles_dir": project_dir,
        "manifest_path": project_dir / "target" / "manifest.json",
    }


@pytest.fixture
def per_node_orchestrator(per_node_dbt_project):
    """Factory fixture that creates a PrefectDbtOrchestrator for PER_NODE tests."""

    def _factory(**kwargs):
        settings = PrefectDbtSettings(
            project_dir=per_node_dbt_project["project_dir"],
            profiles_dir=per_node_dbt_project["profiles_dir"],
        )
        return PrefectDbtOrchestrator(
            settings=settings,
            manifest_path=per_node_dbt_project["manifest_path"],
            **kwargs,
        )

    return _factory


class TestPerNodeIntegration:
    """Integration tests for PER_NODE execution mode against DuckDB.

    All tests use `concurrency=1` because DuckDB's file-based storage
    only supports a single writer at a time.  Without this, concurrent
    `dbt run` invocations within the same wave would conflict on the
    database write lock.  Production databases (Postgres, Snowflake, etc.)
    do not have this limitation.
    """

    def test_per_node_full_build(self, per_node_orchestrator):
        """PER_NODE run_build() executes all 5 executable nodes successfully."""
        from prefect import flow

        orch = per_node_orchestrator(
            execution_mode=ExecutionMode.PER_NODE,
            concurrency=1,
        )

        @flow
        def test_flow():
            return orch.run_build()

        results = test_flow()

        assert set(results.keys()) == ALL_EXECUTABLE
        for node_id, result in results.items():
            assert result["status"] == "success", (
                f"{node_id} failed: {result.get('error')}"
            )

    def test_per_node_wave_ordering(self, per_node_orchestrator):
        """PER_NODE builds respect wave ordering: seeds -> staging -> marts."""
        from prefect import flow

        orch = per_node_orchestrator(
            execution_mode=ExecutionMode.PER_NODE,
            concurrency=1,
        )

        @flow
        def test_flow():
            return orch.run_build()

        results = test_flow()

        seed_started = max(
            results[SEED_CUSTOMERS]["timing"]["started_at"],
            results[SEED_ORDERS]["timing"]["started_at"],
        )
        staging_started = min(
            results[STG_CUSTOMERS]["timing"]["started_at"],
            results[STG_ORDERS]["timing"]["started_at"],
        )
        mart_started = results[CUSTOMER_SUMMARY]["timing"]["started_at"]

        assert seed_started <= staging_started
        assert staging_started <= mart_started

    def test_per_node_with_select(self, per_node_orchestrator):
        """PER_NODE run_build(select='staging') returns only staging models."""
        from prefect import flow

        orch = per_node_orchestrator(
            execution_mode=ExecutionMode.PER_NODE,
            concurrency=1,
        )

        @flow
        def test_flow():
            return orch.run_build(select="staging")

        results = test_flow()

        assert set(results.keys()) == {STG_CUSTOMERS, STG_ORDERS}
        for result in results.values():
            assert result["status"] == "success"

    def test_per_node_uses_correct_commands(self, per_node_orchestrator):
        """PER_NODE uses 'seed' for seeds and 'run' for models."""
        from prefect import flow

        orch = per_node_orchestrator(
            execution_mode=ExecutionMode.PER_NODE,
            concurrency=1,
        )

        @flow
        def test_flow():
            return orch.run_build()

        results = test_flow()

        # Seeds should use 'seed' command
        assert results[SEED_CUSTOMERS]["invocation"]["command"] == "seed"
        assert results[SEED_ORDERS]["invocation"]["command"] == "seed"
        # Models should use 'run' command
        assert results[STG_CUSTOMERS]["invocation"]["command"] == "run"
        assert results[STG_ORDERS]["invocation"]["command"] == "run"
        assert results[CUSTOMER_SUMMARY]["invocation"]["command"] == "run"

    def test_per_node_each_node_has_individual_timing(self, per_node_orchestrator):
        """Each node has its own timing, not shared with the wave."""
        from prefect import flow

        orch = per_node_orchestrator(
            execution_mode=ExecutionMode.PER_NODE,
            concurrency=1,
        )

        @flow
        def test_flow():
            return orch.run_build()

        results = test_flow()

        for node_id, result in results.items():
            timing = result["timing"]
            assert "started_at" in timing
            assert "completed_at" in timing
            assert "duration_seconds" in timing
            assert isinstance(timing["duration_seconds"], float)
            # Each node's invocation should list only its own unique_id
            assert result["invocation"]["args"] == [node_id]

    def test_per_node_ephemeral_not_in_results(self, per_node_orchestrator):
        """Ephemeral models are not executed in PER_NODE mode."""
        from prefect import flow

        orch = per_node_orchestrator(
            execution_mode=ExecutionMode.PER_NODE,
            concurrency=1,
        )

        @flow
        def test_flow():
            return orch.run_build()

        results = test_flow()
        assert INT_ORDERS_ENRICHED not in results

    def test_per_node_creates_database_objects(
        self, per_node_orchestrator, per_node_dbt_project
    ):
        """PER_NODE mode produces the same database objects as PER_WAVE."""
        from prefect import flow

        orch = per_node_orchestrator(
            execution_mode=ExecutionMode.PER_NODE,
            concurrency=1,
        )

        @flow
        def test_flow():
            return orch.run_build()

        results = test_flow()

        for node_id, result in results.items():
            assert result["status"] == "success", (
                f"{node_id} failed: {result.get('error')}"
            )

        db_path = per_node_dbt_project["project_dir"] / "warehouse.duckdb"
        conn = duckdb.connect(str(db_path))
        try:
            customers = conn.execute("select count(*) from main.customers").fetchone()
            assert customers[0] == 5

            summary = conn.execute(
                "select count(*) from main.customer_summary"
            ).fetchone()
            assert summary[0] == 5
        finally:
            conn.close()

    def test_per_node_with_concurrency_limit(self, per_node_orchestrator):
        """PER_NODE with an explicit concurrency limit still succeeds.

        Uses concurrency=1 because DuckDB only supports a single writer.
        The unit tests cover higher concurrency values.
        """
        from prefect import flow

        orch = per_node_orchestrator(
            execution_mode=ExecutionMode.PER_NODE,
            concurrency=1,
        )

        @flow
        def test_flow():
            return orch.run_build()

        results = test_flow()

        assert set(results.keys()) == ALL_EXECUTABLE
        for node_id, result in results.items():
            assert result["status"] == "success", (
                f"{node_id} failed: {result.get('error')}"
            )
