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


def format_diff_with_significance(
    diff_percent: float | None,
    p_value: float,
    significant: bool,
    threshold: float,
) -> tuple[str, str]:
    """Format a diff percentage with significance indicator.

    Returns:
        Tuple of (formatted string, style).
    """
    if diff_percent is None:
        return "", ""

    sign = "+" if diff_percent > 0 else ""
    base = f"{sign}{diff_percent:.0f}%"

    # Add significance indicator
    if not significant:
        base += " ?"  # ? means not statistically significant

    # Determine style
    if diff_percent > threshold:
        style = "red" if significant else "yellow"
    elif diff_percent < -threshold:
        style = "green" if significant else "dim"
    else:
        style = "dim"

    return base, style


def print_comparison(
    suite: BenchmarkSuite,
    comparisons: list[ComparisonResult],
    baseline_path: str,
) -> None:
    """Print comparison results as a table with statistical significance."""
    print_header(suite)
    console.print(f"Comparing against: [dim]{baseline_path}[/dim]")
    console.print(
        "[dim]Note: '?' indicates difference is not statistically significant (p≥0.05)[/dim]"
    )
    console.print()

    table = Table(show_header=True, header_style="bold")
    table.add_column("Command", style="cyan", no_wrap=True)
    table.add_column("Warm (ms)", justify="right")
    table.add_column("Δ", justify="right")
    table.add_column("p-value", justify="right")
    table.add_column("Memory (MB)", justify="right")

    for comp in comparisons:
        result = comp.current

        warm = format_timing(
            result.warm_cache.mean_ms if result.warm_cache else None,
            result.warm_cache.stddev_ms if result.warm_cache else None,
        )
        memory = format_memory(result.peak_memory_mb)

        # Format diff with significance
        warm_diff, warm_style = format_diff_with_significance(
            comp.warm_diff_percent,
            comp.warm_p_value,
            comp.warm_significant,
            comp.threshold,
        )

        # Format p-value
        p_str = ""
        p_style = "dim"
        if comp.baseline is not None and comp.warm_diff_percent is not None:
            p = comp.warm_p_value
            if p < 0.001:
                p_str = "<0.001"
                p_style = "green" if comp.warm_diff_percent < 0 else "red"
            elif p < 0.05:
                p_str = f"{p:.3f}"
                p_style = "green" if comp.warm_diff_percent < 0 else "yellow"
            else:
                p_str = f"{p:.2f}"
                p_style = "dim"

        table.add_row(
            result.command,
            warm,
            Text(warm_diff, style=warm_style),
            Text(p_str, style=p_style),
            memory,
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
    """Print comparison summary with significance info."""
    total = len(comparisons)
    # Significant regressions (exceed threshold AND p < 0.05)
    regressions = sum(1 for c in comparisons if c.is_regression)
    # Significant improvements
    improvements = sum(
        1
        for c in comparisons
        if not c.is_regression
        and c.warm_significant
        and c.warm_diff_percent is not None
        and c.warm_diff_percent < -c.threshold
    )
    new = sum(1 for c in comparisons if c.baseline is None)
    errors = sum(1 for c in comparisons if c.current.error)

    console.print()
    console.print("[bold]Summary:[/bold] (using Welch's t-test, α=0.05)")

    if regressions > 0:
        console.print(f"  [red]Significant regressions: {regressions}[/red]")
    if improvements > 0:
        console.print(f"  [green]Significant improvements: {improvements}[/green]")
    if new > 0:
        console.print(f"  [blue]New commands: {new}[/blue]")
    if errors > 0:
        console.print(f"  [red]Errors: {errors}[/red]")
    if regressions == 0 and errors == 0:
        console.print(
            f"  [green]No significant regressions in {total} commands[/green]"
        )


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
