#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["plotext", "rich"]
# ///
"""visualize CLI benchmark results in the terminal

usage:
    uv run scripts/benchmark_cli_plot.py results.json
    uv run scripts/benchmark_cli_plot.py current.json --compare baseline.json
    uv run scripts/benchmark_cli_plot.py results.json --metric memory
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import plotext as plt
from rich.console import Console
from rich.table import Table

console = Console()


def load_results(path: Path) -> dict:
    """load benchmark results from JSON"""
    with open(path) as f:
        return json.load(f)


def plot_timing_simple(
    results: dict, compare: dict | None = None, cold: bool = False
) -> None:
    """plot timing results using simple_bar for cleaner look"""
    metric = "cold_start" if cold else "warm_cache"
    title = "Cold Start (ms)" if cold else "Warm Cache (ms)"

    commands = []
    values = []

    for r in results["results"]:
        timing = r.get(metric)
        if timing and not r.get("error"):
            cmd = r["command"].replace("prefect ", "")
            commands.append(cmd)
            values.append(timing["mean_ms"])

    if not commands:
        return

    plt.clear_figure()
    plt.simple_bar(commands, values, title=title, color="cyan", width=60)
    plt.show()
    print()


def plot_memory_simple(results: dict) -> None:
    """plot memory usage using simple_bar"""
    commands = []
    values = []

    for r in results["results"]:
        mem = r.get("peak_memory_mb")
        if mem and not r.get("error"):
            cmd = r["command"].replace("prefect ", "")
            commands.append(cmd)
            values.append(mem)

    if not commands:
        return

    plt.clear_figure()
    plt.simple_bar(
        commands, values, title="Peak Memory (MB)", color="magenta", width=60
    )
    plt.show()
    print()


def plot_comparison_table(results: dict, compare: dict) -> None:
    """show comparison as a rich table with visual bars"""
    table = Table(title="Comparison vs Baseline", show_header=True, header_style="bold")
    table.add_column("Command", style="cyan")
    table.add_column("Current", justify="right")
    table.add_column("Baseline", justify="right")
    table.add_column("Diff", justify="right")
    table.add_column("", width=20)  # visual bar

    for r in results["results"]:
        timing = r.get("warm_cache")
        if not timing or r.get("error"):
            continue

        cmd = r["command"].replace("prefect ", "")

        # find baseline
        baseline_timing = None
        for cr in compare["results"]:
            if cr["command"] == r["command"]:
                baseline_timing = cr.get("warm_cache")
                break

        if not baseline_timing:
            continue

        current_ms = timing["mean_ms"]
        baseline_ms = baseline_timing["mean_ms"]
        diff_pct = ((current_ms - baseline_ms) / baseline_ms) * 100

        # visual bar (max 20 chars)
        bar_len = min(abs(int(diff_pct / 5)), 20)
        if diff_pct > 0:
            bar = "[red]" + "█" * bar_len + "[/red]"
            diff_str = f"[red]+{diff_pct:.1f}%[/red]"
        elif diff_pct < -1:
            bar = "[green]" + "█" * bar_len + "[/green]"
            diff_str = f"[green]{diff_pct:.1f}%[/green]"
        else:
            bar = "[dim]=[/dim]"
            diff_str = f"[dim]{diff_pct:.1f}%[/dim]"

        table.add_row(
            cmd,
            f"{current_ms:.0f}ms",
            f"{baseline_ms:.0f}ms",
            diff_str,
            bar,
        )

    console.print(table)
    console.print()


def print_header(results: dict) -> None:
    """print metadata header"""
    m = results.get("metadata", {})
    console.print()
    console.print("[bold cyan]CLI Benchmark Results[/bold cyan]")
    console.print(
        f"[dim]{m.get('git_sha', '?')} ({m.get('git_branch', '?')}) | "
        f"Prefect {m.get('prefect_version', '?')} | "
        f"{m.get('platform', '?')}[/dim]"
    )
    console.print()


def main() -> int:
    parser = argparse.ArgumentParser(description="visualize CLI benchmark results")
    parser.add_argument("results", type=Path, help="benchmark results JSON file")
    parser.add_argument("--compare", type=Path, help="baseline JSON to compare against")
    parser.add_argument(
        "--metric",
        choices=["all", "warm", "cold", "memory"],
        default="all",
        help="which metric to plot (default: all)",
    )

    args = parser.parse_args()

    if not args.results.exists():
        console.print(f"[red]error:[/red] {args.results} not found")
        return 1

    results = load_results(args.results)
    compare = load_results(args.compare) if args.compare else None

    print_header(results)

    if args.metric in ("all", "warm"):
        plot_timing_simple(results, compare, cold=False)

    if args.metric in ("all", "cold"):
        plot_timing_simple(results, compare, cold=True)

    if args.metric in ("all", "memory"):
        plot_memory_simple(results)

    if compare:
        plot_comparison_table(results, compare)

    return 0


if __name__ == "__main__":
    sys.exit(main())
