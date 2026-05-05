"""
Benchmark: read_block_schemas before vs after the checksum-index hoist.

What is measured
----------------
Both paths perform the same reconstruction work on an identical
block_schemas_with_references result set.

  before_pr  --  verbatim pre-PR lookup: _find_block_schema_via_checksum
                 always walks the full flat list with next().  Reconstructing
                 M root schemas each with K child references costs O(M * K * N)
                 where N is the size of the result set.

  after_pr   --  this PR: checksum_index is built once (O(N)) then every
                 child lookup is O(1).  Total cost is O(N + M * K).

Data
----
A synthetic block_schemas_with_references list is built in memory — no
database required.  Each scenario seeds N BlockSchema rows with unique
checksums.  M=N root schemas each reference one child schema, so the
reconstruction loop calls _find_block_schema_via_checksum M times per
root.  The ratio between before/after speedup scales with N.

Methodology
-----------
* N values: 10, 50, 100, 500, 1 000.
* Correctness: before and after must return the same schema object.
* Warmup: 50 paired iterations per scenario.
* Sampling: 500 paired observations (before then after), interleaved
  one-for-one so both paths share the same Python object cache state.
* Statistics: p50, p95, mean, stddev (all in milliseconds).
  Speedup = mean_before / mean_after.

Run with:
    uv run python benches/bench_block_schemas.py
"""

import statistics
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from prefect.server.schemas.core import BlockSchema

WARMUP = 50
REPS = 500

# ---------------------------------------------------------------------------
# Pre-PR verbatim: _find_block_schema_via_checksum without index support.
# The before-PR function always performed an O(N) next() scan.
# ---------------------------------------------------------------------------


def _find_block_schema_via_checksum_before(
    block_schemas_with_references: List[Tuple[BlockSchema, Optional[str], Any]],
    checksum: str,
) -> Optional[BlockSchema]:
    return next(
        (
            block_schema
            for block_schema, _, _ in block_schemas_with_references
            if block_schema.checksum == checksum
        ),
        None,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_schema(checksum: str) -> BlockSchema:
    return BlockSchema(
        id=uuid.uuid4(),
        checksum=checksum,
        fields={"block_schema_references": {}},
        block_type_id=uuid.uuid4(),
        capabilities=[],
        version="1.0",
    )


def _build_rows(n: int) -> List[Tuple[BlockSchema, None, None]]:
    """Build a flat result set of N BlockSchema rows with unique checksums."""
    return [(_make_schema(f"sha256:{i:08x}"), None, None) for i in range(n)]


def _build_index_after_pr(
    rows: List[Tuple[BlockSchema, None, None]],
) -> Dict[str, BlockSchema]:
    """Verbatim index-build loop from read_block_schemas (this PR)."""
    checksum_index: Dict[str, BlockSchema] = {}
    for bs, _, _ in rows:
        if bs.checksum is not None and bs.checksum not in checksum_index:
            checksum_index[bs.checksum] = bs
    return checksum_index


# ---------------------------------------------------------------------------
# Scenario runner
# ---------------------------------------------------------------------------


def run_scenario(n: int) -> dict:
    """
    Simulate reconstructing N root schemas each needing one child lookup.

    before_pr: N calls to _find_block_schema_via_checksum_before (linear scan).
    after_pr:  one index build + N calls to dict.get().
    """
    rows = _build_rows(n)
    # Every schema is both a potential root and a lookup target.
    # Pick the middle schema as the repeated lookup target so the linear
    # scan has to traverse roughly N/2 rows on average.
    target_checksum = rows[n // 2][0].checksum

    # Correctness: both paths must return the same object.
    before_result = _find_block_schema_via_checksum_before(rows, target_checksum)
    index = _build_index_after_pr(rows)
    after_result = index.get(target_checksum)
    assert before_result is after_result, (
        f"[n={n}] result mismatch: before={before_result}, after={after_result}"
    )

    # Warmup
    for _ in range(WARMUP):
        for bs, _, _ in rows:
            _find_block_schema_via_checksum_before(rows, bs.checksum)
        idx = _build_index_after_pr(rows)
        for bs, _, _ in rows:
            idx.get(bs.checksum)

    # Interleaved sampling: one full before-PR pass then one full after-PR pass
    # per rep, so both always see the same Python GC / cache state.
    before_times: list[float] = []
    after_times: list[float] = []

    for _ in range(REPS):
        t0 = time.perf_counter()
        for bs, _, _ in rows:
            _find_block_schema_via_checksum_before(rows, bs.checksum)
        before_times.append((time.perf_counter() - t0) * 1e3)

        t0 = time.perf_counter()
        idx = _build_index_after_pr(rows)
        for bs, _, _ in rows:
            idx.get(bs.checksum)
        after_times.append((time.perf_counter() - t0) * 1e3)

    return {
        "n": n,
        "before_p50": statistics.median(before_times),
        "before_p95": statistics.quantiles(before_times, n=20)[18],
        "before_mean": statistics.mean(before_times),
        "before_sd": statistics.stdev(before_times),
        "after_p50": statistics.median(after_times),
        "after_p95": statistics.quantiles(after_times, n=20)[18],
        "after_mean": statistics.mean(after_times),
        "after_sd": statistics.stdev(after_times),
        "speedup": statistics.mean(before_times) / statistics.mean(after_times),
    }


def _fmt(mean: float, sd: float) -> str:
    return f"{mean:8.3f} +/- {sd:6.3f}"


def main() -> None:
    ns = [10, 50, 100, 500, 1_000]

    hdr = f"{'':>6}  {'before PR (ms)':^38}  {'after PR (ms)':^38}  {'speedup':>7}"
    sub = (
        f"{'N':>6}  "
        f"{'p50':>6} {'p95':>8} {'mean+/-sd':>20}  "
        f"{'p50':>6} {'p95':>8} {'mean+/-sd':>20}  "
        f"{'(mean)':>7}"
    )
    sep = "-" * len(sub)

    print(
        f"\nread_block_schemas · checksum lookup  "
        f"(n={REPS} reps + {WARMUP} warmup per scenario)\n"
    )
    print(hdr)
    print(sub)
    print(sep)

    for n in ns:
        r = run_scenario(n)
        print(
            f"{r['n']:>6}  "
            f"{r['before_p50']:>6.3f} {r['before_p95']:>8.3f}"
            f" {_fmt(r['before_mean'], r['before_sd']):>20}  "
            f"{r['after_p50']:>6.3f} {r['after_p95']:>8.3f}"
            f" {_fmt(r['after_mean'], r['after_sd']):>20}  "
            f"{r['speedup']:>6.1f}x"
        )


if __name__ == "__main__":
    main()
