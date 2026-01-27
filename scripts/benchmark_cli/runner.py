"""Benchmark runner using hyperfine for timing."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .commands import BenchmarkCommand
from .config import BenchmarkConfig, BenchmarkResult, TimingResult


def check_hyperfine() -> str | None:
    """Check if hyperfine is installed and return version.

    Returns:
        Version string if installed, None otherwise.
    """
    try:
        result = subprocess.run(
            ["hyperfine", "--version"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            # Output is like "hyperfine 1.18.0"
            return result.stdout.strip().split()[-1]
        return None
    except FileNotFoundError:
        return None


def get_hyperfine_install_instructions() -> str:
    """Get platform-specific installation instructions for hyperfine."""
    system = platform.system()
    if system == "Darwin":
        return "brew install hyperfine"
    elif system == "Linux":
        return (
            "# Ubuntu/Debian:\n"
            "wget https://github.com/sharkdp/hyperfine/releases/download/v1.18.0/hyperfine_1.18.0_amd64.deb\n"
            "sudo dpkg -i hyperfine_1.18.0_amd64.deb\n\n"
            "# Or with cargo:\n"
            "cargo install hyperfine"
        )
    else:
        return "See https://github.com/sharkdp/hyperfine#installation"


def get_cache_clear_command() -> str:
    """Get platform-specific command to clear caches.

    This clears Python's __pycache__ directories. OS-level cache clearing
    requires elevated privileges and is optional.
    """
    # Find the prefect package location
    prefect_path = '$(python -c "import prefect; print(prefect.__path__[0])" 2>/dev/null || echo .)'

    # Clear __pycache__ directories
    pycache_clear = f"find {prefect_path} -type d -name __pycache__ -exec rm -rf {{}} + 2>/dev/null || true"

    system = platform.system()
    if system == "Darwin":
        # macOS: sync helps, purge requires sudo
        return f"{pycache_clear}; sync"
    elif system == "Linux":
        # Linux: drop_caches requires sudo, try it but don't fail
        return f"{pycache_clear}; sync; {{ echo 3 | sudo tee /proc/sys/vm/drop_caches >/dev/null 2>&1 || true; }}"
    else:
        return pycache_clear


class BenchmarkRunner:
    """Runs benchmarks using hyperfine."""

    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self._hyperfine_version = check_hyperfine()

    @property
    def hyperfine_available(self) -> bool:
        return self._hyperfine_version is not None

    @property
    def hyperfine_version(self) -> str:
        return self._hyperfine_version or "not installed"

    def run_benchmark(self, cmd: BenchmarkCommand) -> BenchmarkResult:
        """Run both cold and warm benchmarks for a command.

        Args:
            cmd: The command to benchmark.

        Returns:
            BenchmarkResult with timing data.
        """
        result = BenchmarkResult(
            command=cmd.name,
            command_args=cmd.args,
            category=cmd.category,
        )

        # Check if server is required but not configured
        if cmd.requires_server and not self.config.server_url:
            result.error = "requires server (use --server-url or set PREFECT_API_URL)"
            return result

        try:
            if not self.config.skip_cold:
                result.cold_start = self._run_cold_start(cmd)

            if not self.config.skip_warm:
                result.warm_cache = self._run_warm_cache(cmd)

        except subprocess.TimeoutExpired:
            result.error = f"timeout after {self.config.timeout_seconds}s"
        except subprocess.CalledProcessError as e:
            result.error = f"command failed with exit code {e.returncode}"
        except Exception as e:
            result.error = str(e)

        return result

    def _run_cold_start(self, cmd: BenchmarkCommand) -> TimingResult:
        """Run cold start benchmark (clearing caches between runs)."""
        return self._run_hyperfine(
            cmd,
            warmup=0,
            prepare=get_cache_clear_command(),
        )

    def _run_warm_cache(self, cmd: BenchmarkCommand) -> TimingResult:
        """Run warm cache benchmark (with warmup runs)."""
        return self._run_hyperfine(
            cmd,
            warmup=self.config.warmup_runs,
            prepare=None,
        )

    def _run_hyperfine(
        self,
        cmd: BenchmarkCommand,
        warmup: int,
        prepare: str | None,
    ) -> TimingResult:
        """Run hyperfine and parse results.

        Args:
            cmd: Command to benchmark.
            warmup: Number of warmup runs.
            prepare: Command to run before each benchmark run.

        Returns:
            TimingResult with statistics.
        """
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            json_output = Path(f.name)

        try:
            hyperfine_args = [
                "hyperfine",
                "--warmup",
                str(warmup),
                "--runs",
                str(self.config.runs),
                "--export-json",
                str(json_output),
                "--time-unit",
                "millisecond",
            ]

            if prepare:
                hyperfine_args.extend(["--prepare", prepare])

            # Add the actual command
            command_str = shutil.which(cmd.args[0]) or cmd.args[0]
            full_command = " ".join([command_str] + cmd.args[1:])
            hyperfine_args.append(full_command)

            # Set up environment for API commands
            env = None
            if cmd.requires_server and self.config.server_url:
                import os

                env = os.environ.copy()
                env["PREFECT_API_URL"] = self.config.server_url

            if self.config.verbose:
                print(f"  Running: {' '.join(hyperfine_args)}", file=sys.stderr)

            subprocess.run(
                hyperfine_args,
                capture_output=not self.config.verbose,
                timeout=self.config.timeout_seconds * (self.config.runs + warmup + 5),
                check=True,
                env=env,
            )

            # Parse results
            with open(json_output) as f:
                data = json.load(f)

            result = data["results"][0]
            # Handle None values (e.g., stddev is null with only 1 run)
            stddev = result.get("stddev")
            # Preserve raw times for statistical analysis
            raw_times_ms = [t * 1000 for t in result["times"]]
            return TimingResult(
                mean_ms=result["mean"] * 1000,
                stddev_ms=stddev * 1000 if stddev is not None else 0.0,
                min_ms=result["min"] * 1000,
                max_ms=result["max"] * 1000,
                runs=len(raw_times_ms),
                times_ms=raw_times_ms,
            )

        finally:
            json_output.unlink(missing_ok=True)
