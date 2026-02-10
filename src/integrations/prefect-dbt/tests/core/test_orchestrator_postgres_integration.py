"""Integration tests for PrefectDbtOrchestrator PER_NODE mode against Postgres.

These tests exercise real concurrent execution (concurrency > 1) which is not
possible with DuckDB's single-writer limitation.  A Postgres service must be
available (default: localhost:5432, user=prefect, password=prefect, db=dbt_test).

Connection settings can be overridden with environment variables:
    PG_HOST, PG_PORT, PG_USER, PG_PASSWORD, PG_DATABASE

Run locally:
    docker run --rm -d -p 5433:5432 \
        -e POSTGRES_USER=prefect -e POSTGRES_PASSWORD=prefect \
        -e POSTGRES_DB=dbt_test --name dbt-test-pg postgres:16
    PG_PORT=5433 uv run --group integration pytest tests/core/test_orchestrator_postgres_integration.py -m integration -v
    docker stop dbt-test-pg
"""

import os
import shutil
from pathlib import Path
from uuid import uuid4

import pytest
import yaml
from dbt.cli.main import dbtRunner

psycopg2 = pytest.importorskip(
    "psycopg2", reason="psycopg2 required for Postgres integration tests"
)
pytest.importorskip(
    "dbt.adapters.postgres",
    reason="dbt-postgres required for Postgres integration tests",
)

from prefect_dbt.core._orchestrator import (  # noqa: E402
    ExecutionMode,
    PrefectDbtOrchestrator,
)
from prefect_dbt.core.settings import PrefectDbtSettings  # noqa: E402

pytestmark = pytest.mark.integration

DBT_TEST_PROJECT = Path(__file__).resolve().parent.parent / "dbt_test_project"

PG_HOST = os.environ.get("PG_HOST", "localhost")
PG_PORT = int(os.environ.get("PG_PORT", "5432"))
PG_USER = os.environ.get("PG_USER", "prefect")
PG_PASSWORD = os.environ.get("PG_PASSWORD", "prefect")
PG_DATABASE = os.environ.get("PG_DATABASE", "dbt_test")

SEED_CUSTOMERS = "seed.test_project.customers"
SEED_ORDERS = "seed.test_project.orders"
STG_CUSTOMERS = "model.test_project.stg_customers"
STG_ORDERS = "model.test_project.stg_orders"
CUSTOMER_SUMMARY = "model.test_project.customer_summary"
INT_ORDERS_ENRICHED = "model.test_project.int_orders_enriched"

ALL_EXECUTABLE = {
    SEED_CUSTOMERS,
    SEED_ORDERS,
    STG_CUSTOMERS,
    STG_ORDERS,
    CUSTOMER_SUMMARY,
}


def _pg_connect():
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASSWORD,
        dbname=PG_DATABASE,
    )


@pytest.fixture(scope="session")
def pg_dbt_project(tmp_path_factory):
    """Set up a real dbt project with Postgres and a parsed manifest.

    Session-scoped: copies the test project to a temp directory, creates a
    unique schema in Postgres, writes profiles.yml, and runs ``dbt parse``.
    """
    schema_name = f"dbt_test_{uuid4().hex[:8]}"
    project_dir = tmp_path_factory.mktemp("dbt_project_pg")

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
                    "type": "postgres",
                    "host": PG_HOST,
                    "port": PG_PORT,
                    "user": PG_USER,
                    "password": PG_PASSWORD,
                    "dbname": PG_DATABASE,
                    "schema": schema_name,
                    "threads": 4,
                }
            },
        }
    }
    profiles_path = project_dir / "profiles.yml"
    profiles_path.write_text(yaml.dump(profiles))

    conn = _pg_connect()
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
    finally:
        conn.close()

    dbt_args = [
        "--project-dir",
        str(project_dir),
        "--profiles-dir",
        str(project_dir),
    ]

    runner = dbtRunner()
    result = runner.invoke(["parse", *dbt_args])
    assert result.success, f"dbt parse failed: {result.exception}"

    manifest_path = project_dir / "target" / "manifest.json"
    assert manifest_path.exists(), "manifest.json not generated"

    yield {
        "project_dir": project_dir,
        "profiles_dir": project_dir,
        "manifest_path": manifest_path,
        "schema": schema_name,
    }

    conn = _pg_connect()
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE")
    finally:
        conn.close()


def _make_orchestrator(pg_dbt_project, **kwargs):
    settings = PrefectDbtSettings(
        project_dir=pg_dbt_project["project_dir"],
        profiles_dir=pg_dbt_project["profiles_dir"],
    )
    return PrefectDbtOrchestrator(
        settings=settings,
        manifest_path=pg_dbt_project["manifest_path"],
        **kwargs,
    )


