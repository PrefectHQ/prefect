#!/usr/bin/env python
"""
CLI benchmark harness for Prefect.

Measures performance of CLI commands using multiple analysis methods:
- Wall time benchmarking via hyperfine
- Call profiling via pyinstrument
- Import time analysis via python -X importtime

Usage:
    just benchmark-cli                    # quick benchmark
    just benchmark-cli --profile          # pyinstrument call tree
    just benchmark-cli --imports          # import time breakdown
    just benchmark-cli --compare old.json # compare against baseline
    just benchmark-cli --plot             # visual charts
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

    # Mode selection
    mode_group = parser.add_argument_group("analysis modes")
    mode_group.add_argument(
        "--profile",
        action="store_true",
        help="Run pyinstrument profiling to see where time is spent",
    )
    mode_group.add_argument(
        "--imports",
        action="store_true",
        help="Show import time breakdown (slowest modules)",
    )

    # Benchmark options
    bench_group = parser.add_argument_group("benchmark options")
    bench_group.add_argument(
        "--runs",
        type=int,
        default=5,
        help="Number of benchmark runs per command (default: 5)",
    )
    bench_group.add_argument(
        "--category",
        choices=["startup", "local", "api", "all"],
        default="all",
        help="Category of commands to benchmark (default: all)",
    )
    bench_group.add_argument(
        "--skip-memory",
        action="store_true",
        help="Skip memory profiling",
    )
    bench_group.add_argument(
        "--skip-cold",
        action="store_true",
        help="Skip cold start tests",
    )

    # Output options
    output_group = parser.add_argument_group("output options")
    output_group.add_argument(
        "--output",
        type=Path,
        help="Save results to JSON file",
    )
    output_group.add_argument(
        "--compare",
        type=Path,
        help="Compare against baseline JSON file",
    )
    output_group.add_argument(
        "--plot",
        action="store_true",
        help="Show visual charts",
    )
    output_group.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON to stdout",
    )

    # Advanced options
    parser.add_argument(
        "--server-url",
        type=str,
        default=os.environ.get("PREFECT_API_URL"),
        help="Prefect API URL for API commands (default: $PREFECT_API_URL)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=10.0,
        help="Regression threshold %% (default: 10.0)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output",
    )

    return parser.parse_args()


def run_profile_analysis() -> int:
    """Run pyinstrument profiling on CLI import."""
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


def run_import_analysis(top_n: int = 25) -> int:
    """Run import time analysis and show slowest modules."""
    console.print("\n[bold cyan]Analyzing import times...[/bold cyan]\n")

    result = subprocess.run(
        [sys.executable, "-X", "importtime", "-c", "from prefect.cli import app"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print_error(f"Import failed: {result.stderr}")
        return 1

    # Parse importtime output
    # Format: "import time: self | cumulative | module"
    lines = result.stderr.strip().split("\n")
    imports = []

    for line in lines:
        match = re.match(r"import time:\s+(\d+)\s+\|\s+(\d+)\s+\|\s+(.+)", line)
        if match:
            self_time = int(match.group(1))
            cumulative = int(match.group(2))
            module = match.group(3).strip()
            imports.append((cumulative, self_time, module))

    # Sort by cumulative time
    imports.sort(reverse=True)

    # Print as table
    from rich.table import Table

    table = Table(title=f"Top {top_n} Slowest Imports", show_header=True)
    table.add_column("Module", style="cyan")
    table.add_column("Cumulative (ms)", justify="right")
    table.add_column("Self (ms)", justify="right")
    table.add_column("", width=30)  # visual bar

    max_cumulative = imports[0][0] if imports else 1

    for cumulative, self_time, module in imports[:top_n]:
        # Visual bar
        bar_len = int((cumulative / max_cumulative) * 30)
        bar = "█" * bar_len

        # Color based on time
        if cumulative > 100000:  # > 100ms
            bar = f"[red]{bar}[/red]"
        elif cumulative > 50000:  # > 50ms
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

    # Highlight prefect modules
    console.print("\n[bold]Prefect module breakdown:[/bold]")
    prefect_imports = [(c, s, m) for c, s, m in imports if "prefect" in m][:10]
    for cumulative, self_time, module in prefect_imports:
        console.print(f"  {module}: [yellow]{cumulative / 1000:.0f}ms[/yellow]")

    return 0


def run_benchmarks(args: argparse.Namespace) -> int:
    """Run hyperfine benchmarks."""
    # Check hyperfine
    hyperfine_version = check_hyperfine()
    if hyperfine_version is None:
        print_error("hyperfine is not installed")
        console.print()
        console.print("Install hyperfine:")
        console.print(get_hyperfine_install_instructions())
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
        skip_cold=args.skip_cold,
        skip_warm=False,
        categories=[args.category] if args.category != "all" else None,
        server_url=args.server_url,
        compare_baseline=args.compare,
        verbose=args.verbose,
    )

    # Get commands
    include_api = config.server_url is not None
    commands = get_commands(
        categories=config.categories,
        include_api=include_api,
    )

    if not commands:
        print_error("No commands to benchmark")
        return 1

    # Filter API commands if no server
    api_commands = [c for c in commands if c.requires_server]
    if api_commands and not config.server_url:
        print_warning(f"Skipping {len(api_commands)} API commands (no --server-url)")
        commands = [c for c in commands if not c.requires_server]

    if not commands:
        print_error("No commands to benchmark after filtering")
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
        if not output_path:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                json.dump(suite_to_dict(suite), f)
                output_path = Path(f.name)

        script_dir = Path(__file__).parent.parent
        plot_script = script_dir / "benchmark_cli_plot.py"

        if plot_script.exists():
            plot_args = ["uv", "run", str(plot_script), str(output_path)]
            if config.compare_baseline:
                plot_args.extend(["--compare", str(config.compare_baseline)])
            subprocess.run(plot_args)

    # Return code
    errors = sum(1 for r in results if r.error)
    return 1 if errors > 0 else 0


def main() -> int:
    args = parse_args()

    # Dispatch based on mode
    if args.profile:
        return run_profile_analysis()

    if args.imports:
        return run_import_analysis()

    # Default: run benchmarks
    return run_benchmarks(args)


if __name__ == "__main__":
    sys.exit(main())
