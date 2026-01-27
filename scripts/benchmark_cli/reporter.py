"""Pretty output for benchmark results using rich."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.text import Text

from .config import BenchmarkSuite
from .results import ComparisonResult

console = Console()
error_console = Console(stderr=True)


def format_timing(mean_ms: float | None, stddev_ms: float | None) -> str:
    """Format timing as 'mean ± stddev'."""
    if mean_ms is None:
        return "-"
    if stddev_ms is None:
        return f"{mean_ms:.0f}"
    return f"{mean_ms:.0f} ± {stddev_ms:.0f}"


def format_memory(mb: float | None) -> str:
    """Format memory in MB."""
    if mb is None:
        return "-"
    return f"{mb:.1f}"


def get_status_style(status: str) -> str:
    """Get rich style for a status string."""
    if status == "OK":
        return "green"
    elif status == "NEW":
        return "blue"
    elif status == "ERROR":
        return "red"
    elif status.startswith("+"):
        return "yellow"
    elif status.startswith("-"):
        return "cyan"
    return ""


def print_header(suite: BenchmarkSuite) -> None:
    """Print the benchmark suite header."""
    m = suite.metadata
    console.print()
    console.print(f"[bold]CLI Benchmark Results[/bold] ({m.timestamp[:10]})")
    console.print(
        f"Git: [cyan]{m.git_sha}[/cyan] ({m.git_branch}) | "
        f"Python {m.python_version} | "
        f"{m.platform}"
    )
    console.print(f"Prefect {m.prefect_version} | hyperfine {m.hyperfine_version}")
    console.print()


def print_results(suite: BenchmarkSuite) -> None:
    """Print benchmark results as a table."""
    print_header(suite)

    table = Table(show_header=True, header_style="bold")
    table.add_column("Command", style="cyan", no_wrap=True)
    table.add_column("Category", style="dim")
    table.add_column("Cold (ms)", justify="right")
    table.add_column("Warm (ms)", justify="right")
    table.add_column("Memory (MB)", justify="right")
    table.add_column("Status", justify="center")

    for result in suite.results:
        status = "ERROR" if result.error else "OK"
        status_style = get_status_style(status)

        cold = format_timing(
            result.cold_start.mean_ms if result.cold_start else None,
            result.cold_start.stddev_ms if result.cold_start else None,
        )
        warm = format_timing(
            result.warm_cache.mean_ms if result.warm_cache else None,
            result.warm_cache.stddev_ms if result.warm_cache else None,
        )
        memory = format_memory(result.peak_memory_mb)

        table.add_row(
            result.command,
            result.category,
            cold,
            warm,
            memory,
            Text(status, style=status_style),
        )

    console.print(table)
    print_summary(suite)


def print_comparison(
    suite: BenchmarkSuite,
    comparisons: list[ComparisonResult],
    baseline_path: str,
) -> None:
    """Print comparison results as a table."""
    print_header(suite)
    console.print(f"Comparing against: [dim]{baseline_path}[/dim]")
    console.print()

    table = Table(show_header=True, header_style="bold")
    table.add_column("Command", style="cyan", no_wrap=True)
    table.add_column("Category", style="dim")
    table.add_column("Cold (ms)", justify="right")
    table.add_column("vs baseline", justify="right")
    table.add_column("Warm (ms)", justify="right")
    table.add_column("vs baseline", justify="right")
    table.add_column("Memory (MB)", justify="right")
    table.add_column("Status", justify="center")

    for comp in comparisons:
        result = comp.current
        status = comp.status
        status_style = get_status_style(status)

        cold = format_timing(
            result.cold_start.mean_ms if result.cold_start else None,
            result.cold_start.stddev_ms if result.cold_start else None,
        )
        warm = format_timing(
            result.warm_cache.mean_ms if result.warm_cache else None,
            result.warm_cache.stddev_ms if result.warm_cache else None,
        )
        memory = format_memory(result.peak_memory_mb)

        # Format diff percentages
        cold_diff = ""
        warm_diff = ""
        if comp.cold_diff_percent is not None:
            sign = "+" if comp.cold_diff_percent > 0 else ""
            cold_diff = f"{sign}{comp.cold_diff_percent:.0f}%"
        if comp.warm_diff_percent is not None:
            sign = "+" if comp.warm_diff_percent > 0 else ""
            warm_diff = f"{sign}{comp.warm_diff_percent:.0f}%"

        # Style diffs
        cold_diff_style = ""
        warm_diff_style = ""
        if comp.cold_diff_percent is not None:
            if comp.cold_diff_percent > comp.threshold:
                cold_diff_style = "red"
            elif comp.cold_diff_percent < -comp.threshold:
                cold_diff_style = "green"
        if comp.warm_diff_percent is not None:
            if comp.warm_diff_percent > comp.threshold:
                warm_diff_style = "red"
            elif comp.warm_diff_percent < -comp.threshold:
                warm_diff_style = "green"

        table.add_row(
            result.command,
            result.category,
            cold,
            Text(cold_diff, style=cold_diff_style),
            warm,
            Text(warm_diff, style=warm_diff_style),
            memory,
            Text(status, style=status_style),
        )

    console.print(table)
    print_comparison_summary(comparisons)


def print_summary(suite: BenchmarkSuite) -> None:
    """Print summary statistics."""
    total = len(suite.results)
    errors = sum(1 for r in suite.results if r.error)
    successful = total - errors

    console.print()
    console.print(f"[bold]Summary:[/bold] {successful}/{total} commands completed")

    if errors > 0:
        console.print(f"[red]{errors} errors[/red]")
        for r in suite.results:
            if r.error:
                console.print(f"  [dim]{r.command}:[/dim] {r.error}")


def print_comparison_summary(comparisons: list[ComparisonResult]) -> None:
    """Print comparison summary."""
    total = len(comparisons)
    regressions = sum(1 for c in comparisons if c.is_regression)
    improvements = sum(
        1
        for c in comparisons
        if not c.is_regression
        and (
            (c.cold_diff_percent is not None and c.cold_diff_percent < -c.threshold)
            or (c.warm_diff_percent is not None and c.warm_diff_percent < -c.threshold)
        )
    )
    new = sum(1 for c in comparisons if c.baseline is None)
    errors = sum(1 for c in comparisons if c.current.error)

    console.print()
    console.print("[bold]Summary:[/bold]")

    if regressions > 0:
        console.print(f"  [red]Regressions: {regressions}[/red]")
    if improvements > 0:
        console.print(f"  [green]Improvements: {improvements}[/green]")
    if new > 0:
        console.print(f"  [blue]New commands: {new}[/blue]")
    if errors > 0:
        console.print(f"  [red]Errors: {errors}[/red]")
    if regressions == 0 and errors == 0:
        console.print(f"  [green]All {total} commands within threshold[/green]")


def print_error(message: str) -> None:
    """Print an error message."""
    error_console.print(f"[red]Error:[/red] {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    error_console.print(f"[yellow]Warning:[/yellow] {message}")


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"[blue]Info:[/blue] {message}")


def print_progress(command: str, index: int, total: int) -> None:
    """Print progress indicator."""
    console.print(
        f"[dim][{index}/{total}][/dim] Benchmarking [cyan]{command}[/cyan]..."
    )
