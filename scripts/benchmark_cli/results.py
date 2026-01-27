"""JSON serialization and comparison for benchmark results."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import (
    BenchmarkConfig,
    BenchmarkResult,
    BenchmarkSuite,
    SuiteMetadata,
    TimingResult,
)


def get_git_info() -> tuple[str, str]:
    """Get current git SHA and branch name.

    Returns:
        Tuple of (sha, branch).
    """
    sha = "unknown"
    branch = "unknown"

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            sha = result.stdout.strip()
    except FileNotFoundError:
        pass

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
    except FileNotFoundError:
        pass

    return sha, branch


def get_prefect_version() -> str:
    """Get the installed Prefect version."""
    try:
        import prefect

        return prefect.__version__
    except ImportError:
        return "unknown"


def create_metadata(hyperfine_version: str) -> SuiteMetadata:
    """Create metadata for a benchmark suite run."""
    git_sha, git_branch = get_git_info()

    return SuiteMetadata(
        timestamp=datetime.now(timezone.utc).isoformat(),
        git_sha=git_sha,
        git_branch=git_branch,
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        platform=f"{platform.system()}/{platform.machine()}",
        prefect_version=get_prefect_version(),
        hyperfine_version=hyperfine_version,
    )


def suite_to_dict(suite: BenchmarkSuite) -> dict[str, Any]:
    """Convert a BenchmarkSuite to a JSON-serializable dict."""

    def timing_to_dict(t: TimingResult | None) -> dict[str, Any] | None:
        if t is None:
            return None
        return asdict(t)

    def result_to_dict(r: BenchmarkResult) -> dict[str, Any]:
        return {
            "command": r.command,
            "command_args": r.command_args,
            "category": r.category,
            "cold_start": timing_to_dict(r.cold_start),
            "warm_cache": timing_to_dict(r.warm_cache),
            "peak_memory_mb": r.peak_memory_mb,
            "error": r.error,
        }

    return {
        "metadata": asdict(suite.metadata),
        "results": [result_to_dict(r) for r in suite.results],
        "config": {
            "runs": suite.config.runs,
            "warmup_runs": suite.config.warmup_runs,
            "regression_threshold_percent": suite.config.regression_threshold_percent,
        },
    }


def dict_to_suite(data: dict[str, Any]) -> BenchmarkSuite:
    """Convert a dict (from JSON) back to a BenchmarkSuite."""

    def dict_to_timing(d: dict[str, Any] | None) -> TimingResult | None:
        if d is None:
            return None
        return TimingResult(**d)

    def dict_to_result(d: dict[str, Any]) -> BenchmarkResult:
        return BenchmarkResult(
            command=d["command"],
            command_args=d["command_args"],
            category=d["category"],
            cold_start=dict_to_timing(d.get("cold_start")),
            warm_cache=dict_to_timing(d.get("warm_cache")),
            peak_memory_mb=d.get("peak_memory_mb"),
            error=d.get("error"),
        )

    metadata = SuiteMetadata(**data["metadata"])
    results = [dict_to_result(r) for r in data["results"]]

    # Reconstruct config with defaults for missing fields
    config_data = data.get("config", {})
    config = BenchmarkConfig(
        runs=config_data.get("runs", 10),
        warmup_runs=config_data.get("warmup_runs", 3),
        regression_threshold_percent=config_data.get(
            "regression_threshold_percent", 10.0
        ),
    )

    return BenchmarkSuite(metadata=metadata, results=results, config=config)


def save_suite(suite: BenchmarkSuite, path: Path) -> None:
    """Save a benchmark suite to a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(suite_to_dict(suite), f, indent=2)


def load_suite(path: Path) -> BenchmarkSuite:
    """Load a benchmark suite from a JSON file."""
    with open(path) as f:
        data = json.load(f)
    return dict_to_suite(data)


class ComparisonResult:
    """Result of comparing two benchmark results."""

    def __init__(
        self,
        command: str,
        category: str,
        current: BenchmarkResult,
        baseline: BenchmarkResult | None,
        threshold_percent: float,
    ):
        self.command = command
        self.category = category
        self.current = current
        self.baseline = baseline
        self.threshold = threshold_percent

    @property
    def cold_diff_percent(self) -> float | None:
        """Percentage difference in cold start time."""
        if (
            self.baseline is None
            or self.baseline.cold_start is None
            or self.current.cold_start is None
        ):
            return None
        baseline_ms = self.baseline.cold_start.mean_ms
        current_ms = self.current.cold_start.mean_ms
        if baseline_ms == 0:
            return None
        return ((current_ms - baseline_ms) / baseline_ms) * 100

    @property
    def warm_diff_percent(self) -> float | None:
        """Percentage difference in warm cache time."""
        if (
            self.baseline is None
            or self.baseline.warm_cache is None
            or self.current.warm_cache is None
        ):
            return None
        baseline_ms = self.baseline.warm_cache.mean_ms
        current_ms = self.current.warm_cache.mean_ms
        if baseline_ms == 0:
            return None
        return ((current_ms - baseline_ms) / baseline_ms) * 100

    @property
    def memory_diff_percent(self) -> float | None:
        """Percentage difference in peak memory."""
        if (
            self.baseline is None
            or self.baseline.peak_memory_mb is None
            or self.current.peak_memory_mb is None
        ):
            return None
        baseline_mb = self.baseline.peak_memory_mb
        current_mb = self.current.peak_memory_mb
        if baseline_mb == 0:
            return None
        return ((current_mb - baseline_mb) / baseline_mb) * 100

    @property
    def is_regression(self) -> bool:
        """Check if this result is a regression."""
        for diff in [self.cold_diff_percent, self.warm_diff_percent]:
            if diff is not None and diff > self.threshold:
                return True
        return False

    @property
    def status(self) -> str:
        """Get status string for display."""
        if self.current.error:
            return "ERROR"
        if self.baseline is None:
            return "NEW"

        diffs = [
            d for d in [self.cold_diff_percent, self.warm_diff_percent] if d is not None
        ]
        if not diffs:
            return "OK"

        max_diff = max(diffs)
        if max_diff > self.threshold:
            return f"+{max_diff:.0f}%"
        elif max_diff < -self.threshold:
            return f"{max_diff:.0f}%"
        else:
            return "OK"


def compare_suites(
    current: BenchmarkSuite,
    baseline: BenchmarkSuite,
    threshold_percent: float = 10.0,
) -> list[ComparisonResult]:
    """Compare two benchmark suites.

    Args:
        current: The current benchmark results.
        baseline: The baseline to compare against.
        threshold_percent: Percentage threshold for regression detection.

    Returns:
        List of comparison results.
    """
    # Build lookup for baseline results by command name
    baseline_lookup = {r.command: r for r in baseline.results}

    comparisons = []
    for result in current.results:
        baseline_result = baseline_lookup.get(result.command)
        comparisons.append(
            ComparisonResult(
                command=result.command,
                category=result.category,
                current=result,
                baseline=baseline_result,
                threshold_percent=threshold_percent,
            )
        )

    return comparisons
