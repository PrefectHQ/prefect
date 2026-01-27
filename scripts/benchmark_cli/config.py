"""Configuration and result dataclasses for CLI benchmarks."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark runs."""

    runs: int = 10
    warmup_runs: int = 3
    timeout_seconds: int = 30
    regression_threshold_percent: float = 10.0
    output_dir: Path = field(default_factory=lambda: Path(".benchmarks"))
    json_output: bool = False
    output_file: Path | None = None
    skip_memory: bool = False
    skip_cold: bool = False
    skip_warm: bool = False
    categories: list[str] | None = None
    server_url: str | None = None
    compare_baseline: Path | None = None
    verbose: bool = False


@dataclass
class TimingResult:
    """Result from a hyperfine timing run."""

    mean_ms: float
    stddev_ms: float
    min_ms: float
    max_ms: float
    runs: int
    # Raw times for statistical analysis (Welch's t-test, percentiles, etc.)
    times_ms: list[float] = field(default_factory=list)


@dataclass
class BenchmarkResult:
    """Result for a single benchmark command."""

    command: str
    command_args: list[str]
    category: str
    cold_start: TimingResult | None = None
    warm_cache: TimingResult | None = None
    peak_memory_mb: float | None = None
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None


@dataclass
class SuiteMetadata:
    """Metadata for a benchmark suite run."""

    timestamp: str
    git_sha: str
    git_branch: str
    python_version: str
    platform: str
    prefect_version: str
    hyperfine_version: str


@dataclass
class BenchmarkSuite:
    """Complete results from a benchmark suite run."""

    metadata: SuiteMetadata
    results: list[BenchmarkResult]
    config: BenchmarkConfig
