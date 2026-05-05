"""
Experimental command — kept as a deprecation alias for the now-GA plugin
diagnostics. New users should run `prefect plugins diagnose`.
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
    help="[deprecated] Plugin system diagnostics. Use `prefect plugins diagnose`.",
    version_flags=[],
    help_flags=["--help"],
)
experimental_app.command(plugins_app)


@plugins_app.command(name="diagnose")
@with_cli_exception_handling
async def diagnose() -> None:
    """[deprecated] Diagnose the plugin system."""
    from prefect.cli.plugins import _diagnose_plugins

    _cli.console.print(
        "[yellow]This command has moved to 'prefect plugins diagnose'. "
        "The 'experimental' alias will be removed in a future release.[/yellow]"
    )
    await _diagnose_plugins()
