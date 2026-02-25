#!/usr/bin/env python
"""Benchmark PrefectDbtOrchestrator vs PrefectDbtRunner.

Creates a 5-layer × 10-model synthetic dbt project backed by Postgres (50 nodes
total) and times each configuration once.  This is intentionally a wall-clock
timer, not a statistical micro-benchmark, so the numbers reflect what users
actually experience.

Each execution group (runner, PER_WAVE, PER_NODE) gets its own Postgres schema
so runs are isolated without requiring separate database connections.

Postgres connection defaults match the GitHub Actions service definition.
Override via environment variables: BENCH_PG_HOST, BENCH_PG_PORT,
BENCH_PG_USER, BENCH_PG_PASSWORD, BENCH_PG_DBNAME.

Usage
-----
    uv run python benches/bench_orchestrator.py
    uv run python benches/bench_orchestrator.py --output results.json
    uv run python benches/bench_orchestrator.py --output pr.json --baseline main.json
    uv run python benches/bench_orchestrator.py --markdown-out comment.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml
from dbt.cli.main import dbtRunner
from prefect_dbt.core._orchestrator import (
    ExecutionMode,
    PrefectDbtOrchestrator,
    TestStrategy,
)
from prefect_dbt.core.runner import PrefectDbtRunner
from prefect_dbt.core.settings import PrefectDbtSettings

from prefect import flow

# ---------------------------------------------------------------------------
# Project configuration
# ---------------------------------------------------------------------------

LAYERS = 5  # dependency layers  (= number of PER_WAVE dbt invocations for "all")
WIDTH = 10  # models per layer   (total = LAYERS * WIDTH = 50 nodes)

# Subset selector: first layer only (1 wave, WIDTH nodes, no dependencies)
SUBSET_SELECT = "path:models/layer_0"

# PER_NODE concurrency — matches the dbt thread count so all execution modes
# get the same degree of parallelism.
PER_NODE_CONCURRENCY = WIDTH

# ---------------------------------------------------------------------------
# Postgres connection defaults
# ---------------------------------------------------------------------------

_PG_HOST = os.environ.get("BENCH_PG_HOST", "localhost")
_PG_PORT = int(os.environ.get("BENCH_PG_PORT", "5432"))
_PG_USER = os.environ.get("BENCH_PG_USER", "postgres")
_PG_PASSWORD = os.environ.get("BENCH_PG_PASSWORD", "postgres")
_PG_DBNAME = os.environ.get("BENCH_PG_DBNAME", "bench")


# ---------------------------------------------------------------------------
# Project setup helpers
# ---------------------------------------------------------------------------


def _write_project_files(project_dir: Path) -> None:
    """Write dbt_project.yml and model SQL files (no profiles.yml)."""
    for layer in range(LAYERS):
        layer_dir = project_dir / "models" / f"layer_{layer}"
        layer_dir.mkdir(parents=True)
        for w in range(WIDTH):
            if layer == 0:
                sql = "SELECT 1 AS id"
            else:
                sql = f"SELECT id FROM {{{{ ref('l{layer - 1}_m{w}') }}}}"
            (layer_dir / f"l{layer}_m{w}.sql").write_text(sql)

    (project_dir / "dbt_project.yml").write_text(
        yaml.dump(
            {
                "name": "dbt_bench",
                "version": "1.0.0",
                "config-version": 2,
                "profile": "bench",
                "model-paths": ["models"],
                "models": {"dbt_bench": {"+materialized": "table"}},
            }
        )
    )


def _write_profiles(profiles_dir: Path, schema: str) -> None:
    profiles_dir.mkdir(parents=True, exist_ok=True)
    (profiles_dir / "profiles.yml").write_text(
        yaml.dump(
            {
                "bench": {
                    "target": "dev",
                    "outputs": {
                        "dev": {
                            "type": "postgres",
                            "host": _PG_HOST,
                            "port": _PG_PORT,
                            "user": _PG_USER,
                            "password": _PG_PASSWORD,
                            "dbname": _PG_DBNAME,
                            "schema": schema,
                            "threads": WIDTH,
                        }
                    },
                }
            }
        )
    )


def setup_project(root: Path) -> tuple[Path, Path, Path, Path]:
    """
    Create the shared project tree and three isolated environments.

    Each group writes to its own Postgres schema so runs don't interfere.

    Returns
    -------
    project_dir, runner_profiles, per_wave_profiles, per_node_profiles
    """
    project_dir = root / "project"
    project_dir.mkdir()
    _write_project_files(project_dir)

    for name in ("runner", "per_wave", "per_node"):
        _write_profiles(root / f"profiles_{name}", schema=f"bench_{name}")

    # Run dbt parse once (parse doesn't connect to the database).
    # Reuse the manifest across all three groups.
    _write_profiles(root / "profiles_parse", schema="bench_parse")
    result = dbtRunner().invoke(
        [
            "parse",
            "--project-dir",
            str(project_dir),
            "--profiles-dir",
            str(root / "profiles_parse"),
        ]
    )
    if not result.success:
        raise RuntimeError(f"dbt parse failed: {result.exception}")

    manifest_path = project_dir / "target" / "manifest.json"
    assert manifest_path.exists(), "dbt parse did not produce manifest.json"

    return (
        project_dir,
        root / "profiles_runner",
        root / "profiles_per_wave",
        root / "profiles_per_node",
    )


# ---------------------------------------------------------------------------
# Timing helpers
# ---------------------------------------------------------------------------


@dataclass
class BenchmarkResult:
    name: str
    elapsed_s: float
    status: str  # "OK" or "FAIL"
    error: str | None = None


def _time(name: str, fn) -> BenchmarkResult:
    """Time fn(); inspect the return value for node-level dbt failures."""
    start = time.perf_counter()
    try:
        result = fn()
        elapsed = time.perf_counter() - start

        # run_build() returns a dict; check for failed nodes
        if isinstance(result, dict):
            failed = [
                uid
                for uid, r in result.items()
                if isinstance(r, dict) and r.get("status") == "error"
            ]
            if failed:
                return BenchmarkResult(
                    name=name,
                    elapsed_s=elapsed,
                    status="FAIL",
                    error=f"dbt build failed for nodes: {failed}",
                )

        return BenchmarkResult(name=name, elapsed_s=elapsed, status="OK")
    except Exception as exc:
        elapsed = time.perf_counter() - start
        return BenchmarkResult(
            name=name, elapsed_s=elapsed, status="FAIL", error=str(exc)
        )


# ---------------------------------------------------------------------------
# Benchmark scenarios
# ---------------------------------------------------------------------------


def run_benchmarks(
    project_dir: Path,
    manifest_path: Path,
    runner_profiles: Path,
    per_wave_profiles: Path,
    per_node_profiles: Path,
) -> list[BenchmarkResult]:
    results: list[BenchmarkResult] = []

    # -- PrefectDbtRunner -------------------------------------------------
    # Calls dbt build in a single invocation; dbt handles DAG ordering.

    def _runner(select: str | None = None) -> None:
        s = PrefectDbtSettings(project_dir=project_dir, profiles_dir=runner_profiles)
        r = PrefectDbtRunner(settings=s, raise_on_failure=True)
        args = ["build"]
        if select:
            args += ["--select", select]
        r.invoke(args)

    results.append(_time("runner / select=None (all)", lambda: _runner()))
    results.append(
        _time(f"runner / select={SUBSET_SELECT}", lambda: _runner(SUBSET_SELECT))
    )

    # -- Orchestrator PER_WAVE --------------------------------------------
    # One dbt invocation per topological wave (LAYERS invocations for "all").

    def _per_wave(select: str | None = None):
        s = PrefectDbtSettings(project_dir=project_dir, profiles_dir=per_wave_profiles)
        orch = PrefectDbtOrchestrator(
            settings=s,
            manifest_path=manifest_path,
            execution_mode=ExecutionMode.PER_WAVE,
            test_strategy=TestStrategy.SKIP,
            create_summary_artifact=False,
            write_run_results=False,
        )
        return orch.run_build(select=select)

    results.append(
        _time("orchestrator / select=None (all) / PER_WAVE", lambda: _per_wave())
    )
    results.append(
        _time(
            f"orchestrator / select={SUBSET_SELECT} / PER_WAVE",
            lambda: _per_wave(SUBSET_SELECT),
        )
    )

    # -- Orchestrator PER_NODE --------------------------------------------
    # One dbt invocation per node (LAYERS*WIDTH invocations for "all").
    # run_build() must be called inside a @flow.

    @flow
    def _per_node_flow(select: str | None = None):  # type: ignore[misc]
        s = PrefectDbtSettings(project_dir=project_dir, profiles_dir=per_node_profiles)
        orch = PrefectDbtOrchestrator(
            settings=s,
            manifest_path=manifest_path,
            execution_mode=ExecutionMode.PER_NODE,
            concurrency=PER_NODE_CONCURRENCY,
            test_strategy=TestStrategy.SKIP,
            create_summary_artifact=False,
            write_run_results=False,
        )
        return orch.run_build(select=select)

    results.append(
        _time("orchestrator / select=None (all) / PER_NODE", lambda: _per_node_flow())
    )
    results.append(
        _time(
            f"orchestrator / select={SUBSET_SELECT} / PER_NODE",
            lambda: _per_node_flow(SUBSET_SELECT),
        )
    )

    return results


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

_COL_NAME = 54
_COL_TIME = 9
_COL_STATUS = 8
_RULE = "-" * (_COL_NAME + _COL_TIME + _COL_STATUS + 2)


def format_text_table(results: list[BenchmarkResult]) -> str:
    header = f"{'Name':<{_COL_NAME}} {'Time':>{_COL_TIME}} {'Status':>{_COL_STATUS}}"
    lines = ["=" * 72, "BENCHMARK RESULTS", "=" * 72, header, _RULE]
    for r in results:
        time_str = f"{r.elapsed_s:.3f}s"
        lines.append(
            f"{r.name:<{_COL_NAME}} {time_str:>{_COL_TIME}} {r.status:>{_COL_STATUS}}"
        )
        if r.error:
            for chunk in _wrap(f"  Error: {r.error}", 70):
                lines.append(chunk)
    lines.append(_RULE)
    return "\n".join(lines)


def _wrap(text: str, width: int) -> list[str]:
    if len(text) <= width:
        return [text]
    out = []
    while len(text) > width:
        split = text.rfind(" ", 0, width)
        if split == -1:
            split = width
        out.append(text[:split])
        text = "  " + text[split:].lstrip()
    if text:
        out.append(text)
    return out


def format_markdown(
    results: list[BenchmarkResult],
    baseline: list[dict] | None,
    sha: str | None,
) -> str:
    node_count = LAYERS * WIDTH
    lines = ["## dbt Orchestrator Benchmark Results"]
    if sha:
        lines.append(f"\nCommit: `{sha[:12]}`")
    lines.append(
        f"\nProject: **{LAYERS} layers × {WIDTH} models = {node_count} nodes** "
        f"(Postgres, `concurrency={PER_NODE_CONCURRENCY}` for PER_NODE)"
    )

    block = "```\n" + format_text_table(results) + "\n```"
    lines.append(
        f"\n<details open>\n<summary>Results</summary>\n\n{block}\n\n</details>"
    )

    if baseline:
        by_name = {r["name"]: r for r in baseline}
        rows = []
        for r in results:
            b = by_name.get(r.name)
            if not b:
                continue
            pct = (r.elapsed_s - b["elapsed_s"]) / b["elapsed_s"] * 100
            sign = "+" if pct >= 0 else ""
            flag = " 🚨" if pct > 15 else (" ⚠️" if pct > 5 else "")
            rows.append(
                f"| `{r.name}` | {b['elapsed_s']:.3f}s | "
                f"{r.elapsed_s:.3f}s | {sign}{pct:.1f}%{flag} |"
            )
        if rows:
            table = (
                "| Benchmark | main | PR | Change |\n"
                "|---|---|---|---|\n" + "\n".join(rows)
            )
            lines.append(
                "\n<details>\n<summary>Comparison vs main</summary>\n\n"
                + table
                + "\n\n</details>"
            )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", metavar="JSON", help="Save results to JSON")
    parser.add_argument(
        "--baseline", metavar="JSON", help="Load baseline results from JSON"
    )
    parser.add_argument(
        "--markdown-out", metavar="MD", help="Write Markdown comment body"
    )
    parser.add_argument("--sha", help="Git SHA to include in the comment")
    args = parser.parse_args()

    baseline: list[dict] | None = None
    if args.baseline:
        p = Path(args.baseline)
        if p.exists():
            baseline = json.loads(p.read_text()).get("results")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        print("Setting up benchmark project …", flush=True)
        project_dir, runner_profiles, per_wave_profiles, per_node_profiles = (
            setup_project(root)
        )
        manifest_path = project_dir / "target" / "manifest.json"

        print(
            f"Running benchmarks ({LAYERS} layers × {WIDTH} models = {LAYERS * WIDTH} nodes) …\n",
            flush=True,
        )
        results = run_benchmarks(
            project_dir,
            manifest_path,
            runner_profiles,
            per_wave_profiles,
            per_node_profiles,
        )

    table = format_text_table(results)
    print(table)

    if args.output:
        Path(args.output).write_text(
            json.dumps({"results": [asdict(r) for r in results]}, indent=2)
        )
        print(f"\nResults saved to {args.output}", flush=True)

    if args.markdown_out:
        md = format_markdown(results, baseline, args.sha)
        Path(args.markdown_out).write_text(md)
        print(f"Markdown written to {args.markdown_out}", flush=True)

    return 1 if any(r.status == "FAIL" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
