#!/usr/bin/env python
"""
CLI benchmark harness for Prefect.

Measures cold start time, warm cache time, and memory usage of CLI commands
using hyperfine for accurate wall-time measurement.

Usage:
    uv run -m scripts.benchmark_cli [OPTIONS]

Examples:
    # Run all benchmarks
    uv run -m scripts.benchmark_cli

    # Quick check (fewer runs, startup only)
    uv run -m scripts.benchmark_cli --runs 3 --skip-memory --category startup

    # JSON output for CI
    uv run -m scripts.benchmark_cli --json --output results.json

    # Compare against baseline
    uv run -m scripts.benchmark_cli --compare baseline.json

    # With server for API commands
    uv run -m scripts.benchmark_cli --server-url http://127.0.0.1:4200/api
"""

from __future__ import annotations

import argparse
import os
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

    parser.add_argument(
        "--runs",
        type=int,
        default=10,
        help="Number of benchmark runs per command (default: 10)",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=3,
        help="Number of warmup runs for warm cache tests (default: 3)",
    )
    parser.add_argument(
        "--category",
        choices=["startup", "local", "api", "all"],
        default="all",
        help="Category of commands to benchmark (default: all)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file path (default: stdout for JSON, .benchmarks/results.json)",
    )
    parser.add_argument(
        "--compare",
        type=Path,
        help="Baseline JSON file to compare against",
    )
    parser.add_argument(
        "--skip-memory",
        action="store_true",
        help="Skip memory profiling (faster)",
    )
    parser.add_argument(
        "--skip-cold",
        action="store_true",
        help="Skip cold start tests (faster)",
    )
    parser.add_argument(
        "--skip-warm",
        action="store_true",
        help="Skip warm cache tests",
    )
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
        help="Regression threshold percentage (default: 10.0)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Timeout per command in seconds (default: 30)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Show visual charts after benchmarking",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Check hyperfine is installed
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
        warmup_runs=args.warmup,
        timeout_seconds=args.timeout,
        regression_threshold_percent=args.threshold,
        json_output=args.json,
        output_file=args.output,
        skip_memory=args.skip_memory,
        skip_cold=args.skip_cold,
        skip_warm=args.skip_warm,
        categories=[args.category] if args.category != "all" else None,
        server_url=args.server_url,
        compare_baseline=args.compare,
        verbose=args.verbose,
    )

    # Get commands to benchmark
    include_api = config.server_url is not None
    commands = get_commands(
        categories=config.categories,
        include_api=include_api,
    )

    if not commands:
        print_error("No commands to benchmark")
        return 1

    # Warn about API commands if no server
    api_commands = [c for c in commands if c.requires_server]
    if api_commands and not config.server_url:
        print_warning(
            f"Skipping {len(api_commands)} API commands (no --server-url or PREFECT_API_URL)"
        )
        commands = [c for c in commands if not c.requires_server]

    if not commands:
        print_error("No commands to benchmark after filtering")
        return 1

    print_info(f"Benchmarking {len(commands)} commands with {config.runs} runs each")
    if config.skip_cold:
        print_info("Skipping cold start tests")
    if config.skip_warm:
        print_info("Skipping warm cache tests")
    if config.skip_memory:
        print_info("Skipping memory profiling")
    console.print()

    # Initialize runner and profiler
    runner = BenchmarkRunner(config)
    memory_profiler = MemoryProfiler(config) if not config.skip_memory else None

    # Run benchmarks
    results = []
    for i, cmd in enumerate(commands, 1):
        print_progress(cmd.name, i, len(commands))

        # Run timing benchmarks
        result = runner.run_benchmark(cmd)

        # Run memory profiling
        if memory_profiler and result.success:
            result.peak_memory_mb = memory_profiler.measure_command(cmd)

        results.append(result)

    # Create suite
    metadata = create_metadata(hyperfine_version)
    suite = BenchmarkSuite(metadata=metadata, results=results, config=config)

    # Output results
    console.print()

    if config.compare_baseline:
        try:
            baseline = load_suite(config.compare_baseline)
            comparisons = compare_suites(
                suite, baseline, config.regression_threshold_percent
            )
            print_comparison(suite, comparisons, str(config.compare_baseline))

            # Check for regressions
            regressions = [c for c in comparisons if c.is_regression]
            if regressions:
                print_warning(f"{len(regressions)} regression(s) detected")
        except FileNotFoundError:
            print_error(f"Baseline file not found: {config.compare_baseline}")
            print_results(suite)
    else:
        print_results(suite)

    # Save JSON output
    output_path = config.output_file
    if config.json_output:
        import json

        output_data = suite_to_dict(suite)
        if output_path:
            save_suite(suite, output_path)
            print_info(f"Results saved to {output_path}")
        else:
            console.print()
            print(json.dumps(output_data, indent=2))
    elif output_path:
        save_suite(suite, output_path)
        print_info(f"Results saved to {output_path}")

    # Show plots if requested
    if args.plot:
        # Save to temp file if no output path specified
        if not output_path:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                import json

                json.dump(suite_to_dict(suite), f)
                output_path = Path(f.name)

        # Find the plot script
        script_dir = Path(__file__).parent.parent
        plot_script = script_dir / "benchmark_cli_plot.py"

        if plot_script.exists():
            plot_args = ["uv", "run", str(plot_script), str(output_path)]
            if config.compare_baseline:
                plot_args.extend(["--compare", str(config.compare_baseline)])
            subprocess.run(plot_args)
        else:
            print_warning(f"Plot script not found: {plot_script}")

    # Return non-zero if there were errors or regressions
    errors = sum(1 for r in results if r.error)
    if errors > 0:
        return 1

    if config.compare_baseline:
        try:
            baseline = load_suite(config.compare_baseline)
            comparisons = compare_suites(
                suite, baseline, config.regression_threshold_percent
            )
            if any(c.is_regression for c in comparisons):
                return 1
        except FileNotFoundError:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
