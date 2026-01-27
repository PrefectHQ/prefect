#!/usr/bin/env python
"""
CLI benchmark harness for Prefect.

Three analysis modes:
  just benchmark-cli              # hyperfine wall-time benchmarks
  just benchmark-cli --profile    # pyinstrument call tree (where is time spent?)
  just benchmark-cli --imports    # import time breakdown (which imports are slow?)

Comparison mode:
  just benchmark-cli --output baseline.json   # save baseline
  just benchmark-cli --compare baseline.json  # compare with Welch's t-test

Options:
  --runs N        Number of runs per command (default: 5)
  --plot          Show terminal visualization
  --json          Output raw JSON to stdout
  --skip-memory   Skip memory profiling
  --category X    Only benchmark category: startup, local, api, all
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from .commands import get_commands
from .config import BenchmarkConfig, BenchmarkSuite
from .memory import MemoryProfiler
from .reporter import (
    console,
    print_comparison,
    print_error,
    print_info,
    print_progress,
    print_results,
    print_warning,
)
from .results import (
    compare_suites,
    create_metadata,
    load_suite,
    save_suite,
    suite_to_dict,
)
from .runner import (
    BenchmarkRunner,
    check_hyperfine,
    get_hyperfine_install_instructions,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark Prefect CLI performance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Analysis modes (mutually exclusive)
    mode = parser.add_argument_group("analysis mode")
    mode.add_argument(
        "--profile",
        action="store_true",
        help="Run pyinstrument profiling (shows call tree)",
    )
    mode.add_argument(
        "--imports",
        action="store_true",
        help="Show import time breakdown",
    )

    # Benchmark options
    bench = parser.add_argument_group("benchmark options")
    bench.add_argument(
        "--runs",
        type=int,
        default=5,
        help="Runs per command (default: 5)",
    )
    bench.add_argument(
        "--category",
        choices=["startup", "local", "api", "all"],
        default="all",
        help="Command category (default: all)",
    )
    bench.add_argument(
        "--skip-memory",
        action="store_true",
        help="Skip memory profiling",
    )

    # Output options
    out = parser.add_argument_group("output")
    out.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Save results to JSON file",
    )
    out.add_argument(
        "--compare",
        "-c",
        type=Path,
        help="Compare against baseline JSON (uses Welch's t-test)",
    )
    out.add_argument(
        "--plot",
        action="store_true",
        help="Show terminal visualization",
    )
    out.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON to stdout",
    )
    out.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output",
    )

    # Advanced
    parser.add_argument(
        "--server-url",
        default=os.environ.get("PREFECT_API_URL"),
        help="API URL for API commands (default: $PREFECT_API_URL)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=10.0,
        help="Regression threshold %% (default: 10)",
    )

    return parser.parse_args()


# =============================================================================
# Profile mode: pyinstrument call tree
# =============================================================================


def run_profile() -> int:
    """Profile CLI import with pyinstrument to see where time is spent."""
    console.print(
        "\n[bold cyan]Profiling CLI import with pyinstrument...[/bold cyan]\n"
    )

    script = """
from pyinstrument import Profiler

profiler = Profiler()
profiler.start()

from prefect.cli import app

