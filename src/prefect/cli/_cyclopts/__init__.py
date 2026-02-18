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


_app = cyclopts.App(
    name="prefect",
    help="Prefect CLI for workflow orchestration.",
    help_flags=["--help"],
    version_flags=[],
)

_app.meta.group_parameters = cyclopts.Group("Session Parameters", sort_key=0)

# Global console instance, reconfigured by the root callback with
# color_system, soft_wrap, and force_interactive from settings.
console: Console = Console(highlight=False, theme=_THEME)


def is_interactive() -> bool:
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
        cyclopts.Parameter("--profile", help="Select a profile for this CLI run."),
    ] = None,
    prompt: Annotated[
        Optional[bool],
        cyclopts.Parameter(
            "--prompt", negative="--no-prompt", help="Toggle interactive prompts."
        ),
    ] = None,
):
    """Prefect CLI for workflow orchestration."""
    _setup_and_run(tokens, profile=profile, prompt=prompt)


def _setup_and_run(
    tokens: tuple[str, ...],
    *,
    profile: Optional[str] = None,
    prompt: Optional[bool] = None,
    delegate: bool = False,
) -> None:
    """Shared environment setup and command dispatch.

    Called from both the cyclopts meta callback (for native commands and
    ``--help``) and from ``_dispatch`` (for delegated commands that must
    bypass cyclopts argument parsing).
    """
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

        if delegate:
            _delegate(tokens[0], tokens[1:])
        else:
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


# Short flags that need rewriting before cyclopts meta parses them.
# Cyclopts meta processes ALL tokens, so a short flag like -p would be
# greedily consumed as --profile even when it appears after a subcommand
# (where it means --pool).  We rewrite top-level short flags to their
# long form before cyclopts sees them; subcommand flags pass through.
_TOP_LEVEL_SHORT_FLAGS = {"-p": "--profile"}


def _normalize_top_level_flags(args: list[str]) -> list[str]:
    """Rewrite short flags to long form when they appear before the command.

    Only rewrites flags that appear before the first non-flag token (the
    command name).  After the command, all tokens pass through unchanged
    so subcommand flags like ``worker start -p pool`` are not affected.
    """
    result = []
    seen_command = False
    it = iter(args)
    for token in it:
        if seen_command:
            result.append(token)
        elif token in _TOP_LEVEL_SHORT_FLAGS:
            result.append(_TOP_LEVEL_SHORT_FLAGS[token])
        elif not token.startswith("-"):
            seen_command = True
            result.append(token)
        else:
            result.append(token)
    return result


def _parse_global_options(
    args: list[str],
) -> tuple[Optional[str], Optional[bool], list[str]]:
    """Extract ``--profile`` and ``--prompt``/``--no-prompt`` from *args*.

    Returns ``(profile, prompt, remaining)`` where *remaining* has the
    global flags removed but subcommand tokens left untouched.
    """
    profile: Optional[str] = None
    prompt: Optional[bool] = None
    remaining: list[str] = []
    i = 0
    while i < len(args):
        if args[i] == "--profile" and i + 1 < len(args):
            profile = args[i + 1]
            i += 2
        elif args[i] == "--prompt":
            prompt = True
            i += 1
        elif args[i] == "--no-prompt":
            prompt = False
            i += 1
        else:
            remaining.append(args[i])
            i += 1
    return profile, prompt, remaining


def _dispatch(args: list[str]) -> None:
    """Route *args* to either a delegated Typer command or cyclopts.

    Delegated commands are dispatched **before** cyclopts processes the
    tokens, avoiding cyclopts splitting combined short flags like ``-jv``
    into ``-j``, ``-v``.  Native commands go through ``_app.meta()`` as
    usual.
    """
    profile, prompt, remaining = _parse_global_options(args)
    if remaining and remaining[0] in _DELEGATED_COMMANDS:
        _setup_and_run(tuple(remaining), profile=profile, prompt=prompt, delegate=True)
    else:
        _app.meta(args)


def app():
    """Entry point that invokes the meta app for global option handling."""
    _dispatch(_normalize_top_level_flags(sys.argv[1:]))


# Commands that delegate to the Typer CLI.  Dispatched from _root_callback
# *before* cyclopts parses subcommand args (cyclopts would otherwise mangle
# combined short flags like "-jv" into "-j", "-v").
_DELEGATED_COMMANDS: set[str] = {
    "api",
    "artifact",
    "automation",
    "block",
    "cloud",
    "deploy",
    "dev",
    "global-concurrency-limit",
    "task-run",
    "transfer",
    "variable",
    "work-pool",
    "work-queue",
}


