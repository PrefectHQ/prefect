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
    TestStrategy,
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

# Test node IDs generated from schema.yml files in the test project.
# These are deterministic: dbt derives them from model/column/test names
# plus a short hash suffix.
TEST_NOT_NULL_STG_CUSTOMERS_ID = (
    "test.test_project.not_null_stg_customers_customer_id.e2cfb1f9aa"
)
TEST_NOT_NULL_STG_ORDERS_ORDER_ID = (
    "test.test_project.not_null_stg_orders_order_id.81cfe2fe64"
)
TEST_NOT_NULL_STG_ORDERS_CUSTOMER_ID = (
    "test.test_project.not_null_stg_orders_customer_id.af79d5e4b5"
)
TEST_UNIQUE_STG_CUSTOMERS_ID = (
    "test.test_project.unique_stg_customers_customer_id.c7614daada"
)
TEST_UNIQUE_STG_ORDERS_ID = "test.test_project.unique_stg_orders_order_id.e3b841c71a"
TEST_RELATIONSHIPS_ORDERS_CUSTOMERS = "test.test_project.relationships_stg_orders_customer_id__customer_id__ref_stg_customers_.430bf21500"
TEST_NOT_NULL_SUMMARY_ID = (
    "test.test_project.not_null_customer_summary_customer_id.a81d32eb67"
)
TEST_UNIQUE_SUMMARY_ID = (
    "test.test_project.unique_customer_summary_customer_id.2fb01e9693"
)

