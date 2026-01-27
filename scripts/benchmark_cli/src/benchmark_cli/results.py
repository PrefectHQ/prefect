"""JSON serialization and comparison for benchmark results."""

from __future__ import annotations

import json
import math
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


def welch_ttest(x: list[float], y: list[float]) -> tuple[float, float]:
    """Perform Welch's t-test on two samples.

    Uses scipy if available, otherwise falls back to a simple approximation.

    Returns:
        Tuple of (t-statistic, p-value).
        Returns (0.0, 1.0) if test cannot be performed.
    """
    n1, n2 = len(x), len(y)
    if n1 < 2 or n2 < 2:
        return 0.0, 1.0

    # Try scipy first (more accurate)
    try:
        from scipy import stats

        t, p = stats.ttest_ind(x, y, equal_var=False)
        return float(t), float(p)
    except ImportError:
        pass

    # Fallback: manual calculation
    mean1 = sum(x) / n1
    mean2 = sum(y) / n2

    var1 = sum((xi - mean1) ** 2 for xi in x) / (n1 - 1)
    var2 = sum((yi - mean2) ** 2 for yi in y) / (n2 - 1)

    if var1 == 0 and var2 == 0:
        return 0.0, 1.0

    # Welch's t-statistic
    se = math.sqrt(var1 / n1 + var2 / n2)
    if se == 0:
        return 0.0, 1.0

    t = (mean1 - mean2) / se

    # Approximate p-value using normal distribution for simplicity
    # (accurate when df > 30, reasonable approximation otherwise)
    p = 2 * (1 - _normal_cdf(abs(t)))

    return t, min(p, 1.0)  # Ensure p <= 1


def _normal_cdf(x: float) -> float:
    """Approximate CDF of standard normal distribution."""
    # Using error function approximation
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


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
        # Handle old format without times_ms
        if "times_ms" not in d:
            d = {**d, "times_ms": []}
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
    """Result of comparing two benchmark results with statistical significance."""

    SIGNIFICANCE_THRESHOLD = 0.05  # p-value threshold

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
        # Compute statistical significance
        self._warm_t, self._warm_p = self._compute_significance("warm_cache")
        self._cold_t, self._cold_p = self._compute_significance("cold_start")

    def _compute_significance(self, metric: str) -> tuple[float, float]:
        """Compute Welch's t-test for a metric."""
        if self.baseline is None:
            return 0.0, 1.0

        current_timing = getattr(self.current, metric)
        baseline_timing = getattr(self.baseline, metric)

        if current_timing is None or baseline_timing is None:
            return 0.0, 1.0

        current_times = current_timing.times_ms
        baseline_times = baseline_timing.times_ms

        if not current_times or not baseline_times:
            return 0.0, 1.0

        return welch_ttest(current_times, baseline_times)

    @property
    def warm_p_value(self) -> float:
        """P-value for warm cache comparison."""
        return self._warm_p

    @property
    def cold_p_value(self) -> float:
        """P-value for cold start comparison."""
        return self._cold_p

    @property
    def warm_significant(self) -> bool:
        """Whether warm cache difference is statistically significant."""
        return self._warm_p < self.SIGNIFICANCE_THRESHOLD

    @property
    def cold_significant(self) -> bool:
        """Whether cold start difference is statistically significant."""
        return self._cold_p < self.SIGNIFICANCE_THRESHOLD

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
        """Check if this result is a statistically significant regression."""
        # Must exceed threshold AND be statistically significant
        if self.warm_diff_percent is not None:
            if self.warm_diff_percent > self.threshold and self.warm_significant:
                return True
        if self.cold_diff_percent is not None:
            if self.cold_diff_percent > self.threshold and self.cold_significant:
                return True
        return False

    @property
    def status(self) -> str:
        """Get status string for display."""
        if self.current.error:
            return "ERROR"
        if self.baseline is None:
            return "NEW"

        diff = self.warm_diff_percent
        significant = self.warm_significant

        if diff is None:
            return "OK"

        if diff > self.threshold:
            if significant:
                return f"[red]+{diff:.0f}%[/red]"
            else:
                return f"[yellow]+{diff:.0f}%?[/yellow]"  # ? = not significant
        elif diff < -self.threshold:
            if significant:
                return f"[green]{diff:.0f}%[/green]"
            else:
                return f"[dim]{diff:.0f}%?[/dim]"
        else:
            return "[dim]OK[/dim]"


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
