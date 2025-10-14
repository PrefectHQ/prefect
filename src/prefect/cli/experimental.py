"""
Experimental CLI commands.

These commands provide access to experimental features that are subject to change.
"""

from __future__ import annotations

import importlib.metadata as md

from prefect._experimental.plugins.manager import ENTRYPOINTS_GROUP
from prefect.cli._types import PrefectTyper
from prefect.cli.root import app
from prefect.settings import get_current_settings

experimental_app: PrefectTyper = PrefectTyper(
    name="experimental",
    help="Access experimental features (subject to change).",
    hidden=True,  # Hidden from main help, but accessible
)
app.add_typer(experimental_app)

plugins_app: PrefectTyper = PrefectTyper(
    name="plugins",
    help="Plugin system diagnostics.",
)
experimental_app.add_typer(plugins_app)


@plugins_app.command("diagnose")
async def diagnose():
    """
    Diagnose the experimental plugin system.

    This command provides information about:
    - Whether the plugin system is enabled
    - What plugins are discoverable via entry points
    - Current configuration (timeouts, allow/deny lists)

    Note: This runs the plugin discovery but does not execute hooks.
    Use safe mode (PREFECT_EXPERIMENTS_PLUGINS_SAFE_MODE=1) to test plugin loading
    without executing hooks.
    """
    from prefect._experimental.plugins import run_startup_hooks

    app.console.print("\n[bold]Prefect Experimental Plugin System Diagnostics[/bold]\n")

    # Check if enabled
    settings = get_current_settings().experiments.plugins
    enabled = settings.enabled
    app.console.print(f"Enabled: [{'green' if enabled else 'red'}]{enabled}[/]")

    if not enabled:
        app.console.print("\n[yellow]Plugin system is disabled.[/yellow]")
        app.console.print(
            "Set [cyan]PREFECT_EXPERIMENTS_PLUGINS_ENABLED=1[/cyan] to enable.\n"
        )
        return

    # Show configuration
    timeout = settings.setup_timeout_seconds
    allow = settings.allow
    deny = settings.deny
    strict = settings.strict
    safe = settings.safe_mode

    app.console.print(f"Timeout: {timeout}s")
    app.console.print(f"Strict mode: {strict}")
    app.console.print(f"Safe mode: {safe}")
    app.console.print(f"Allow list: {allow or 'None'}")
    app.console.print(f"Deny list: {deny or 'None'}")

    # Discover entry points
    app.console.print(
        f"\n[bold]Discoverable Plugins (entry point group: {ENTRYPOINTS_GROUP})[/bold]\n"
    )

    entry_points = list(md.entry_points(group=ENTRYPOINTS_GROUP))

    if not entry_points:
        app.console.print("[yellow]No plugins found.[/yellow]\n")
        return

    for ep in entry_points:
        filtered = False
        reason = None
        if allow and ep.name not in allow:
            filtered = True
            reason = "not in allow list"
        elif deny and ep.name in deny:
            filtered = True
            reason = "in deny list"

        status_color = "red" if filtered else "green"
        status = f"[{status_color}]{'filtered' if filtered else 'active'}[/]"

        app.console.print(f"  • {ep.name}: {status}")
        app.console.print(f"    Module: {ep.value}")

        if filtered and reason:
            app.console.print(f"    Reason: {reason}")

        # Try to load and get version requirement
        try:
            plugin = ep.load()
            requires = getattr(plugin, "PREFECT_PLUGIN_API_REQUIRES", ">=0.1,<1")
            app.console.print(f"    API requirement: {requires}")
        except Exception as e:
            app.console.print(f"    [red]Failed to load: {e}[/]")

        app.console.print()

    # Run startup hooks to show what they do
    if not safe:
        app.console.print("[bold]Running Startup Hooks[/bold]\n")

        from prefect import __version__
        from prefect._experimental.plugins.spec import HookContext
        from prefect.logging import get_logger

        ctx = HookContext(
            prefect_version=__version__,
            api_url=get_current_settings().api.url,
            logger_factory=get_logger,
        )
        summaries = await run_startup_hooks(ctx)

        if summaries:
            for summary in summaries:
                status = "[red]error[/]" if summary.error else "[green]success[/]"
                app.console.print(f"  • {summary.plugin}: {status}")

                if summary.error:
                    app.console.print(f"    Error: {summary.error}")
                elif summary.env_preview:
                    app.console.print(
                        f"    Environment variables: {len(summary.env_preview)}"
                    )
                    for k, v in summary.env_preview.items():
                        app.console.print(f"      {k}={v}")

                    if summary.note:
                        app.console.print(f"    Note: {summary.note}")
                else:
                    app.console.print("    No changes")

                app.console.print()
        else:
            app.console.print("[yellow]No plugins executed.[/yellow]\n")
    else:
        app.console.print(
            "\n[yellow]Safe mode enabled - skipping hook execution.[/yellow]"
        )
        app.console.print(
            "Set [cyan]PREFECT_EXPERIMENTS_PLUGINS_SAFE_MODE=0[/cyan] to execute hooks.\n"
        )