ALL_TESTS = {
    TEST_NOT_NULL_STG_CUSTOMERS_ID,
    TEST_NOT_NULL_STG_ORDERS_ORDER_ID,
    TEST_NOT_NULL_STG_ORDERS_CUSTOMER_ID,
    TEST_UNIQUE_STG_CUSTOMERS_ID,
    TEST_UNIQUE_STG_ORDERS_ID,
    TEST_RELATIONSHIPS_ORDERS_CUSTOMERS,
    TEST_NOT_NULL_SUMMARY_ID,
    TEST_UNIQUE_SUMMARY_ID,
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
    """Factory fixture that creates a PrefectDbtOrchestrator for the test project.

    Defaults to `test_strategy=TestStrategy.SKIP` so that tests which are not
    specifically exercising test-strategy behaviour get deterministic results
    containing only model/seed nodes.  Tests in `TestTestStrategyIntegration`
    override this by passing an explicit `test_strategy`.
    """

    def _factory(**kwargs):
        kwargs.setdefault("test_strategy", TestStrategy.SKIP)
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

    def test_build_with_select(self, orchestrator, dbt_project):
        """run_build(select='staging') returns only staging models."""
        orch = orchestrator()
        results = orch.run_build(select="staging")

        # Should only contain the two staging models
        assert set(results.keys()) == {STG_CUSTOMERS, STG_ORDERS}
        for result in results.values():
            assert result["status"] == "success"

        # Verify the staging views were actually created in DuckDB
        db_path = dbt_project["project_dir"] / "warehouse.duckdb"
        conn = duckdb.connect(str(db_path))
        try:
            assert (
                conn.execute("select count(*) from main.stg_customers").fetchone()[0]
                == 5
            )
            assert (
                conn.execute("select count(*) from main.stg_orders").fetchone()[0] == 10
            )
        finally:
            conn.close()

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
    """Factory fixture that creates a PrefectDbtOrchestrator for PER_NODE tests.

    Defaults to `test_strategy=TestStrategy.SKIP` for the same reason as
    the `orchestrator` fixture.
    """

    def _factory(**kwargs):
        kwargs.setdefault("test_strategy", TestStrategy.SKIP)
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


@pytest.fixture
def caching_orchestrator(per_node_dbt_project, tmp_path):
    """Factory fixture for PER_NODE orchestrator with caching enabled.

    Shares result_storage and cache_key_storage across calls so
    cross-instance cache tests can verify persistence.

    Uses ThreadPoolTaskRunner to avoid ProcessPoolTaskRunner limitations
    with Prefect's cache key resolution across process boundaries.
    """
    from prefect.task_runners import ThreadPoolTaskRunner

    result_dir = tmp_path / "result_storage"
    result_dir.mkdir()
    key_dir = tmp_path / "cache_key_storage"
    key_dir.mkdir()

    def _factory(**kwargs):
        settings = PrefectDbtSettings(
            project_dir=per_node_dbt_project["project_dir"],
            profiles_dir=per_node_dbt_project["profiles_dir"],
        )
        defaults = {
            "settings": settings,
            "manifest_path": per_node_dbt_project["manifest_path"],
            "execution_mode": ExecutionMode.PER_NODE,
            "concurrency": 1,
            "enable_caching": True,
            "result_storage": result_dir,
            "cache_key_storage": str(key_dir),
            "task_runner_type": ThreadPoolTaskRunner,
            "test_strategy": TestStrategy.SKIP,
        }
        defaults.update(kwargs)
        return PrefectDbtOrchestrator(**defaults)

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

    def test_per_node_with_select(self, per_node_orchestrator, per_node_dbt_project):
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

        # Verify the staging views were actually created in DuckDB
        db_path = per_node_dbt_project["project_dir"] / "warehouse.duckdb"
        conn = duckdb.connect(str(db_path))
        try:
            assert (
                conn.execute("select count(*) from main.stg_customers").fetchone()[0]
                == 5
            )
            assert (
                conn.execute("select count(*) from main.stg_orders").fetchone()[0] == 10
            )
        finally:
            conn.close()

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


def _object_exists(db_path: Path, name: str) -> bool:
    """Check whether a table or view exists in DuckDB."""
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(f"select 1 from main.{name} limit 1")
        return True
    except duckdb.CatalogException:
        return False
    finally:
        conn.close()


def _drop_object(db_path: Path, name: str, kind: str = "TABLE") -> None:
    """Drop a table or view from DuckDB."""
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(f"DROP {kind} IF EXISTS main.{name}")
    finally:
        conn.close()


def _row_count(db_path: Path, name: str) -> int:
    """Return the row count of a table or view in DuckDB."""
    conn = duckdb.connect(str(db_path))
    try:
        return conn.execute(f"select count(*) from main.{name}").fetchone()[0]
    finally:
        conn.close()


class TestPerNodeCachingIntegration:
    """Integration tests for PER_NODE caching against real DuckDB.

    Cache-hit detection strategy ("drop table"):
      1. Run 1: build all nodes (populates DuckDB + cache)
      2. Drop a specific table/view from DuckDB
      3. Run 2: build again
      4. If the node was cached (not re-executed), the dropped object stays absent
      5. If the node was re-executed, dbt recreates the object
    """

    def test_second_run_uses_cache(self, caching_orchestrator, per_node_dbt_project):
        """A second identical build hits the cache — dbt does not re-execute."""
        from prefect import flow

        orch = caching_orchestrator()
        db_path = per_node_dbt_project["project_dir"] / "warehouse.duckdb"

        @flow
        def run():
            return orch.run_build()

        # Run 1: full build
        r1 = run()
        assert all(r["status"] == "success" for r in r1.values())
        assert _object_exists(db_path, "customer_summary")

        # Drop a mart table between runs
        _drop_object(db_path, "customer_summary", "TABLE")
        assert not _object_exists(db_path, "customer_summary")

        # Run 2: should be entirely cached
        r2 = run()
        assert all(r["status"] == "cached" for r in r2.values())

        # customer_summary was NOT recreated → dbt never re-executed it
        assert not _object_exists(db_path, "customer_summary")

    def test_sql_change_invalidates_affected_nodes(
        self, caching_orchestrator, per_node_dbt_project
    ):
        """Changing a SQL file invalidates that node and cascades downstream.

        stg_customers.sql is modified between runs.  The file-content hash
        changes, which invalidates stg_customers' cache key.  Because
        customer_summary includes stg_customers in its upstream_cache_keys,
        its own key also changes — so it is re-executed as well.

        We verify with the "drop table" trick: drop customer_summary after
        run 1.  If it reappears after run 2 the cascade invalidation worked.
        """
        from prefect import flow

        project_dir = per_node_dbt_project["project_dir"]
        db_path = project_dir / "warehouse.duckdb"

        orch = caching_orchestrator()

        @flow
        def run():
            return orch.run_build()

        # Run 1: full build
        r1 = run()
        assert all(r["status"] == "success" for r in r1.values())
        assert _object_exists(db_path, "customer_summary")

        # Modify stg_customers — changes its file_content_hash
        stg_path = project_dir / "models" / "staging" / "stg_customers.sql"
        stg_path.write_text(
            "select customer_id, name, created_at::date as created_at\n"
            "from {{ ref('customers') }}\n"
            "where customer_id <= 3\n"
        )

        # Drop customer_summary TABLE.  If the downstream cascade works,
        # dbt will re-create it in run 2.
        _drop_object(db_path, "customer_summary", "TABLE")
        assert not _object_exists(db_path, "customer_summary")

        # Run 2: stg_customers cache miss (file changed) propagates to
        # customer_summary cache miss (upstream key changed) → re-executed
        r2 = run()
        assert all(r["status"] in ("success", "cached") for r in r2.values())

        # customer_summary was re-created → cascade invalidation worked
        assert _object_exists(db_path, "customer_summary")

        # stg_customers VIEW was also re-executed (file hash changed)
        assert _row_count(db_path, "stg_customers") == 3

    def test_full_refresh_bypasses_cache(
        self, caching_orchestrator, per_node_dbt_project
    ):
        """full_refresh=True forces re-execution even when cache is warm."""
        from prefect import flow

        orch = caching_orchestrator()
        db_path = per_node_dbt_project["project_dir"] / "warehouse.duckdb"

        @flow
        def run(**kwargs):
            return orch.run_build(**kwargs)

        # Run 1: warm cache
        r1 = run()
        assert all(r["status"] == "success" for r in r1.values())

        # Drop customer_summary
        _drop_object(db_path, "customer_summary", "TABLE")

        # Run 2 with full_refresh → cache is bypassed
        r2 = run(full_refresh=True)
        assert all(r["status"] == "success" for r in r2.values())

        # customer_summary was recreated because full_refresh bypassed cache
        assert _object_exists(db_path, "customer_summary")

    def test_cache_persists_across_orchestrator_instances(
        self, caching_orchestrator, per_node_dbt_project
    ):
        """A second orchestrator instance (sharing storage) reuses the cache."""
        from prefect import flow

        db_path = per_node_dbt_project["project_dir"] / "warehouse.duckdb"

        # Instance 1: build and populate cache
        orch1 = caching_orchestrator()

        @flow
        def run1():
            return orch1.run_build()

        r1 = run1()
        assert all(r["status"] == "success" for r in r1.values())

        # Drop customer_summary between instances
        _drop_object(db_path, "customer_summary", "TABLE")

        # Instance 2: shares the same storage dirs
        orch2 = caching_orchestrator()

        @flow
        def run2():
            return orch2.run_build()

        r2 = run2()
        assert all(r["status"] == "cached" for r in r2.values())

        # customer_summary was NOT recreated → orch2 used orch1's cache
        assert not _object_exists(db_path, "customer_summary")

    def test_caching_disabled_executes_every_time(
        self, caching_orchestrator, per_node_dbt_project
    ):
        """With enable_caching=False, every run re-executes all nodes."""
        from prefect import flow

        orch = caching_orchestrator(enable_caching=False)
        db_path = per_node_dbt_project["project_dir"] / "warehouse.duckdb"

        @flow
        def run():
            return orch.run_build()

        # Run 1
        r1 = run()
        assert all(r["status"] == "success" for r in r1.values())

        # Drop customer_summary
        _drop_object(db_path, "customer_summary", "TABLE")

        # Run 2 without caching → dbt re-executes everything
        r2 = run()
        assert all(r["status"] == "success" for r in r2.values())

        # customer_summary was recreated (no caching = always re-executes)
        assert _object_exists(db_path, "customer_summary")

    def test_full_refresh_always_re_executes(
        self, caching_orchestrator, per_node_dbt_project
    ):
        """Repeated full_refresh=True runs always execute (never cached)."""
        from prefect import flow

        orch = caching_orchestrator()
        db_path = per_node_dbt_project["project_dir"] / "warehouse.duckdb"

        @flow
        def run(**kwargs):
            return orch.run_build(**kwargs)

        # Run 1: full_refresh build — populates DB
        r1 = run(full_refresh=True)
        assert all(r["status"] == "success" for r in r1.values())
        assert _object_exists(db_path, "customer_summary")

        # Drop customer_summary between runs
        _drop_object(db_path, "customer_summary", "TABLE")
        assert not _object_exists(db_path, "customer_summary")

        # Run 2: full_refresh again — must re-execute (not cached)
        r2 = run(full_refresh=True)
        assert all(r["status"] == "success" for r in r2.values())

        # customer_summary was recreated — full_refresh never caches
        assert _object_exists(db_path, "customer_summary")

    def test_normal_run_after_full_refresh_uses_cache(
        self, caching_orchestrator, per_node_dbt_project
    ):
        """A normal run's cache isn't poisoned by a full_refresh run."""
        from prefect import flow

        orch = caching_orchestrator()
        db_path = per_node_dbt_project["project_dir"] / "warehouse.duckdb"

        @flow
        def run(**kwargs):
            return orch.run_build(**kwargs)

        # Run 1: normal build — warms cache
        r1 = run()
        assert all(r["status"] == "success" for r in r1.values())

        # Run 2: full_refresh — always executes
        r2 = run(full_refresh=True)
        assert all(r["status"] == "success" for r in r2.values())

        # Drop customer_summary
        _drop_object(db_path, "customer_summary", "TABLE")
        assert not _object_exists(db_path, "customer_summary")

        # Run 3: normal build — should hit Run 1's cache
        r3 = run()
        assert all(r["status"] == "cached" for r in r3.values())

        # customer_summary was NOT recreated — Run 1's cache was used
        assert not _object_exists(db_path, "customer_summary")

    def test_macro_change_invalidates_cache(
        self, caching_orchestrator, per_node_dbt_project
    ):
        """Editing a macro file invalidates cache for dependent nodes."""
        from prefect import flow

        project_dir = per_node_dbt_project["project_dir"]
        db_path = project_dir / "warehouse.duckdb"

        orch = caching_orchestrator()

        @flow
        def run():
            return orch.run_build()

        # Run 1: full build — warms cache
        r1 = run()
        assert all(r["status"] == "success" for r in r1.values())
        assert _object_exists(db_path, "customer_summary")

        # Modify the macro file on disk — changes the macro content hash
        macro_path = project_dir / "macros" / "format_amount.sql"
        macro_path.write_text(
            "{% macro format_amount(column) %}\n"
            "    coalesce({{ column }}, 0)\n"
            "{% endmacro %}\n"
        )

        # Drop customer_summary — if cache miss, dbt will recreate it
        _drop_object(db_path, "customer_summary", "TABLE")
        assert not _object_exists(db_path, "customer_summary")

        # Run 2: macro hash changed → customer_summary must re-execute
        r2 = run()
        assert all(r["status"] in ("success", "cached") for r in r2.values())

        # customer_summary was recreated — macro change invalidated cache
        assert _object_exists(db_path, "customer_summary")


class TestTestStrategyIntegration:
    """Integration tests for test strategies against a real DuckDB dbt project.

    The dbt test project includes schema.yml files that define not_null,
    unique, and relationship tests on staging and mart models.  The expected
    test node IDs are declared as constants (ALL_TESTS) so assertions are
    deterministic.
    """

    def test_fixture_contains_test_definitions(self, dbt_project):
        """Guard: verify the manifest contains the expected test nodes.

        If this fails, the schema.yml files in dbt_test_project are missing
        or dbt parse did not generate test nodes.
        """
        import json

        manifest = json.loads(dbt_project["manifest_path"].read_text())
        manifest_test_ids = {
            uid for uid in manifest["nodes"] if uid.startswith("test.")
        }
        assert manifest_test_ids == ALL_TESTS, (
            f"Manifest test nodes don't match ALL_TESTS.\n"
            f"  Missing: {ALL_TESTS - manifest_test_ids}\n"
            f"  Extra:   {manifest_test_ids - ALL_TESTS}"
        )

    def test_skip_produces_no_test_results(self, orchestrator):
        """SKIP strategy: no test node IDs in results."""
        orch = orchestrator(test_strategy=TestStrategy.SKIP)
        results = orch.run_build()

        test_ids = {k for k in results if k.startswith("test.")}
        assert test_ids == set()
        assert set(results.keys()) == ALL_EXECUTABLE

    def test_immediate_per_wave_includes_tests(self, orchestrator):
        """IMMEDIATE + PER_WAVE: all expected test nodes appear with success."""
        orch = orchestrator(test_strategy=TestStrategy.IMMEDIATE)
        results = orch.run_build()

        model_ids = {k for k in results if not k.startswith("test.")}
        test_ids = {k for k in results if k.startswith("test.")}

        assert model_ids == ALL_EXECUTABLE
        assert test_ids == ALL_TESTS
        for tid in test_ids:
            assert results[tid]["status"] == "success", (
                f"Test {tid} failed: {results[tid].get('error')}"
            )

    def test_deferred_per_wave_includes_tests(self, orchestrator):
        """DEFERRED + PER_WAVE: all expected test nodes appear with success."""
        orch = orchestrator(test_strategy=TestStrategy.DEFERRED)
        results = orch.run_build()

        model_ids = {k for k in results if not k.startswith("test.")}
        test_ids = {k for k in results if k.startswith("test.")}

        assert model_ids == ALL_EXECUTABLE
        assert test_ids == ALL_TESTS
        for tid in test_ids:
            assert results[tid]["status"] == "success", (
                f"Test {tid} failed: {results[tid].get('error')}"
            )

    def test_immediate_per_node_includes_tests(self, per_node_orchestrator):
        """IMMEDIATE + PER_NODE: all expected test nodes appear with success."""
        from prefect import flow

        orch = per_node_orchestrator(
            execution_mode=ExecutionMode.PER_NODE,
            concurrency=1,
            test_strategy=TestStrategy.IMMEDIATE,
        )

        @flow
        def test_flow():
            return orch.run_build()

        results = test_flow()

        model_ids = {k for k in results if not k.startswith("test.")}
        test_ids = {k for k in results if k.startswith("test.")}

        assert model_ids == ALL_EXECUTABLE
        assert test_ids == ALL_TESTS
        for tid in test_ids:
            assert results[tid]["status"] == "success", (
                f"Test {tid} failed: {results[tid].get('error')}"
            )

    def test_deferred_per_node_includes_tests(self, per_node_orchestrator):
        """DEFERRED + PER_NODE: test nodes run after all models."""
        from prefect import flow

        orch = per_node_orchestrator(
            execution_mode=ExecutionMode.PER_NODE,
            concurrency=1,
            test_strategy=TestStrategy.DEFERRED,
        )

        @flow
        def test_flow():
            return orch.run_build()

        results = test_flow()

        model_ids = {k for k in results if not k.startswith("test.")}
        test_ids = {k for k in results if k.startswith("test.")}

        assert model_ids == ALL_EXECUTABLE
        assert test_ids == ALL_TESTS

        # All models must complete before any test starts
        latest_model = max(results[m]["timing"]["completed_at"] for m in model_ids)
        earliest_test = min(results[t]["timing"]["started_at"] for t in test_ids)
        assert latest_model <= earliest_test

    def test_relationship_test_passes(self, orchestrator):
        """The relationship test between stg_orders.customer_id -> stg_customers passes."""
        orch = orchestrator(test_strategy=TestStrategy.IMMEDIATE)
        results = orch.run_build()

        assert TEST_RELATIONSHIPS_ORDERS_CUSTOMERS in results
        assert results[TEST_RELATIONSHIPS_ORDERS_CUSTOMERS]["status"] == "success", (
            f"Relationship test failed: "
            f"{results[TEST_RELATIONSHIPS_ORDERS_CUSTOMERS].get('error')}"
        )

    def test_per_node_skip_produces_no_test_results(self, per_node_orchestrator):
        """SKIP + PER_NODE: no test results, backward compatible."""
        from prefect import flow

        orch = per_node_orchestrator(
            execution_mode=ExecutionMode.PER_NODE,
            concurrency=1,
            test_strategy=TestStrategy.SKIP,
        )

        @flow
        def test_flow():
            return orch.run_build()

        results = test_flow()

        test_ids = {k for k in results if k.startswith("test.")}
        assert test_ids == set()
        assert set(results.keys()) == ALL_EXECUTABLE
