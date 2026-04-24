"""
Benchmark: count_flow_runs before vs after the EXISTS-to-JOIN rewrite.

What is measured
----------------
Both paths are full end-to-end calls that include Python query construction,
SQLAlchemy compilation, and SQL execution — exactly what happens in production
on every /api/flow_runs/count request.

  before_pr  --  verbatim pre-PR body of count_flow_runs: builds a
                 SELECT count(*) and routes it through _apply_flow_run_filters,
                 which appends one correlated EXISTS subquery per active filter.

  after_pr   --  the current count_flow_runs (this PR): same entry point,
                 but the fast path builds explicit JOINs instead of EXISTS
                 when task_run_filter is absent.

The only difference between the two functions is the rewritten block in
count_flow_runs.  All other overhead (async dispatch, ORM session, scalar fetch)
is identical and present in both timings.

Methodology
-----------
* Filters: four FK dimensions exercised independently and in combination.
* Data: matching rows carry all four target FKs; decoy rows carry decoy FKs.
  Both deployment_id / work_queue_id / flow_id are indexed (FK index pattern).
* Correctness: before and after must return the same count == n_matching.
* Warmup: 20 paired calls per scenario to reach steady-state page-cache.
* Sampling: 200 paired observations per scenario (100 before, 100 after),
  interleaved one-for-one so both paths see identical cache state each rep.
* Statistics reported: p50, p95, mean, stddev.  Speedup = mean_before / mean_after.

Run with:
    # SQLite (default — one isolated file per scenario):
    uv run python benches/bench_count_flow_runs.py

    # PostgreSQL (pass any SQLAlchemy-compatible async URL):
    uv run python benches/bench_count_flow_runs.py \\
        --db-url postgresql+asyncpg://bench:bench@localhost/prefect_bench
"""
import argparse
import asyncio
import datetime
import os
import statistics
import time
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import select

from prefect.server import models, schemas
from prefect.server.database import dependencies as _db_deps
from prefect.server.database.dependencies import provide_database_interface
from prefect.server.models.flow_runs import _apply_flow_run_filters

_DB_BASE = os.path.join(os.path.dirname(__file__), "_bench_cfr")
WARMUP = 20
REPS = 100


async def _count_flow_runs_before_pr(
    db,
    session,
    flow_filter=None,
    flow_run_filter=None,
    task_run_filter=None,
    deployment_filter=None,
    work_pool_filter=None,
    work_queue_filter=None,
):
    """Verbatim pre-PR body of count_flow_runs (no fast path)."""
    query = select(sa.func.count(None)).select_from(db.FlowRun)
    query = await _apply_flow_run_filters(
        db,
        query,
        flow_filter=flow_filter,
        flow_run_filter=flow_run_filter,
        task_run_filter=task_run_filter,
        deployment_filter=deployment_filter,
        work_pool_filter=work_pool_filter,
        work_queue_filter=work_queue_filter,
    )
    result = await session.execute(query)
    return result.scalar_one()


async def _setup_entities(session):
    target_flow = await models.flows.create_flow(
        session=session,
        flow=schemas.core.Flow(name=f"bench-flow-target-{uuid4()}"),
    )
    decoy_flow = await models.flows.create_flow(
        session=session,
        flow=schemas.core.Flow(name=f"bench-flow-decoy-{uuid4()}"),
    )
    target_dep = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name=f"bench-dep-target-{uuid4()}", flow_id=target_flow.id
        ),
    )
    decoy_dep = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name=f"bench-dep-decoy-{uuid4()}", flow_id=decoy_flow.id
        ),
    )
    target_wp = await models.workers.create_work_pool(
        session=session,
        work_pool=schemas.actions.WorkPoolCreate(name=f"bench-wp-target-{uuid4()}"),
    )
    decoy_wp = await models.workers.create_work_pool(
        session=session,
        work_pool=schemas.actions.WorkPoolCreate(name=f"bench-wp-decoy-{uuid4()}"),
    )
    target_wq = await models.workers.create_work_queue(
        session=session,
        work_pool_id=target_wp.id,
        work_queue=schemas.actions.WorkQueueCreate(name=f"bench-wq-target-{uuid4()}"),
    )
    decoy_wq = await models.workers.create_work_queue(
        session=session,
        work_pool_id=decoy_wp.id,
        work_queue=schemas.actions.WorkQueueCreate(name=f"bench-wq-decoy-{uuid4()}"),
    )
    await session.flush()
    return (
        target_flow.id,
        target_dep.id,
        target_wp.id,
        target_wq.id,
        decoy_flow.id,
        decoy_dep.id,
        decoy_wq.id,
    )