class TestPerNodePostgresConcurrency:
    """Integration tests for PER_NODE mode with real concurrent execution on Postgres."""

    def test_concurrent_full_build(self, pg_dbt_project):
        """All 5 nodes succeed with concurrency=4."""
        from prefect import flow

        orchestrator = _make_orchestrator(
            pg_dbt_project,
            execution_mode=ExecutionMode.PER_NODE,
            concurrency=4,
        )

        @flow
        def test_flow():
            return orchestrator.run_build()

        results = test_flow()

        assert set(results.keys()) == ALL_EXECUTABLE
        for node_id, result in results.items():
            assert result["status"] == "success", (
                f"{node_id} failed: {result.get('error')}"
            )

    def test_concurrent_nodes_overlap_in_time(self, pg_dbt_project):
        """With concurrency=4, same-wave nodes finish near-simultaneously.

        The orchestrator records ``started_at`` before semaphore acquisition,
        so overlap-based checks are vacuous.  Instead we verify concurrency
        via ``completed_at`` spread: concurrent nodes finish near the same
        time, so the spread of ``completed_at`` within a wave should be
        small relative to each node's execution time.
        """
        from datetime import datetime

        from prefect import flow

        orchestrator = _make_orchestrator(
            pg_dbt_project,
            execution_mode=ExecutionMode.PER_NODE,
            concurrency=4,
        )

        @flow
        def test_flow():
            return orchestrator.run_build()

        results = test_flow()

        def _completion_spread_is_concurrent(node_ids):
            """Check if nodes finished near-simultaneously (concurrent)."""
            timings = [results[nid]["timing"] for nid in node_ids]
            ends = sorted(datetime.fromisoformat(t["completed_at"]) for t in timings)
            durations = [t["duration_seconds"] for t in timings]
            spread = (ends[-1] - ends[0]).total_seconds()
            min_duration = min(durations)
            # Concurrent: spread is small relative to each node's duration
            return spread < min_duration * 0.5

        seeds_concurrent = _completion_spread_is_concurrent(
            [SEED_CUSTOMERS, SEED_ORDERS]
        )
        staging_concurrent = _completion_spread_is_concurrent(
            [STG_CUSTOMERS, STG_ORDERS]
        )

        assert seeds_concurrent or staging_concurrent, (
            "Expected at least one pair of same-wave nodes to execute concurrently. "
            f"Seed timings: {results[SEED_CUSTOMERS]['timing']} vs {results[SEED_ORDERS]['timing']}, "
            f"Staging timings: {results[STG_CUSTOMERS]['timing']} vs {results[STG_ORDERS]['timing']}"
        )

    def test_concurrency_limit_serializes(self, pg_dbt_project):
        """With concurrency=1, within-wave nodes complete sequentially.

        The orchestrator records ``started_at`` before semaphore acquisition,
        so within a wave all tasks share nearly identical ``started_at``
        values.  Instead we verify serialization via ``completed_at`` spread:
        with serial execution the spread equals the execution time of all but
        the first node (>= 50 ms each), whereas parallel execution produces
        near-identical ``completed_at`` values.
        """
        from datetime import datetime

        from prefect import flow

        orchestrator = _make_orchestrator(
            pg_dbt_project,
            execution_mode=ExecutionMode.PER_NODE,
            concurrency=1,
        )

        @flow
        def test_flow():
            return orchestrator.run_build()

        results = test_flow()

        # Within each multi-node wave, serial execution means the spread of
        # completed_at values equals the execution time of all but the first
        # node.  Each dbt command against Postgres takes at least ~50 ms, so
        # the spread should be substantial.  With parallel execution
        # (concurrency=4), same-wave nodes complete within a few ms of each
        # other.
        seed_ends = sorted(
            [
                datetime.fromisoformat(
                    results[SEED_CUSTOMERS]["timing"]["completed_at"]
                ),
                datetime.fromisoformat(results[SEED_ORDERS]["timing"]["completed_at"]),
            ]
        )
        stg_ends = sorted(
            [
                datetime.fromisoformat(
                    results[STG_CUSTOMERS]["timing"]["completed_at"]
                ),
                datetime.fromisoformat(results[STG_ORDERS]["timing"]["completed_at"]),
            ]
        )

        seed_spread = (seed_ends[1] - seed_ends[0]).total_seconds()
        stg_spread = (stg_ends[1] - stg_ends[0]).total_seconds()

        assert seed_spread > 0.05 or stg_spread > 0.05, (
            f"Expected serial execution to spread completion times within waves. "
            f"Seed spread: {seed_spread:.3f}s, staging spread: {stg_spread:.3f}s"
        )

    def test_concurrent_creates_correct_data(self, pg_dbt_project):
        """Postgres has correct row counts and aggregation values after concurrent build."""
        from prefect import flow

        orchestrator = _make_orchestrator(
            pg_dbt_project,
            execution_mode=ExecutionMode.PER_NODE,
            concurrency=4,
        )

        @flow
        def test_flow():
            return orchestrator.run_build()

        results = test_flow()

        for node_id, result in results.items():
            assert result["status"] == "success", (
                f"{node_id} failed: {result.get('error')}"
            )

        schema = pg_dbt_project["schema"]
        conn = _pg_connect()
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT count(*) FROM {schema}.customers")
                assert cur.fetchone()[0] == 5

                cur.execute(f"SELECT count(*) FROM {schema}.orders")
                assert cur.fetchone()[0] == 10

                cur.execute(f"SELECT count(*) FROM {schema}.stg_customers")
                assert cur.fetchone()[0] == 5

                cur.execute(f"SELECT count(*) FROM {schema}.stg_orders")
                assert cur.fetchone()[0] == 10

                cur.execute(f"SELECT count(*) FROM {schema}.customer_summary")
                assert cur.fetchone()[0] == 5

                cur.execute(
                    f"SELECT order_count, total_amount FROM {schema}.customer_summary "
                    f"WHERE customer_name = 'alice'"
                )
                alice = cur.fetchone()
                assert alice[0] == 2  # alice has 2 orders
                assert alice[1] == 300  # 100 + 200
        finally:
            conn.close()

    def test_per_node_ephemeral_not_in_results(self, pg_dbt_project):
        """Ephemeral models are not executed in PER_NODE mode."""
        from prefect import flow

        orchestrator = _make_orchestrator(
            pg_dbt_project,
            execution_mode=ExecutionMode.PER_NODE,
            concurrency=4,
        )

        @flow
        def test_flow():
            return orchestrator.run_build()

        results = test_flow()
        assert INT_ORDERS_ENRICHED not in results
