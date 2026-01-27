"""Benchmark command definitions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BenchmarkCommand:
    """Definition of a command to benchmark."""

    name: str
    args: list[str]
    category: str
    description: str
    requires_server: bool = False
    timeout: int = 30


# Categories:
# - startup: measure CLI framework and import overhead
# - local: commands that don't need a server
# - api: commands that require a running Prefect server

BENCHMARK_COMMANDS: list[BenchmarkCommand] = [
    # Startup commands - measure import and CLI framework overhead
    BenchmarkCommand(
        name="prefect --help",
        args=["prefect", "--help"],
        category="startup",
        description="baseline import cost, minimal command",
    ),
    BenchmarkCommand(
        name="prefect --version",
        args=["prefect", "--version"],
        category="startup",
        description="minimal output, single value",
    ),
    BenchmarkCommand(
        name="prefect version",
        args=["prefect", "version"],
        category="startup",
        description="full version with integrations scan",
    ),
    # Local commands - don't require server
    BenchmarkCommand(
        name="prefect config view",
        args=["prefect", "config", "view", "--hide-sources"],
        category="local",
        description="local file reads, settings loading",
    ),
    BenchmarkCommand(
        name="prefect profile ls",
        args=["prefect", "profile", "ls"],
        category="local",
        description="profile loading, table rendering",
    ),
    BenchmarkCommand(
        name="prefect config validate",
        args=["prefect", "config", "validate"],
        category="local",
        description="settings validation",
    ),
    BenchmarkCommand(
        name="prefect server start --help",
        args=["prefect", "server", "start", "--help"],
        category="local",
        description="complex subcommand help text",
    ),
    # API commands - require a running server
    BenchmarkCommand(
        name="prefect flow ls",
        args=["prefect", "flow", "ls"],
        category="api",
        description="simple API read",
        requires_server=True,
    ),
    BenchmarkCommand(
        name="prefect flow-run ls",
        args=["prefect", "flow-run", "ls", "--limit", "5"],
        category="api",
        description="API read with pagination",
        requires_server=True,
    ),
    BenchmarkCommand(
        name="prefect deployment ls",
        args=["prefect", "deployment", "ls", "--limit", "5"],
        category="api",
        description="common operation, deployment listing",
        requires_server=True,
    ),
    BenchmarkCommand(
        name="prefect work-pool ls",
        args=["prefect", "work-pool", "ls"],
        category="api",
        description="work pool listing",
        requires_server=True,
    ),
    BenchmarkCommand(
        name="prefect variable ls",
        args=["prefect", "variable", "ls"],
        category="api",
        description="variables listing",
        requires_server=True,
    ),
]


def get_commands(
    categories: list[str] | None = None,
    include_api: bool = True,
) -> list[BenchmarkCommand]:
    """Get benchmark commands filtered by category.

    Args:
        categories: List of categories to include. If None, include all.
        include_api: Whether to include API commands (requires server).

    Returns:
        Filtered list of benchmark commands.
    """
    commands = BENCHMARK_COMMANDS

    if categories:
        commands = [c for c in commands if c.category in categories]

    if not include_api:
        commands = [c for c in commands if not c.requires_server]

    return commands