async def _seed(session, db, ids, n_total, n_matching):
    target_flow_id, target_dep_id, _, target_wq_id = ids[:4]
    decoy_flow_id, decoy_dep_id, decoy_wq_id = ids[4:]
    _now = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
    base = {
        "created": _now,
        "updated": _now,
        "run_count": 0,
        "total_run_time": datetime.timedelta(0),
        "parameters": {},
        "tags": [],
        "context": {},
        "empirical_policy": {},
        "auto_scheduled": 0,
    }
    matching_rows = [
        {
            **base,
            "id": str(uuid4()),
            "name": f"run-match-{i}",
            "flow_id": str(target_flow_id),
            "deployment_id": str(target_dep_id),
            "work_queue_id": str(target_wq_id),
        }
        for i in range(n_matching)
    ]
    decoy_rows = [
        {
            **base,
            "id": str(uuid4()),
            "name": f"run-decoy-{i}",
            "flow_id": str(decoy_flow_id),
            "deployment_id": str(decoy_dep_id),
            "work_queue_id": str(decoy_wq_id),
        }
        for i in range(n_total - n_matching)
    ]
    all_rows = matching_rows + decoy_rows
    chunk = 500
    for start in range(0, len(all_rows), chunk):
        await session.execute(
            db.FlowRun.__table__.insert(), all_rows[start : start + chunk]
        )


async def run_scenario(
    n_total: int, n_matching: int, db_url: str | None = None
) -> list[dict]:
    if db_url is None:
        db_path = f"{_DB_BASE}_{n_total}.db"
        if os.path.exists(db_path):
            os.remove(db_path)
        db_url = f"sqlite+aiosqlite:///{db_path}"

    os.environ["PREFECT_API_DATABASE_CONNECTION_URL"] = db_url
    _db_deps.MODELS_DEPENDENCIES["database_config"] = None
    db = provide_database_interface()
    await db.create_db()

    engine = await db.engine()
    async with engine.begin() as conn:
        for col in ("deployment_id", "work_queue_id", "flow_id"):
            await conn.execute(
                sa.text(
                    f"CREATE INDEX IF NOT EXISTS ix_flow_run_{col}"
                    f" ON flow_run ({col})"
                )
            )
        # Non-SQLite backends share one DB across scenarios; clear previous data.
        if "sqlite" not in db_url:
            for tbl in ("flow_run", "deployment", "work_queue", "work_pool", "flow"):
                await conn.execute(sa.text(f"DELETE FROM {tbl}"))

    async with db.session_context(begin_transaction=True) as session:
        ids = await _setup_entities(session)
        await _seed(session, db, ids, n_total, n_matching)

    target_flow_id, target_dep_id, target_wp_id, target_wq_id = ids[:4]

    dep_f = schemas.filters.DeploymentFilter(
        id=schemas.filters.DeploymentFilterId(any_=[target_dep_id])
    )
    wq_f = schemas.filters.WorkQueueFilter(
        id=schemas.filters.WorkQueueFilterId(any_=[target_wq_id])
    )
    wp_f = schemas.filters.WorkPoolFilter(
        id=schemas.filters.WorkPoolFilterId(any_=[target_wp_id])
    )
    flow_f = schemas.filters.FlowFilter(
        id=schemas.filters.FlowFilterId(any_=[target_flow_id])
    )

    filter_scenarios = [
        ("deployment", dict(deployment_filter=dep_f)),
        ("work_queue", dict(work_queue_filter=wq_f)),
        ("work_pool", dict(work_pool_filter=wp_f)),
        ("flow", dict(flow_filter=flow_f)),
        (
            "all four",
            dict(
                deployment_filter=dep_f,
                work_queue_filter=wq_f,
                work_pool_filter=wp_f,
                flow_filter=flow_f,
            ),
        ),
    ]

    results = []

    async with db.session_context() as session:
        for label, kwargs in filter_scenarios:
            # Correctness: both paths must return the same count.
            before_count = await _count_flow_runs_before_pr(
                db, session, **kwargs
            )
            after_count = await models.flow_runs.count_flow_runs(
                session=session, **kwargs
            )
            assert before_count == after_count == n_matching, (
                f"[{label}] count mismatch: "
                f"before={before_count}, after={after_count}, "
                f"expected={n_matching}"
            )

            # Warmup: steady-state page-cache, SQLAlchemy compilation cache.
            for _ in range(WARMUP):
                await _count_flow_runs_before_pr(db, session, **kwargs)
                await models.flow_runs.count_flow_runs(session=session, **kwargs)

            # Interleaved sampling: one before-PR call then one after-PR call
            # per rep, so both always see the same cache state.
            before_times: list[float] = []
            after_times: list[float] = []
            for _ in range(REPS):
                t0 = time.perf_counter()
                await _count_flow_runs_before_pr(db, session, **kwargs)
                before_times.append((time.perf_counter() - t0) * 1e3)

                t0 = time.perf_counter()
                await models.flow_runs.count_flow_runs(session=session, **kwargs)
                after_times.append((time.perf_counter() - t0) * 1e3)

            results.append(
                {
                    "label": label,
                    "before_p50": statistics.median(before_times),
                    "before_p95": statistics.quantiles(before_times, n=20)[18],
                    "before_mean": statistics.mean(before_times),
                    "before_sd": statistics.stdev(before_times),
                    "after_p50": statistics.median(after_times),
                    "after_p95": statistics.quantiles(after_times, n=20)[18],
                    "after_mean": statistics.mean(after_times),
                    "after_sd": statistics.stdev(after_times),
                    "speedup": statistics.mean(before_times)
                    / statistics.mean(after_times),
                }
            )

    return results


