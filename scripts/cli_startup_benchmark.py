"""Paired, order-balanced CLI startup benchmark gate used by `.github/workflows/benchmarks.yaml`.

`cli-bench run` measures every base command before any head command, so runner timing
drift between the two batches is reported as a code change. This helper instead measures
base and head back to back for each command, alternating which goes first each round,
and judges each command from the paired per-round ratios.

Decision rule for each command, from `rounds` pairs (`base_i`, `head_i`):

- `d_i = ln(head_i / base_i)`; the effect is the geometric-mean ratio `exp(mean(d)) - 1`.
- A one-sided paired t-test (`scipy.stats.ttest_1samp`) tests for a slowdown (or speedup).
- The per-command significance level is `alpha / family_size` (Bonferroni), where
  `family_size` is the number of selected commands across all shards.
- `regression`: effect above `threshold_percent` and slowdown p-value below that level.
- `inconclusive`: effect above the threshold without that evidence; reported, not failed.
- `error`: a failed command, fewer than `min_rounds` complete pairs, or non-positive
  or non-finite timings. Errors fail the gate.

Results are written in the `cli-bench` JSON format (`baseline.json`, `comparison.json`)
along with `cli-benchmark-compare.md` and `cli-benchmark-digest.json`.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from cli_bench.config import (
    BenchmarkCommand,
    BenchmarkConfig,
    BenchmarkResult,
    BenchmarkSuite,
    SuiteMetadata,
    TimingResult,
    get_commands,
    load_project_config,
)
from cli_bench.results import save_suite
from scipy import stats

Status = Literal["ok", "regression", "improvement", "inconclusive", "error"]


class CommandFailedError(Exception):
    """A benchmarked command could not produce a valid measurement."""


@dataclass(frozen=True)
class Target:
    label: Literal["base", "head"]
    root: Path
    sha: str


@dataclass
class CommandMeasurement:
    command: BenchmarkCommand
    base_ms: list[float] = field(default_factory=list)
    head_ms: list[float] = field(default_factory=list)
    orders: list[tuple[str, str]] = field(default_factory=list)
    error: str | None = None


@dataclass(frozen=True)
class Verdict:
    command: str
    status: Status
    reason: str
    rounds: int
    effect_percent: float | None = None
    p_value: float | None = None
    improvement_p_value: float | None = None
    per_command_alpha: float | None = None


RunOnce = Callable[[Target, BenchmarkCommand], float]


def target_command(target: Target, args: list[str]) -> tuple[list[str], dict[str, str]]:
    """Resolve `args` to the target checkout's virtual environment, never the caller's."""
    bin_dir = target.root / ".venv" / "bin"
    executable = bin_dir / args[0]
    if not executable.is_file():
        raise CommandFailedError(f"{executable} does not exist")
    env = {
        **os.environ,
        "VIRTUAL_ENV": str(target.root / ".venv"),
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
    }
    return [str(executable), *args[1:]], env


def time_command(target: Target, command: BenchmarkCommand) -> float:
    """Run one command in the target environment and return its wall time in ms."""
    argv, env = target_command(target, command.args)
    try:
        start = time.perf_counter()
        process = subprocess.run(
            argv,
            cwd=target.root,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=command.timeout,
            check=False,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
    except subprocess.TimeoutExpired:
        raise CommandFailedError(
            f"{target.label}: `{command.name}` timed out after {command.timeout}s"
        )
    if process.returncode != 0:
        stderr_tail = process.stderr.strip()[-500:]
        raise CommandFailedError(
            f"{target.label}: `{command.name}` exited with code {process.returncode}: "
            f"{stderr_tail}"
        )
    return elapsed_ms


def measure_command(
    command: BenchmarkCommand,
    base: Target,
    head: Target,
    rounds: int,
    warmups: int,
    run_once: RunOnce,
) -> CommandMeasurement:
    """Warm up both targets, then take `rounds` adjacent base/head pairs.

    The pair order alternates every round so a steady drift biases base and head equally.
    A failure stops sampling this command and is recorded with the partial samples.
    """
    if rounds < 2 or rounds % 2:
        raise ValueError("rounds must be an even number of at least 2")
    measurement = CommandMeasurement(command=command)
    try:
        for _ in range(warmups):
            run_once(base, command)
            run_once(head, command)
        for round_index in range(rounds):
            order = (base, head) if round_index % 2 == 0 else (head, base)
            samples = {target.label: run_once(target, command) for target in order}
            measurement.orders.append((order[0].label, order[1].label))
            measurement.base_ms.append(samples["base"])
            measurement.head_ms.append(samples["head"])
    except CommandFailedError as exc:
        measurement.error = str(exc)
    return measurement


def _one_sided_p_values(log_ratios: list[float]) -> tuple[float, float]:
    if statistics.pstdev(log_ratios) == 0:
        mean = statistics.fmean(log_ratios)
        return (0.0 if mean > 0 else 1.0), (0.0 if mean < 0 else 1.0)
    slower = stats.ttest_1samp(log_ratios, 0.0, alternative="greater").pvalue
    faster = stats.ttest_1samp(log_ratios, 0.0, alternative="less").pvalue
    return float(slower), float(faster)


def evaluate(
    measurement: CommandMeasurement,
    threshold_percent: float,
    alpha: float,
    family_size: int,
    min_rounds: int,
) -> Verdict:
    name = measurement.command.name
    rounds = min(len(measurement.base_ms), len(measurement.head_ms))
    if measurement.error:
        return Verdict(name, "error", measurement.error, rounds)
    if len(measurement.base_ms) != len(measurement.head_ms) or rounds < min_rounds:
        return Verdict(
            name,
            "error",
            f"insufficient evidence: {len(measurement.base_ms)} base and "
            f"{len(measurement.head_ms)} head samples, need {min_rounds} pairs",
            rounds,
        )
    samples = measurement.base_ms + measurement.head_ms
    if not all(math.isfinite(sample) and sample > 0 for sample in samples):
        return Verdict(
            name, "error", "invalid non-positive or non-finite timing", rounds
        )

    log_ratios = [
        math.log(head / base)
        for base, head in zip(measurement.base_ms, measurement.head_ms)
    ]
    effect_percent = (math.exp(statistics.fmean(log_ratios)) - 1) * 100
    slower_p, faster_p = _one_sided_p_values(log_ratios)
    per_command_alpha = alpha / family_size

    if effect_percent > threshold_percent:
        status: Status = (
            "regression" if slower_p < per_command_alpha else "inconclusive"
        )
    elif effect_percent < -threshold_percent and faster_p < per_command_alpha:
        status = "improvement"
    else:
        status = "ok"
    reason = (
        f"{effect_percent:+.1f}% paired geometric-mean change, "
        f"one-sided p={slower_p:.4g} (slower) vs alpha {per_command_alpha:.4g}"
    )
    return Verdict(
        name,
        status,
        reason,
        rounds,
        effect_percent=effect_percent,
        p_value=slower_p,
        improvement_p_value=faster_p,
        per_command_alpha=per_command_alpha,
    )


def select_commands(
    config_path: Path, shard_index: int, shard_total: int, category: str
) -> tuple[list[BenchmarkCommand], int]:
    """Round-robin shard the configured commands; return the shard and the family size."""
    project = load_project_config(config_path)
    family = get_commands(project, categories=[category], include_api=False)
    selected = [
        command
        for index, command in enumerate(project.commands)
        if index % shard_total == shard_index and command in family
    ]
    return selected, len(family)


def _timing(samples: list[float]) -> TimingResult | None:
    if not samples:
        return None
    return TimingResult(
        mean_ms=statistics.fmean(samples),
        stddev_ms=statistics.stdev(samples) if len(samples) > 1 else 0.0,
        min_ms=min(samples),
        max_ms=max(samples),
        runs=len(samples),
        times_ms=list(samples),
    )


def write_suite(
    path: Path,
    target: Target,
    measurements: list[CommandMeasurement],
    rounds: int,
    warmups: int,
    threshold_percent: float,
    target_version: str = "unknown",
) -> None:
    """Write one side of the comparison in the `cli-bench` suite format."""
    results = [
        BenchmarkResult(
            command=m.command.name,
            command_args=m.command.args,
            category=m.command.category,
            warm_cache=_timing(m.base_ms if target.label == "base" else m.head_ms),
            error=m.error,
        )
        for m in measurements
    ]
    metadata = SuiteMetadata(
        timestamp=datetime.now(UTC).isoformat(),
        git_sha=target.sha,
        git_branch=target.label,
        python_version=platform.python_version(),
        platform=f"{platform.system()}/{platform.machine()}",
        target_version=target_version,
        hyperfine_version="not used",
    )
    config = BenchmarkConfig(
        runs=rounds, warmup_runs=warmups, regression_threshold_percent=threshold_percent
    )
    save_suite(BenchmarkSuite(metadata=metadata, results=results, config=config), path)


def _format_ms(samples: list[float]) -> str:
    return f"{statistics.median(samples):.0f}" if samples else "-"


def render_summary(
    base: Target,
    head: Target,
    measurements: list[CommandMeasurement],
    verdicts: list[Verdict],
    decision: dict[str, object],
) -> str:
    lines = [
        "## CLI Benchmark Results",
        "",
        (
            f"Base `{base.sha[:12]}` vs head `{head.sha[:12]}`: {decision['rounds']} "
            f"order-balanced paired rounds after {decision['warmups']} warmups "
            "per revision."
        ),
        (
            "Regression: paired geometric-mean slowdown > "
            f"{decision['threshold_percent']}% and one-sided paired t-test "
            f"p < {decision['alpha']} / {decision['family_size']} commands."
        ),
        "",
        "| Command | Base median (ms) | Head median (ms) | Paired delta | p (slower) | Result |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for measurement, verdict in zip(measurements, verdicts):
        delta = (
            f"{verdict.effect_percent:+.1f}%"
            if verdict.effect_percent is not None
            else "-"
        )
        p_value = f"{verdict.p_value:.4f}" if verdict.p_value is not None else "-"
        flag = " :red_circle:" if verdict.status in ("regression", "error") else ""
        lines.append(
            f"| {verdict.command} | {_format_ms(measurement.base_ms)} | "
            f"{_format_ms(measurement.head_ms)} | {delta} | {p_value} | "
            f"{verdict.status}{flag} |"
        )
    failures = [v for v in verdicts if v.status in ("regression", "error")]
    if failures:
        lines += ["", f"**{len(failures)} failing command(s):**"]
        lines += [f"- `{v.command}` ({v.status}): {v.reason}" for v in failures]
    return "\n".join(lines) + "\n"


def _digest_entry(
    verdict: Verdict, measurement: CommandMeasurement
) -> dict[str, object]:
    return {
        "command": verdict.command,
        "category": measurement.command.category,
        "warm_diff_percent": verdict.effect_percent,
        "warm_p_value": (
            verdict.improvement_p_value
            if verdict.status == "improvement"
            else verdict.p_value
        ),
        "warm_significant": verdict.status in ("regression", "improvement"),
        "cold_diff_percent": None,
        "cold_p_value": None,
        "cold_significant": False,
    }


def run_gate(
    config_path: Path,
    shard_index: int,
    shard_total: int,
    category: str,
    base: Target,
    head: Target,
    output_dir: Path,
    rounds: int,
    warmups: int,
    threshold_percent: float,
    alpha: float,
    min_rounds: int,
    target_versions: dict[str, str],
    run_once: RunOnce = time_command,
) -> int:
    commands, family_size = select_commands(
        config_path, shard_index, shard_total, category
    )
    if not commands:
        print(
            f"No {category!r} commands selected for shard {shard_index}/{shard_total}"
        )
        return 1
    print(
        f"Shard {shard_index}/{shard_total}: {len(commands)} of {family_size} commands, "
        f"{len(commands) * 2 * (rounds + warmups)} invocations "
        f"({warmups} warmups + {rounds} rounds per revision per command)"
    )

    measurements: list[CommandMeasurement] = []
    verdicts: list[Verdict] = []
    for command in commands:
        measurement = measure_command(command, base, head, rounds, warmups, run_once)
        verdict = evaluate(
            measurement, threshold_percent, alpha, family_size, min_rounds
        )
        print(f"{verdict.command}: {verdict.status} ({verdict.reason})")
        measurements.append(measurement)
        verdicts.append(verdict)

    decision: dict[str, object] = {
        "rule": "paired geometric-mean change with one-sided paired t-test, Bonferroni",
        "threshold_percent": threshold_percent,
        "alpha": alpha,
        "family_size": family_size,
        "per_command_alpha": alpha / family_size,
        "rounds": rounds,
        "warmups": warmups,
        "min_rounds": min_rounds,
        "shard_index": shard_index,
        "shard_total": shard_total,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    for target, filename in ((base, "baseline.json"), (head, "comparison.json")):
        write_suite(
            output_dir / filename,
            target,
            measurements,
            rounds,
            warmups,
            threshold_percent,
            target_versions[target.label],
        )
    digest = {
        "threshold_percent": threshold_percent,
        "baseline_sha": base.sha,
        "head_sha": head.sha,
        "decision": decision,
        "significant_regressions": [
            _digest_entry(v, m)
            for v, m in zip(verdicts, measurements)
            if v.status == "regression"
        ],
        "significant_improvements": [
            _digest_entry(v, m)
            for v, m in zip(verdicts, measurements)
            if v.status == "improvement"
        ],
        "commands": [
            {
                "command": v.command,
                "status": v.status,
                "reason": v.reason,
                "effect_percent": v.effect_percent,
                "p_value_slower": v.p_value,
                "p_value_faster": v.improvement_p_value,
                "base_ms": m.base_ms,
                "head_ms": m.head_ms,
                "orders": m.orders,
            }
            for v, m in zip(verdicts, measurements)
        ],
    }
    (output_dir / "cli-benchmark-digest.json").write_text(
        json.dumps(digest, indent=2) + "\n"
    )
    summary = render_summary(base, head, measurements, verdicts, decision)
    (output_dir / "cli-benchmark-compare.md").write_text(summary)
    if step_summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(step_summary, "a") as f:
            f.write(summary)
    print(summary)

    return 1 if any(v.status in ("regression", "error") for v in verdicts) else 0


def verify_target(target: Target, version_command: list[str] | None) -> str:
    """Check the checkout is the requested revision and return its reported version."""
    resolved = subprocess.run(
        ["git", "-C", str(target.root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    if resolved != target.sha:
        raise CommandFailedError(
            f"{target.label} checkout {target.root} is at {resolved or 'unknown'}, "
            f"expected {target.sha}"
        )
    if not version_command:
        return "unknown"
    argv, env = target_command(target, version_command)
    process = subprocess.run(
        argv,
        cwd=target.root,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if process.returncode != 0:
        raise CommandFailedError(
            f"{target.label}: version command failed: {process.stderr.strip()[-500:]}"
        )
    return process.stdout.strip().split()[-1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--shard-total", type=int, required=True)
    parser.add_argument("--base-root", type=Path, required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--head-root", type=Path, required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--category", default="startup")
    parser.add_argument("--rounds", type=int, default=10)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--min-rounds", type=int, default=6)
    parser.add_argument("--threshold", type=float, default=15.0)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--output-dir", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)

    base = Target("base", args.base_root.resolve(), args.base_sha)
    head = Target("head", args.head_root.resolve(), args.head_sha)
    version_command = load_project_config(args.config).version_command
    try:
        versions = {t.label: verify_target(t, version_command) for t in (base, head)}
    except (CommandFailedError, subprocess.TimeoutExpired) as exc:
        print(f"Cannot benchmark: {exc}", file=sys.stderr)
        return 1

    return run_gate(
        config_path=args.config,
        shard_index=args.shard_index,
        shard_total=args.shard_total,
        category=args.category,
        base=base,
        head=head,
        output_dir=args.output_dir,
        rounds=args.rounds,
        warmups=args.warmups,
        threshold_percent=args.threshold,
        alpha=args.alpha,
        min_rounds=args.min_rounds,
        target_versions=versions,
    )


if __name__ == "__main__":
    sys.exit(main())