def _delegate(command: str, tokens: tuple[str, ...]) -> None:
    """Delegate execution to the Typer CLI for commands not yet migrated.

    With standalone_mode=False, Click/Typer returns the exit code instead
    of calling sys.exit, and raises exceptions for usage errors (missing
    args, unknown options) instead of printing and exiting.  We catch those
    and convert them to SystemExit with the correct code so the caller
    (and our test runner) sees the right exit behavior.
    """
    import click

    from prefect.cli._typer_loader import load_typer_commands
    from prefect.cli.root import app as typer_app

    load_typer_commands()
    try:
        exit_code = typer_app([command, *tokens], standalone_mode=False)
    except click.exceptions.Exit as exc:
        raise SystemExit(exc.code)
    except click.ClickException as exc:
        exc.show()
        raise SystemExit(exc.exit_code)
    except click.Abort:
        raise SystemExit(1)
    if exit_code:
        raise SystemExit(exit_code)


# =============================================================================
# Delegated command stubs
#
# Each stub forwards to the existing typer implementation. As commands are
# migrated, their stub here is replaced with an import of the native cyclopts
# implementation.
# =============================================================================


def _delegated_app(name: str, help: str) -> cyclopts.App:
    """Create a cyclopts App for a delegated command.

    Uses help_flags=["--help"] (not ["-h", "--help"]) so that short flags
    like ``-h`` pass through to the typer implementation instead of being
    intercepted as help requests.  version_flags=[] prevents cyclopts from
    intercepting ``--version`` which some subcommands use as a value flag.
    """
    return cyclopts.App(name=name, help=help, help_flags=["--help"], version_flags=[])


# --- deploy ---
deploy_app = _delegated_app("deploy", "Create and manage deployments.")
_app.command(deploy_app)


@deploy_app.default
def deploy_default(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    _delegate("deploy", tokens)


# --- flow ---
from prefect.cli._cyclopts.flow import flow_app

_app.command(flow_app)


# --- flow-run ---
from prefect.cli._cyclopts.flow_run import flow_run_app

_app.command(flow_run_app)


# --- deployment ---
from prefect.cli._cyclopts.deployment import deployment_app

_app.command(deployment_app)


# --- server ---
from prefect.cli._cyclopts.server import server_app

_app.command(server_app)

# --- worker ---
from prefect.cli._cyclopts.worker import worker_app

_app.command(worker_app)

# --- shell ---
from prefect.cli._cyclopts.shell import shell_app

_app.command(shell_app)

# --- config ---
from prefect.cli._cyclopts.config import config_app

_app.command(config_app)

# --- profile ---
from prefect.cli._cyclopts.profile import profile_app

_app.command(profile_app)


# --- cloud ---
cloud_app = _delegated_app("cloud", "Interact with Prefect Cloud.")
_app.command(cloud_app)


@cloud_app.default
def cloud_default(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    _delegate("cloud", tokens)


# --- work-pool ---
work_pool_app = _delegated_app("work-pool", "Manage work pools.")
_app.command(work_pool_app)


@work_pool_app.default
def work_pool_default(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    _delegate("work-pool", tokens)


# --- work-queue ---
work_queue_app = _delegated_app("work-queue", "Manage work queues.")
_app.command(work_queue_app)


@work_queue_app.default
def work_queue_default(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    _delegate("work-queue", tokens)


# --- variable ---
variable_app = _delegated_app("variable", "Manage Prefect variables.")
_app.command(variable_app)


@variable_app.default
def variable_default(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    _delegate("variable", tokens)


# --- block ---
block_app = _delegated_app("block", "Interact with blocks.")
_app.command(block_app)


@block_app.default
def block_default(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    _delegate("block", tokens)


# --- concurrency-limit ---
from prefect.cli._cyclopts.concurrency_limit import concurrency_limit_app

_app.command(concurrency_limit_app)


# --- global-concurrency-limit ---
global_concurrency_limit_app = _delegated_app(
    "global-concurrency-limit", "Manage global concurrency limits."
)
_app.command(global_concurrency_limit_app)


@global_concurrency_limit_app.default
def global_concurrency_limit_default(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    _delegate("global-concurrency-limit", tokens)


# --- artifact ---
artifact_app = _delegated_app("artifact", "Manage artifacts.")
_app.command(artifact_app)


@artifact_app.default
def artifact_default(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    _delegate("artifact", tokens)


# --- automation ---
automation_app = _delegated_app("automation", "Manage automations.")
_app.command(automation_app)


@automation_app.default
def automation_default(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    _delegate("automation", tokens)


# --- experimental ---
from prefect.cli._cyclopts.experimental import experimental_app

_app.command(experimental_app)


# --- events ---
from prefect.cli._cyclopts.events import events_app

_app.command(events_app)


# --- task ---
from prefect.cli._cyclopts.task import task_app

_app.command(task_app)


# --- task-run ---
task_run_app = _delegated_app("task-run", "Manage task runs.")
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


# --- dashboard ---
from prefect.cli._cyclopts.dashboard import dashboard_app

_app.command(dashboard_app)


@_app.command(name="dev")
def dev_cmd(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    """Development commands."""
    _delegate("dev", tokens)


# --- sdk ---
from prefect.cli._cyclopts.sdk import sdk_app

_app.command(sdk_app)


@_app.command(name="transfer")
def transfer_cmd(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
):
    """Transfer resources between workspaces."""
    _delegate("transfer", tokens)


# --- version ---
from prefect.cli._cyclopts.version import version

_app.command(version, name="version")
