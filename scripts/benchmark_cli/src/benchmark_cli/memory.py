"""Memory profiling using tracemalloc."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from .commands import BenchmarkCommand
from .config import BenchmarkConfig


class MemoryProfiler:
    """Profile memory usage of CLI commands using tracemalloc."""

    def __init__(self, config: BenchmarkConfig):
        self.config = config

    def measure_command(self, cmd: BenchmarkCommand) -> float | None:
        """Measure peak memory usage of a command.

        Uses tracemalloc in a subprocess to measure memory used by
        importing and invoking the CLI via CliRunner.

        Args:
            cmd: The command to measure.

        Returns:
            Peak memory in MB, or None if measurement failed.
        """
        # Build the measurement script
        script = self._build_measurement_script(cmd)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script)
            script_path = Path(f.name)

        try:
            # Set up environment for API commands
            env = None
            if cmd.requires_server and self.config.server_url:
                import os

                env = os.environ.copy()
                env["PREFECT_API_URL"] = self.config.server_url

            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=self.config.timeout_seconds,
                env=env,
            )

            if result.returncode != 0:
                if self.config.verbose:
                    print(
                        f"  Memory profiling failed: {result.stderr}", file=sys.stderr
                    )
                return None

            # Parse the JSON output
            try:
                data = json.loads(result.stdout.strip())
                return data["peak_mb"]
            except (json.JSONDecodeError, KeyError):
                if self.config.verbose:
                    print(
                        f"  Failed to parse memory output: {result.stdout}",
                        file=sys.stderr,
                    )
                return None

        except subprocess.TimeoutExpired:
            if self.config.verbose:
                print("  Memory profiling timed out", file=sys.stderr)
            return None
        finally:
            script_path.unlink(missing_ok=True)

    def _build_measurement_script(self, cmd: BenchmarkCommand) -> str:
        """Build a Python script to measure memory usage.

        Uses CliRunner to invoke the CLI in-process with tracemalloc
        tracking memory allocations.
        """
        # Convert command args to the format CliRunner expects
        # First arg is 'prefect', rest are the actual args
        cli_args = cmd.args[1:] if cmd.args[0] == "prefect" else cmd.args

        script = textwrap.dedent(f"""
            import json
            import tracemalloc
            import sys

            # Start memory tracking
            tracemalloc.start()

            try:
                # Import and invoke the CLI
                from prefect.cli import app
                from typer.testing import CliRunner

                runner = CliRunner()
                result = runner.invoke(app, {cli_args!r}, catch_exceptions=True)

                # Get peak memory
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()

                # Output result as JSON
                print(json.dumps({{
                    "peak_mb": peak / 1024 / 1024,
                    "current_mb": current / 1024 / 1024,
                    "exit_code": result.exit_code,
                }}))

            except Exception as e:
                tracemalloc.stop()
                print(json.dumps({{"error": str(e)}}))
                sys.exit(1)
        """).strip()

        return script


def measure_import_memory() -> float:
    """Measure memory used by just importing prefect.cli.

    This is useful for understanding baseline memory overhead.
    """
    script = textwrap.dedent("""
        import json
        import tracemalloc

        tracemalloc.start()

        from prefect.cli import app

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        print(json.dumps({
            "peak_mb": peak / 1024 / 1024,
            "current_mb": current / 1024 / 1024,
        }))
    """).strip()

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        data = json.loads(result.stdout.strip())
        return data["peak_mb"]
    return 0.0