def _fmt(mean: float, sd: float) -> str:
    return f"{mean:6.2f} +/- {sd:5.2f}"


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="count_flow_runs before/after benchmark"
    )
    parser.add_argument(
        "--db-url",
        default=None,
        metavar="URL",
        help=(
            "Async SQLAlchemy database URL.  Omit for per-scenario SQLite files. "
            "PostgreSQL example: postgresql+asyncpg://bench:bench@localhost/prefect_bench"
        ),
    )
    args = parser.parse_args()

    scenarios = [
        (1_000, 100),
        (10_000, 1_000),
        (100_000, 5_000),
    ]

    hdr = (
        f"{'':12}  "
        f"{'before PR':^38}  "
        f"{'after PR':^38}  "
        f"{'speedup':>7}"
    )
    sub = (
        f"{'filter':>12}  "
        f"{'p50':>6} {'p95':>6} {'mean+/-sd':>16}  "
        f"{'p50':>6} {'p95':>6} {'mean+/-sd':>16}  "
        f"{'(mean)':>7}"
    )

    for n_total, n_matching in scenarios:
        print(
            f"\n-- {n_total:,} rows  ({n_matching:,} matching,"
            f" {n_total - n_matching:,} decoy)"
            f"  n={REPS} interleaved pairs  --"
        )
        print(hdr)
        print(sub)
        print("-" * len(sub))
        print(f"  seeding {n_total:,} rows...", flush=True)
        results = await run_scenario(n_total, n_matching, db_url=args.db_url)
        for r in results:
            print(
                f"{r['label']:>12}  "
                f"{r['before_p50']:>6.2f} {r['before_p95']:>6.2f}"
                f" {_fmt(r['before_mean'], r['before_sd']):>16}  "
                f"{r['after_p50']:>6.2f} {r['after_p95']:>6.2f}"
                f" {_fmt(r['after_mean'], r['after_sd']):>16}  "
                f"{r['speedup']:>6.1f}x"
            )


if __name__ == "__main__":
    asyncio.run(main())
