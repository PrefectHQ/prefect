"""
Centralized Typer CLI command registration.

Used by both the default (typer) entrypoint and the cyclopts delegation path
to ensure all commands are registered before the Typer app is invoked.
"""

from __future__ import annotations


def load_typer_commands() -> None:
    """Import CLI submodules to register them with the Typer app."""
    import importlib

    modules = [
        "prefect.cli.api",
        "prefect.cli.artifact",
        "prefect.cli.block",
        "prefect.cli.cloud",
        "prefect.cli.cloud.asset",
        "prefect.cli.cloud.ip_allowlist",
        "prefect.cli.cloud.webhook",
        "prefect.cli.shell",
        "prefect.cli.concurrency_limit",
        "prefect.cli.config",
        "prefect.cli.dashboard",
        "prefect.cli.deploy",
        "prefect.cli.deployment",
        "prefect.cli.dev",
        "prefect.cli.events",
        "prefect.cli.experimental",
        "prefect.cli.flow",
        "prefect.cli.flow_run",
        "prefect.cli.global_concurrency_limit",
        "prefect.cli.profile",
        "prefect.cli.sdk",
        "prefect.cli.server",
        "prefect.cli.task",
        "prefect.cli.variable",
        "prefect.cli.work_pool",
        "prefect.cli.work_queue",
        "prefect.cli.worker",
        "prefect.cli.task_run",
        "prefect.cli.transfer",
        "prefect.events.cli.automations",
    ]

    for module in modules:
        importlib.import_module(module)
