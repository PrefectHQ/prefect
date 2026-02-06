"""
Prefect CLI powered by cyclopts.

This is the new CLI implementation being migrated from typer to cyclopts.
Enable with PREFECT_CLI_FAST=1 during the migration period.

Commands not yet migrated will delegate to the existing typer implementation.
"""

import asyncio
import sys
from typing import Annotated, Optional

import cyclopts
from rich.console import Console
from rich.theme import Theme

_THEME = Theme({"prompt.choices": "bold blue"})


def _get_version() -> str:
    import prefect

    return prefect.__version__


_app = cyclopts.App(
    name="prefect",
    help="Prefect CLI for workflow orchestration.",
    version=_get_version,
)

_app.meta.group_parameters = cyclopts.Group("Session Parameters", sort_key=0)

# Global console instance, reconfigured by the root callback with
# color_system, soft_wrap, and force_interactive from settings.
console: Console = Console(highlight=False, theme=_THEME)


def _is_interactive() -> bool:
    """Check if the CLI should prompt for input.

    After the root callback runs, console.is_interactive reflects
    both the --prompt/--no-prompt flag and the PREFECT_CLI_PROMPT setting
    (via Console's force_interactive parameter).
    """
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
    global console
    import prefect.context
    from prefect.logging.configuration import setup_logging
    from prefect.settings import get_current_settings

    def _run_with_settings() -> None:
        global console

        settings = get_current_settings()
        prompt_value = prompt if prompt is not None else settings.cli.prompt

        console = Console(
            highlight=False,
            color_system="auto" if settings.cli.colors else None,
            theme=_THEME,
            soft_wrap=not settings.cli.wrap_lines,
            force_interactive=prompt_value,
        )

        if not settings.testing.test_mode:
            setup_logging()

        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

        _app(tokens)

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
    """Delegate execution to the Typer CLI for commands not yet migrated."""
    from prefect.cli._typer_loader import load_typer_commands
    from prefect.cli.root import app as typer_app

    load_typer_commands()
    typer_app([command, *tokens], standalone_mode=False)


# =============================================================================
# Delegated command stubs
#
# Each stub forwards to the existing typer implementation. As commands are
# migrated, their stub here is replaced with an import of the native cyclopts
# implementation.
# =============================================================================

# --- deploy ---
deploy_app = cyclopts.App(name="deploy", help="Create and manage deployments.")
_app.command(deploy_app)


@deploy_app.default
def deploy_default(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    _delegate("deploy", tokens)


# --- flow ---
flow_app = cyclopts.App(name="flow", help="Manage flows.")
_app.command(flow_app)


@flow_app.default
def flow_default(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    _delegate("flow", tokens)


# --- flow-run ---
flow_run_app = cyclopts.App(name="flow-run", help="Interact with flow runs.")
_app.command(flow_run_app)


@flow_run_app.default
def flow_run_default(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    _delegate("flow-run", tokens)


# --- deployment ---
deployment_app = cyclopts.App(
    name="deployment", help="Manage deployments (legacy commands)."
)
_app.command(deployment_app)


@deployment_app.default
def deployment_default(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    _delegate("deployment", tokens)


# --- server ---
server_app = cyclopts.App(name="server", help="Start and manage the Prefect server.")
_app.command(server_app)


@server_app.default
def server_default(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    _delegate("server", tokens)


# --- worker ---
worker_app = cyclopts.App(name="worker", help="Start and interact with workers.")
_app.command(worker_app)


@worker_app.default
def worker_default(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    _delegate("worker", tokens)


# --- shell ---
shell_app = cyclopts.App(name="shell", help="Run shell commands as Prefect flows.")
_app.command(shell_app)


@shell_app.default
def shell_default(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    _delegate("shell", tokens)


# --- config ---
from prefect.cli._cyclopts.config import config_app

_app.command(config_app)

# --- profile ---
from prefect.cli._cyclopts.profile import profile_app

_app.command(profile_app)


# --- cloud ---
cloud_app = cyclopts.App(name="cloud", help="Interact with Prefect Cloud.")
_app.command(cloud_app)


@cloud_app.default
def cloud_default(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    _delegate("cloud", tokens)


# --- work-pool ---
work_pool_app = cyclopts.App(name="work-pool", help="Manage work pools.")
_app.command(work_pool_app)


@work_pool_app.default
def work_pool_default(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    _delegate("work-pool", tokens)


# --- work-queue ---
work_queue_app = cyclopts.App(name="work-queue", help="Manage work queues.")
_app.command(work_queue_app)


@work_queue_app.default
def work_queue_default(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    _delegate("work-queue", tokens)


# --- variable ---
variable_app = cyclopts.App(name="variable", help="Manage Prefect variables.")
_app.command(variable_app)


@variable_app.default
def variable_default(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    _delegate("variable", tokens)


# --- block ---
block_app = cyclopts.App(name="block", help="Interact with blocks.")
_app.command(block_app)


@block_app.default
def block_default(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    _delegate("block", tokens)


# --- concurrency-limit ---
concurrency_limit_app = cyclopts.App(
    name="concurrency-limit", help="Manage task-level concurrency limits."
)
_app.command(concurrency_limit_app)


@concurrency_limit_app.default
def concurrency_limit_default(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    _delegate("concurrency-limit", tokens)


# --- global-concurrency-limit ---
global_concurrency_limit_app = cyclopts.App(
    name="global-concurrency-limit", help="Manage global concurrency limits."
)
_app.command(global_concurrency_limit_app)


@global_concurrency_limit_app.default
def global_concurrency_limit_default(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    _delegate("global-concurrency-limit", tokens)


# --- artifact ---
artifact_app = cyclopts.App(name="artifact", help="Manage artifacts.")
_app.command(artifact_app)


@artifact_app.default
def artifact_default(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    _delegate("artifact", tokens)


# --- automation ---
automation_app = cyclopts.App(name="automation", help="Manage automations.")
_app.command(automation_app)


@automation_app.default
def automation_default(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    _delegate("automation", tokens)


# --- experimental ---
experimental_app = cyclopts.App(name="experimental", help="Experimental commands.")
_app.command(experimental_app)


@experimental_app.default
def experimental_default(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    _delegate("experimental", tokens)


# --- events ---
events_app = cyclopts.App(name="events", help="Manage events.")
_app.command(events_app)


@events_app.default
def events_default(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    _delegate("events", tokens)


# --- task ---
task_app = cyclopts.App(name="task", help="Manage tasks.")
_app.command(task_app)


@task_app.default
def task_default(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    _delegate("task", tokens)


# --- task-run ---
task_run_app = cyclopts.App(name="task-run", help="Manage task runs.")
_app.command(task_run_app)


@task_run_app.default
def task_run_default(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    _delegate("task-run", tokens)


# --- Simple commands (no subcommands) ---


@_app.command(name="api")
def api_cmd(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    """Interact with the Prefect API."""
    _delegate("api", tokens)


@_app.command(name="dashboard")
def dashboard_cmd(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    """Open the Prefect dashboard."""
    _delegate("dashboard", tokens)


@_app.command(name="dev")
def dev_cmd(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    """Development commands."""
    _delegate("dev", tokens)


@_app.command(name="sdk")
def sdk_cmd(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    """Generate typed Python SDK from deployments."""
    _delegate("sdk", tokens)


@_app.command(name="transfer")
def transfer_cmd(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    """Transfer resources between workspaces."""
    _delegate("transfer", tokens)


# --- version ---
from prefect.cli._cyclopts.version import version

_app.command(version, name="version")