profiler.stop()
print(profiler.output_text(unicode=True, color=True, show_all=False))
"""

    result = subprocess.run(
        ["uv", "run", "--with", "pyinstrument", "python", "-c", script],
        capture_output=False,
    )
    return result.returncode


# =============================================================================
# Import mode: python -X importtime analysis
# =============================================================================


def run_imports(top_n: int = 25) -> int:
    """Analyze import times and show slowest modules."""
    console.print("\n[bold cyan]Analyzing import times...[/bold cyan]\n")

    result = subprocess.run(
        [sys.executable, "-X", "importtime", "-c", "from prefect.cli import app"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print_error(f"Import failed: {result.stderr}")
        return 1

    # Parse importtime output: "import time: self | cumulative | module"
    imports = []
    for line in result.stderr.strip().split("\n"):
        match = re.match(r"import time:\s+(\d+)\s+\|\s+(\d+)\s+\|\s+(.+)", line)
        if match:
            self_time = int(match.group(1))
            cumulative = int(match.group(2))
            module = match.group(3).strip()
            imports.append((cumulative, self_time, module))

    imports.sort(reverse=True)

    # Print table
    from rich.table import Table

    table = Table(title=f"Top {top_n} Slowest Imports", show_header=True)
    table.add_column("Module", style="cyan")
    table.add_column("Cumulative (ms)", justify="right")
    table.add_column("Self (ms)", justify="right")
    table.add_column("", width=30)

    max_cum = imports[0][0] if imports else 1

    for cumulative, self_time, module in imports[:top_n]:
        bar_len = int((cumulative / max_cum) * 30)
        bar = "\u2588" * bar_len

        if cumulative > 100000:
            bar = f"[red]{bar}[/red]"
        elif cumulative > 50000:
            bar = f"[yellow]{bar}[/yellow]"
        else:
            bar = f"[green]{bar}[/green]"

        table.add_row(
            module,
            f"{cumulative / 1000:.1f}",
            f"{self_time / 1000:.1f}",
            bar,
        )

    console.print(table)

    # Summary
    total_ms = imports[0][0] / 1000 if imports else 0
    console.print(f"\n[bold]Total import time:[/bold] {total_ms:.0f}ms")

    # Prefect breakdown
    console.print("\n[bold]Prefect module breakdown:[/bold]")
    prefect_imports = [(c, s, m) for c, s, m in imports if "prefect" in m][:10]
    for cumulative, _, module in prefect_imports:
        console.print(f"  {module}: [yellow]{cumulative / 1000:.0f}ms[/yellow]")

    return 0


# =============================================================================
# Benchmark mode: hyperfine wall-time measurement
# =============================================================================


def run_benchmarks(args: argparse.Namespace) -> int:
    """Run hyperfine benchmarks with statistical analysis."""
    # Check hyperfine
    hyperfine_version = check_hyperfine()
    if hyperfine_version is None:
        print_error("hyperfine is required for benchmarks")
        console.print(f"\nInstall: {get_hyperfine_install_instructions()}")
        console.print("\nOr use --profile or --imports for dependency-free analysis")
        return 1

    # Build config
    config = BenchmarkConfig(
        runs=args.runs,
        warmup_runs=3,
        timeout_seconds=30,
        regression_threshold_percent=args.threshold,
        json_output=args.json,
        output_file=args.output,
        skip_memory=args.skip_memory,
        skip_cold=True,  # Focus on warm cache for consistency
        skip_warm=False,
        categories=[args.category] if args.category != "all" else None,
        server_url=args.server_url,
        compare_baseline=args.compare,
        verbose=args.verbose,
    )

    # Get commands
    commands = get_commands(
        categories=config.categories,
        include_api=config.server_url is not None,
    )

    if not commands:
        print_error("No commands to benchmark")
        return 1

    # Filter API commands if no server
    api_cmds = [c for c in commands if c.requires_server]
    if api_cmds and not config.server_url:
        print_warning(f"Skipping {len(api_cmds)} API commands (no --server-url)")
        commands = [c for c in commands if not c.requires_server]

    if not commands:
        print_error("No commands left after filtering")
        return 1

    print_info(f"Benchmarking {len(commands)} commands ({config.runs} runs each)")
    console.print()

    # Run benchmarks
    runner = BenchmarkRunner(config)
    memory_profiler = MemoryProfiler(config) if not config.skip_memory else None

    results = []
    for i, cmd in enumerate(commands, 1):
        print_progress(cmd.name, i, len(commands))
        result = runner.run_benchmark(cmd)

        if memory_profiler and result.success:
            result.peak_memory_mb = memory_profiler.measure_command(cmd)

        results.append(result)

    # Create suite
    metadata = create_metadata(hyperfine_version)
    suite = BenchmarkSuite(metadata=metadata, results=results, config=config)

    # Output
    console.print()

    if config.compare_baseline:
        try:
            baseline = load_suite(config.compare_baseline)
            comparisons = compare_suites(
                suite, baseline, config.regression_threshold_percent
            )
            print_comparison(suite, comparisons, str(config.compare_baseline))
        except FileNotFoundError:
            print_error(f"Baseline not found: {config.compare_baseline}")
            print_results(suite)
    else:
        print_results(suite)

    # Save output
    output_path = config.output_file
    if config.json_output:
        if output_path:
            save_suite(suite, output_path)
            print_info(f"Saved to {output_path}")
        else:
            print(json.dumps(suite_to_dict(suite), indent=2))
    elif output_path:
        save_suite(suite, output_path)
        print_info(f"Saved to {output_path}")

    # Plot
    if args.plot:
        _run_plot(suite, output_path, config.compare_baseline)

    # Return code
    errors = sum(1 for r in results if r.error)
    return 1 if errors > 0 else 0


def _run_plot(
    suite: BenchmarkSuite,
    output_path: Path | None,
    compare_baseline: Path | None,
) -> None:
    """Run the visualization script."""
    if not output_path:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(suite_to_dict(suite), f)
            output_path = Path(f.name)

    script_dir = Path(__file__).parent.parent
    plot_script = script_dir / "benchmark_cli_plot.py"

    if plot_script.exists():
        plot_args = ["uv", "run", str(plot_script), str(output_path)]
        if compare_baseline:
            plot_args.extend(["--compare", str(compare_baseline)])
        subprocess.run(plot_args)


# =============================================================================
# Main entry point
# =============================================================================


def main() -> int:
    args = parse_args()

    if args.profile:
        return run_profile()

    if args.imports:
        return run_imports()

    return run_benchmarks(args)


if __name__ == "__main__":
    sys.exit(main())
