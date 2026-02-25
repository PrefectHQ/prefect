"""
Experimental command — native cyclopts implementation.

Access experimental features (subject to change).
"""

import cyclopts

import prefect.cli._app as _cli
from prefect.cli._utilities import with_cli_exception_handling

experimental_app: cyclopts.App = cyclopts.App(
    name="experimental",
    help="Access experimental features (subject to change).",
    version_flags=[],
    help_flags=["--help"],
)

plugins_app: cyclopts.App = cyclopts.App(
    name="plugins",
    help="Plugin system diagnostics.",
    version_flags=[],
    help_flags=["--help"],
)
experimental_app.command(plugins_app)


@plugins_app.command(name="diagnose")
@with_cli_exception_handling
async def diagnose():
    """Diagnose the experimental plugin system."""
    import importlib.metadata as md

    from prefect._experimental.plugins.manager import ENTRYPOINTS_GROUP
    from prefect.settings import get_current_settings

    _cli.console.print(
        "\n[bold]Prefect Experimental Plugin System Diagnostics[/bold]\n"
    )

    # Check if enabled
    settings = get_current_settings().experiments.plugins
    enabled = settings.enabled
    _cli.console.print(f"Enabled: [{'green' if enabled else 'red'}]{enabled}[/]")

    if not enabled:
        _cli.console.print("\n[yellow]Plugin system is disabled.[/yellow]")
        _cli.console.print(
            "Set [cyan]PREFECT_EXPERIMENTS_PLUGINS_ENABLED=1[/cyan] to enable.\n"
        )
        return

    # Show configuration
    timeout = settings.setup_timeout_seconds
    allow = settings.allow
    deny = settings.deny
    strict = settings.strict
    safe = settings.safe_mode

    _cli.console.print(f"Timeout: {timeout}s")
    _cli.console.print(f"Strict mode: {strict}")
    _cli.console.print(f"Safe mode: {safe}")
    _cli.console.print(f"Allow list: {allow or 'None'}")
    _cli.console.print(f"Deny list: {deny or 'None'}")

    # Discover entry points
    _cli.console.print(
        f"\n[bold]Discoverable Plugins (entry point group: {ENTRYPOINTS_GROUP})[/bold]\n"
    )

    entry_points = list(md.entry_points(group=ENTRYPOINTS_GROUP))

    if not entry_points:
        _cli.console.print("[yellow]No plugins found.[/yellow]\n")
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

        _cli.console.print(f"  • {ep.name}: {status}")
        _cli.console.print(f"    Module: {ep.value}")

        if filtered and reason:
            _cli.console.print(f"    Reason: {reason}")

        # Try to load and get version requirement
        try:
            plugin = ep.load()
            requires = getattr(plugin, "PREFECT_PLUGIN_API_REQUIRES", ">=0.1,<1")
            _cli.console.print(f"    API requirement: {requires}")
        except Exception as e:
            _cli.console.print(f"    [red]Failed to load: {e}[/]")

        _cli.console.print()

    # Run startup hooks to show what they do
    if not safe:
        _cli.console.print("[bold]Running Startup Hooks[/bold]\n")

        from prefect import __version__
        from prefect._experimental.plugins import run_startup_hooks
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
                _cli.console.print(f"  • {summary.plugin}: {status}")

                if summary.error:
                    _cli.console.print(f"    Error: {summary.error}")
                elif summary.env_preview:
                    _cli.console.print(
                        f"    Environment variables: {len(summary.env_preview)}"
                    )
                    for k, v in summary.env_preview.items():
                        _cli.console.print(f"      {k}={v}")

                    if summary.note:
                        _cli.console.print(f"    Note: {summary.note}")
                else:
                    _cli.console.print("    No changes")

                _cli.console.print()
        else:
            _cli.console.print("[yellow]No plugins executed.[/yellow]\n")
    else:
        _cli.console.print(
            "\n[yellow]Safe mode enabled - skipping hook execution.[/yellow]"
        )
        _cli.console.print(
            "Set [cyan]PREFECT_EXPERIMENTS_PLUGINS_SAFE_MODE=0[/cyan] to execute hooks.\n"
        )
