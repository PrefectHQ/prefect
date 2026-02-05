"""
Prefect CLI powered by cyclopts.

This is the new CLI implementation being migrated from typer to cyclopts.
Enable with PREFECT_CLI_FAST=1 during the migration period.

Commands not yet migrated will delegate to the existing typer implementation.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Annotated, Optional

import cyclopts
from rich.console import Console
from rich.theme import Theme


# Lazy version lookup - only imports prefect when needed
def _get_version() -> str:
    import prefect

    return prefect.__version__


_app = cyclopts.App(
    name="prefect",
    help="Prefect CLI for workflow orchestration.",
    version=_get_version,
)

# Configure meta app group for global options
_app.meta.group_parameters = cyclopts.Group("Session Parameters", sort_key=0)

# Global console instance, configured by the root callback
console: Console = Console(
    highlight=False,
    theme=Theme({"prompt.choices": "bold blue"}),
)

# Track whether prompt mode is forced
_prompt_override: Optional[bool] = None


def is_interactive() -> bool:
    """Check if the CLI should prompt for input."""
    if _prompt_override is not None:
        return _prompt_override
    return console.is_interactive


@_app.meta.default
def _root_callback(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
    profile: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--profile", alias="-p", help="Select a profile for this CLI run."
        ),
    ] = None,
    prompt: Annotated[
        Optional[bool],
        cyclopts.Parameter(
            "--prompt", negative="--no-prompt", help="Toggle interactive prompts."
        ),
    ] = None,
):
    """Prefect CLI for workflow orchestration."""
    global console, _prompt_override
    import prefect.context
    from prefect.logging.configuration import setup_logging
    from prefect.settings import PREFECT_CLI_PROMPT, get_current_settings

    def _run_with_settings() -> None:
        global console, _prompt_override

        settings = get_current_settings()

        # Handle --prompt (default from PREFECT_CLI_PROMPT setting)
        if prompt is None:
            _prompt_override = PREFECT_CLI_PROMPT.value()
        else:
            _prompt_override = prompt

        # Configure console
        console = Console(
            highlight=False,
            color_system="auto" if settings.cli.colors else None,
            theme=Theme({"prompt.choices": "bold blue"}),
            soft_wrap=not settings.cli.wrap_lines,
            force_interactive=_prompt_override,
        )

        # Setup logging (skip in test mode)
        if not settings.testing.test_mode:
            setup_logging()

        # Windows event loop policy
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

        # Invoke the actual command
        _app(tokens)

    # Handle --profile
    if profile and prefect.context.get_settings_context().profile.name != profile:
        try:
            with prefect.context.use_profile(
                profile, override_environment_variables=True
            ):
                _run_with_settings()
        except KeyError:
            print(f"Unknown profile {profile!r}.", file=sys.stderr)
            sys.exit(1)
    else:
        _run_with_settings()


def app():
    """Entry point that invokes the meta app for global option handling."""
    _app.meta()


def _delegate(command: str, tokens: tuple[str, ...]) -> None:
    """Delegate execution to the Typer CLI for parity."""
    from prefect.cli._typer_loader import load_typer_commands
    from prefect.cli.root import app as typer_app

    load_typer_commands()
    typer_app([command, *tokens], standalone_mode=False)


# =============================================================================
# Command groups - each delegates to real implementation when executed
# =============================================================================

# --- deploy ---
deploy_app = cyclopts.App(name="deploy", help="Create and manage deployments.")
_app.command(deploy_app)


@deploy_app.default
def deploy_default(*tokens: str):
    """Deploy flows. Run 'prefect deploy --help' for options."""
    _delegate("deploy", tokens)


# --- flow-run ---
flow_run_app = cyclopts.App(name="flow-run", help="Interact with flow runs.")
_app.command(flow_run_app)


@flow_run_app.default
def flow_run_default(*tokens: str):
    """Manage flow runs."""
    _delegate("flow-run", tokens)


# --- worker ---
worker_app = cyclopts.App(name="worker", help="Start and interact with workers.")
_app.command(worker_app)


@worker_app.default
def worker_default(*tokens: str):
    """Manage workers."""
    _delegate("worker", tokens)


# --- block ---
block_app = cyclopts.App(name="block", help="Interact with blocks.")
_app.command(block_app)


@block_app.default
def block_default(*tokens: str):
    """Manage blocks."""
    _delegate("block", tokens)


# --- config (native cyclopts) ---
from prefect.cli._cyclopts.config import config_app

_app.command(config_app)


# --- profile ---
profile_app = cyclopts.App(name="profile", help="Manage Prefect profiles.")
_app.command(profile_app)


@profile_app.default
def profile_default(*tokens: str):
    """Manage profiles."""
    _delegate("profile", tokens)


# --- server ---
server_app = cyclopts.App(name="server", help="Start and manage the Prefect server.")
_app.command(server_app)


@server_app.default
def server_default(*tokens: str):
    """Manage server."""
    _delegate("server", tokens)


# --- cloud ---
cloud_app = cyclopts.App(name="cloud", help="Interact with Prefect Cloud.")
_app.command(cloud_app)


@cloud_app.default
def cloud_default(*tokens: str):
    """Manage cloud."""
    _delegate("cloud", tokens)


# --- work-pool ---
work_pool_app = cyclopts.App(name="work-pool", help="Manage work pools.")
_app.command(work_pool_app)


@work_pool_app.default
def work_pool_default(*tokens: str):
    """Manage work pools."""
    _delegate("work-pool", tokens)


# --- variable ---
variable_app = cyclopts.App(name="variable", help="Manage Prefect variables.")
_app.command(variable_app)


@variable_app.default
def variable_default(*tokens: str):
    """Manage variables."""
    _delegate("variable", tokens)


# =============================================================================
# Less common commands - show "not implemented" for now
# =============================================================================


@_app.command(name="api")
def api_cmd(*tokens: str):
    """Interact with the Prefect API."""
    _delegate("api", tokens)


@_app.command(name="artifact")
def artifact_cmd(*tokens: str):
    """Manage artifacts."""
    _delegate("artifact", tokens)


@_app.command(name="concurrency-limit")
def concurrency_limit_cmd(*tokens: str):
    """Manage concurrency limits."""
    _delegate("concurrency-limit", tokens)


@_app.command(name="dashboard")
def dashboard_cmd(*tokens: str):
    """Open the Prefect dashboard."""
    _delegate("dashboard", tokens)


@_app.command(name="deployment")
def deployment_cmd(*tokens: str):
    """Manage deployments (legacy)."""
    _delegate("deployment", tokens)


@_app.command(name="dev")
def dev_cmd(*tokens: str):
    """Development commands."""
    _delegate("dev", tokens)


@_app.command(name="events")
def events_cmd(*tokens: str):
    """Manage events."""
    _delegate("events", tokens)


@_app.command(name="flow")
def flow_cmd(*tokens: str):
    """Manage flows."""
    _delegate("flow", tokens)


@_app.command(name="global-concurrency-limit")
def global_concurrency_limit_cmd(*tokens: str):
    """Manage global concurrency limits."""
    _delegate("global-concurrency-limit", tokens)


@_app.command(name="shell")
def shell_cmd(*tokens: str):
    """Start an interactive shell."""
    _delegate("shell", tokens)


@_app.command(name="task")
def task_cmd(*tokens: str):
    """Manage tasks."""
    _delegate("task", tokens)


@_app.command(name="task-run")
def task_run_cmd(*tokens: str):
    """Manage task runs."""
    _delegate("task-run", tokens)


@_app.command(name="work-queue")
def work_queue_cmd(*tokens: str):
    """Manage work queues."""
    _delegate("work-queue", tokens)


@_app.command(name="automations")
def automations_cmd(*tokens: str):
    """Manage automations."""
    _delegate("automations", tokens)


@_app.command(name="transfer")
def transfer_cmd(*tokens: str):
    """Transfer resources between workspaces."""
    _delegate("transfer", tokens)


# =============================================================================
# Top-level version command (separate from --version flag)
# =============================================================================


@_app.command(name="version")
def version_cmd():
    """Display detailed version information."""
    _delegate("version", ())
