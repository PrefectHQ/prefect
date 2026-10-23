"""
Tests scripts/cli_startup_benchmark.py
"""

from __future__ import annotations

import importlib.util
import json
import math
import random
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

pytest.importorskip("scipy", reason="requires the `cli-bench` dependency group")
pytest.importorskip("cli_bench", reason="requires the `cli-bench` dependency group")

from cli_bench.config import BenchmarkCommand
from cli_bench.results import compare_suites, load_suite

SCRIPT_PATH = Path(__file__).parents[2] / "scripts" / "cli_startup_benchmark.py"

# Samples from the `prefect deployment --help` comparison that failed the
# sequential gate in https://github.com/PrefectHQ/prefect/actions/runs/39992885993
CAPTURED_BASE_MS = [
    847.53014218,
    842.51490218,
    853.28838618,
    855.45177718,
    897.87757618,
]
CAPTURED_HEAD_MS = [
    1254.78392272,
    1146.85725172,
    1095.69174772,
    921.20381472,
    898.32573772,
]


@pytest.fixture(scope="module")
def bench():
    spec = importlib.util.spec_from_file_location("cli_startup_benchmark", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop(spec.name, None)


def make_command(name: str = "cli --help") -> BenchmarkCommand:
    return BenchmarkCommand(name=name, args=name.split(), category="startup")


class ScriptedRunner:
    """Deterministic stand-in for timing one CLI invocation.

    `cost(label, command_name, call_index)` returns the simulated wall time, so
    drift can be modelled as a function of when a sample is taken.
    """

    def __init__(self, cost: Callable[[str, str, int], float]):
        self.cost = cost
        self.calls: list[tuple[str, str]] = []

    def __call__(self, target, command) -> float:
        index = len(self.calls)
        self.calls.append((target.label, command.name))
        return self.cost(target.label, command.name, index)


def drifting_cost(
    head_factor: float, seed: int = 0
) -> Callable[[str, str, int], float]:
    """Runner that slows down over time with transient bursts and jitter."""
    rng = random.Random(seed)

    def cost(label: str, _command: str, index: int) -> float:
        trend = 1 + 0.02 * index  # steadily slowing host, ~+40% within a command
        burst = 1.35 if (index // 6) % 3 == 1 else 1.0  # shared noisy-neighbour bursts
        jitter = rng.uniform(0.97, 1.03)
        factor = head_factor if label == "head" else 1.0
        return 800 * trend * burst * jitter * factor

    return cost


@pytest.fixture
def targets(bench, tmp_path):
    return (
        bench.Target("base", tmp_path / "base", "a" * 40),
        bench.Target("head", tmp_path / "head", "b" * 40),
    )


def test_rounds_are_paired_order_balanced_and_keep_target_identity(bench, targets):
    base, head = targets
    runner = ScriptedRunner(lambda label, _c, _i: 100.0 if label == "base" else 200.0)

    measurement = bench.measure_command(
        make_command(), base, head, rounds=6, warmups=2, run_once=runner
    )

    assert runner.calls[:4] == [("base", "cli --help"), ("head", "cli --help")] * 2
    measured = [label for label, _ in runner.calls[4:]]
    pairs = [tuple(measured[i : i + 2]) for i in range(0, len(measured), 2)]
    assert pairs == [("base", "head"), ("head", "base")] * 3
    assert measurement.orders == [("base", "head"), ("head", "base")] * 3
    assert measurement.base_ms == [100.0] * 6
    assert measurement.head_ms == [200.0] * 6
    assert measurement.error is None


def test_odd_round_counts_are_rejected(bench, targets):
    with pytest.raises(ValueError, match="even"):
        bench.measure_command(
            make_command(), *targets, rounds=5, warmups=1, run_once=lambda t, c: 1.0
        )


def test_shared_drift_without_code_change_is_not_a_regression(bench, targets):
    measurement = bench.measure_command(
        make_command(),
        *targets,
        rounds=10,
        warmups=2,
        run_once=ScriptedRunner(drifting_cost(1.0)),
    )

    verdict = bench.evaluate(
        measurement, threshold_percent=15, alpha=0.05, family_size=28, min_rounds=6
    )

    assert verdict.status == "ok"
    assert abs(verdict.effect_percent) < 5


def test_same_drift_with_sequential_suites_fooled_the_previous_gate(targets):
    """Documents why sampling order matters: all-base-then-all-head confounds drift."""
    cost = drifting_cost(1.0)
    base_samples = [cost("base", "cli", i) for i in range(5)]
    head_samples = [cost("head", "cli", i) for i in range(5, 10)]
    assert sum(head_samples) / sum(base_samples) > 1.15


@pytest.mark.parametrize("seed", range(5))
def test_stable_slowdown_above_threshold_fails_despite_drift(bench, targets, seed):
    measurement = bench.measure_command(
        make_command(),
        *targets,
        rounds=10,
        warmups=2,
        run_once=ScriptedRunner(drifting_cost(1.20, seed=seed)),
    )

    verdict = bench.evaluate(
        measurement, threshold_percent=15, alpha=0.05, family_size=28, min_rounds=6
    )

    assert verdict.status == "regression"
    assert 15 < verdict.effect_percent < 25
    assert verdict.p_value < verdict.per_command_alpha == pytest.approx(0.05 / 28)


def test_stable_slowdown_below_threshold_passes(bench, targets):
    measurement = bench.measure_command(
        make_command(),
        *targets,
        rounds=10,
        warmups=2,
        run_once=ScriptedRunner(drifting_cost(1.10)),
    )

    verdict = bench.evaluate(
        measurement, threshold_percent=15, alpha=0.05, family_size=28, min_rounds=6
    )

    assert verdict.status == "ok"
    assert verdict.p_value < verdict.per_command_alpha  # real, but under the 15% bar


def test_captured_failing_samples_are_not_a_strong_regression(bench, tmp_path):
    measurement = bench.CommandMeasurement(
        command=make_command("prefect deployment --help"),
        base_ms=list(CAPTURED_BASE_MS),
        head_ms=list(CAPTURED_HEAD_MS),
        orders=[("base", "head"), ("head", "base")] * 2 + [("base", "head")],
    )

    verdict = bench.evaluate(
        measurement, threshold_percent=15, alpha=0.05, family_size=28, min_rounds=4
    )

    assert verdict.status == "inconclusive"
    assert verdict.effect_percent > 15
    assert 0.01 < verdict.p_value < 0.05
    assert verdict.p_value > verdict.per_command_alpha

    # With the default evidence floor, five rounds are reported as insufficient
    # rather than as a pass or a regression.
    default_verdict = bench.evaluate(
        measurement, threshold_percent=15, alpha=0.05, family_size=28, min_rounds=6
    )
    assert default_verdict.status == "error"
    assert "insufficient" in default_verdict.reason


def test_pinned_tool_flagged_the_captured_samples(bench, tmp_path):
    """The previous gate's verdict on the captured samples, kept for contrast."""
    base, head = (
        bench.Target("base", tmp_path, "a" * 40),
        bench.Target("head", tmp_path, "b" * 40),
    )
    measurement = bench.CommandMeasurement(
        command=make_command("prefect deployment --help"),
        base_ms=list(CAPTURED_BASE_MS),
        head_ms=list(CAPTURED_HEAD_MS),
        orders=[],
    )
    bench.write_suite(tmp_path / "baseline.json", base, [measurement], 5, 0, 15)
    bench.write_suite(tmp_path / "comparison.json", head, [measurement], 5, 0, 15)

    (comparison,) = compare_suites(
        load_suite(tmp_path / "comparison.json"),
        load_suite(tmp_path / "baseline.json"),
        15,
    )
    assert comparison.is_regression


@pytest.mark.parametrize(
    "base_ms, head_ms, error, reason",
    [
        ([100.0] * 4, [100.0] * 4, None, "insufficient"),
        ([100.0] * 6, [100.0] * 5, None, "insufficient"),
        ([100.0] * 5 + [math.nan], [100.0] * 6, None, "invalid"),
        ([100.0] * 6, [100.0] * 5 + [0.0], None, "invalid"),
        ([100.0] * 6, [100.0] * 6, "exit code 2", "exit code 2"),
    ],
)
def test_invalid_or_insufficient_measurements_fail_closed(
    bench, base_ms, head_ms, error, reason
):
    measurement = bench.CommandMeasurement(
        command=make_command(), base_ms=base_ms, head_ms=head_ms, orders=[], error=error
    )

    verdict = bench.evaluate(
        measurement, threshold_percent=15, alpha=0.05, family_size=1, min_rounds=6
    )

    assert verdict.status == "error"
    assert reason in verdict.reason


def test_family_wise_correction_uses_the_whole_command_family(bench):
    head_ratios = [1.45, 1.0, 1.35, 1.05, 1.4, 1.1, 1.3, 1.0]
    measurement = bench.CommandMeasurement(
        command=make_command(),
        base_ms=[1000.0] * len(head_ratios),
        head_ms=[1000.0 * ratio for ratio in head_ratios],
    )

    alone = bench.evaluate(measurement, 15, 0.05, family_size=1, min_rounds=6)
    in_family = bench.evaluate(measurement, 15, 0.05, family_size=28, min_rounds=6)

    assert alone.status == "regression"
    assert in_family.status == "inconclusive"
    assert alone.p_value == in_family.p_value


def write_config(path: Path, command_names: list[str]) -> Path:
    lines = [
        "[project]",
        'name = "fakecli"',
        'version_command = ["fakecli", "--version"]',
    ]
    for name in command_names:
        lines += [
            "",
            "[[commands]]",
            f'name = "{name}"',
            f"args = {json.dumps(name.split())}",
            'category = "startup"',
        ]
    path.write_text("\n".join(lines) + "\n")
    return path


def test_shards_share_the_full_family_size(bench, tmp_path):
    names = [f"fakecli cmd{i}" for i in range(9)]
    config = write_config(tmp_path / "bench.toml", names)

    selections = [
        bench.select_commands(config, index, 4, "startup") for index in range(4)
    ]

    assert [[c.name for c in selected] for selected, _ in selections] == [
        names[0::4],
        names[1::4],
        names[2::4],
        names[3::4],
    ]
    assert {family for _, family in selections} == {9}


def run_gate(bench, tmp_path, runner, names=("fakecli a", "fakecli b"), **overrides):
    config = write_config(tmp_path / "bench.toml", list(names))
    base = bench.Target("base", tmp_path / "base", "a" * 40)
    head = bench.Target("head", tmp_path / "head", "b" * 40)
    out = tmp_path / "out"
    kwargs = {
        "config_path": config,
        "shard_index": 0,
        "shard_total": 1,
        "category": "startup",
        "base": base,
        "head": head,
        "output_dir": out,
        "rounds": 6,
        "warmups": 1,
        "threshold_percent": 15,
        "alpha": 0.05,
        "min_rounds": 6,
        "run_once": runner,
        "target_versions": {"base": "1.0", "head": "1.1"},
    }
    kwargs.update(overrides)
    return bench.run_gate(**kwargs), out


def test_gate_reports_regressions_with_identity_and_raw_observations(bench, tmp_path):
    def cost(label, command, index):
        slow = label == "head" and command == "fakecli b"
        return 100.0 * (1.5 if slow else 1.0) * (1 + 0.001 * (index % 7))

    exit_code, out = run_gate(bench, tmp_path, ScriptedRunner(cost))

    assert exit_code == 1
    digest = json.loads((out / "cli-benchmark-digest.json").read_text())
    assert digest["baseline_sha"] == "a" * 40
    assert digest["head_sha"] == "b" * 40
    assert digest["decision"]["family_size"] == 2
    assert [r["command"] for r in digest["significant_regressions"]] == ["fakecli b"]
    by_command = {c["command"]: c for c in digest["commands"]}
    assert by_command["fakecli a"]["status"] == "ok"
    assert len(by_command["fakecli b"]["base_ms"]) == 6

    baseline = load_suite(out / "baseline.json")
    comparison = load_suite(out / "comparison.json")
    assert (baseline.metadata.git_sha, baseline.metadata.target_version) == (
        "a" * 40,
        "1.0",
    )
    assert (comparison.metadata.git_sha, comparison.metadata.target_version) == (
        "b" * 40,
        "1.1",
    )
    assert (
        comparison.results[1].warm_cache.times_ms == by_command["fakecli b"]["head_ms"]
    )

    summary = (out / "cli-benchmark-compare.md").read_text()
    assert "fakecli b" in summary and "regression" in summary
    assert "a" * 12 in summary and "b" * 12 in summary


def test_gate_passes_when_nothing_regresses(bench, tmp_path):
    exit_code, out = run_gate(bench, tmp_path, ScriptedRunner(lambda *_: 100.0))

    assert exit_code == 0
    digest = json.loads((out / "cli-benchmark-digest.json").read_text())
    assert digest["significant_regressions"] == []
    assert {c["status"] for c in digest["commands"]} == {"ok"}


def test_command_failure_fails_closed_and_keeps_partial_artifacts(bench, tmp_path):
    def cost(label, command, index):
        if label == "head" and command == "fakecli a" and index > 5:
            raise bench.CommandFailedError("fakecli a exited with code 3: boom")
        return 100.0

    exit_code, out = run_gate(bench, tmp_path, ScriptedRunner(cost))

    assert exit_code == 1
    digest = json.loads((out / "cli-benchmark-digest.json").read_text())
    by_command = {c["command"]: c for c in digest["commands"]}
    assert by_command["fakecli a"]["status"] == "error"
    assert "boom" in by_command["fakecli a"]["reason"]
    assert by_command["fakecli a"]["base_ms"]  # partial evidence retained
    assert by_command["fakecli b"]["status"] == "ok"
    comparison = load_suite(out / "comparison.json")
    assert "boom" in comparison.results[0].error
    assert "boom" in (out / "cli-benchmark-compare.md").read_text()


FAKE_CLI = """#!/bin/sh
echo "$0 $*" >> "{log}"
if [ "$1" = "--version" ]; then echo "fakecli {version}"; exit 0; fi
if [ "$1" = "fail" ]; then echo "broken" >&2; exit 4; fi
exit 0
"""


def make_target_checkout(root: Path, version: str) -> str:
    bin_dir = root / ".venv" / "bin"
    bin_dir.mkdir(parents=True)
    executable = bin_dir / "fakecli"
    executable.write_text(FAKE_CLI.format(log=root / "calls.log", version=version))
    executable.chmod(0o755)
    git = [
        "git",
        "-C",
        str(root),
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.com",
    ]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", version], check=True)
    return subprocess.run(
        [*git, "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.mark.skipif(sys.platform == "win32", reason="uses POSIX shell executables")
def test_cli_runs_each_target_environment_and_writes_artifacts(bench, tmp_path):
    base_sha = make_target_checkout(tmp_path / "base", "1.0")
    head_sha = make_target_checkout(tmp_path / "head", "2.0")
    config = write_config(tmp_path / "bench.toml", ["fakecli ok", "fakecli fail"])
    out = tmp_path / "out"

    exit_code = bench.main(
        [
            "--config", str(config),
            "--shard-index", "0",
            "--shard-total", "1",
            "--base-root", str(tmp_path / "base"),
            "--base-sha", base_sha,
            "--head-root", str(tmp_path / "head"),
            "--head-sha", head_sha,
            "--rounds", "2",
            "--warmups", "1",
            "--min-rounds", "2",
            "--output-dir", str(out),
        ]
    )  # fmt: skip

    assert exit_code == 1  # `fakecli fail` exits non-zero
    for label in ("base", "head"):
        calls = (tmp_path / label / "calls.log").read_text().splitlines()
        assert all(line.startswith(str(tmp_path / label / ".venv")) for line in calls)
        assert sum(line.endswith(" ok") for line in calls) == 3  # warmup + rounds
    digest = json.loads((out / "cli-benchmark-digest.json").read_text())
    by_command = {c["command"]: c for c in digest["commands"]}
    assert by_command["fakecli ok"]["status"] == "ok"
    assert by_command["fakecli fail"]["status"] == "error"
    assert "broken" in by_command["fakecli fail"]["reason"]
    assert load_suite(out / "baseline.json").metadata.target_version == "1.0"
    assert load_suite(out / "comparison.json").metadata.target_version == "2.0"
    assert (digest["baseline_sha"], digest["head_sha"]) == (base_sha, head_sha)


def test_cli_rejects_a_checkout_that_is_not_the_requested_revision(bench, tmp_path):
    base_sha = make_target_checkout(tmp_path / "base", "1.0")
    make_target_checkout(tmp_path / "head", "2.0")
    config = write_config(tmp_path / "bench.toml", ["fakecli ok"])

    exit_code = bench.main(
        [
            "--config", str(config),
            "--shard-index", "0",
            "--shard-total", "1",
            "--base-root", str(tmp_path / "base"),
            "--base-sha", base_sha,
            "--head-root", str(tmp_path / "head"),
            "--head-sha", base_sha,
            "--output-dir", str(tmp_path / "out"),
        ]
    )  # fmt: skip

    assert exit_code == 1
    assert not (tmp_path / "head" / "calls.log").exists()
