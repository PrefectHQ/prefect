"""Prefect CLI powered by cyclopts."""

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
        cyclopts.Parameter("--prompt", help="Toggle interactive prompts."),
    ] = None,
):
    """Prefect CLI for workflow orchestration."""
    _setup_and_run(tokens, profile=profile, prompt=prompt)


def _setup_and_run(
    tokens: tuple[str, ...],
    *,
    profile: Optional[str] = None,
    prompt: Optional[bool] = None,
) -> None:
    """Environment setup and command dispatch."""
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


# Short flags that need rewriting before cyclopts meta parses them.
# Cyclopts meta processes ALL tokens, so a short flag like -p would be
# greedily consumed as --profile even when it appears after a subcommand
# (where it means --pool).  We rewrite top-level short flags to their
# long form before cyclopts sees them; subcommand flags pass through.
_TOP_LEVEL_SHORT_FLAGS = {"-p": "--profile"}

# Multi-character short flags (e.g. -jv, -cl) that typer/click accept
# but cyclopts splits into stacked single-char flags (-j -v).  These
# are rewritten to their long forms before cyclopts parses them.
_MULTICHAR_SHORT_FLAGS = {
    "-jv": "--job-variable",
    "-cl": "--concurrency-limit",
}


def _normalize_top_level_flags(args: list[str]) -> list[str]:
    """Rewrite short flags to long form when they appear before the command.

    Only rewrites flags that appear before the first non-flag token (the
    command name).  After the command, all tokens pass through unchanged
    so subcommand flags like ``worker start -p pool`` are not affected.
    """
    result = []
    seen_command = False
    for token in args:
        if seen_command:
            result.append(_MULTICHAR_SHORT_FLAGS.get(token, token))
        elif token in _TOP_LEVEL_SHORT_FLAGS:
            result.append(_TOP_LEVEL_SHORT_FLAGS[token])
        elif not token.startswith("-"):
            seen_command = True
            result.append(token)
        else:
            result.append(token)
    return result


def app() -> None:
    """Entry point that invokes the meta app for global option handling."""
    args = sys.argv[1:]
    # Fast path: --version / -v prints just the version string and exits
    # without loading settings, logging, or heavy imports.  We can't use
    # cyclopts' version_flags because subcommands like `deploy` and
    # `flow serve` also accept --version as a parameter.
    if args and args[0] in ("--version", "-v"):
        import prefect

        print(prefect.__version__)
        raise SystemExit(0)
    _app.meta(_normalize_top_level_flags(args))


# =============================================================================
# Command registrations
# =============================================================================

# --- deploy ---
from prefect.cli.deploy import deploy_app, init  # noqa: E402

_app.command(deploy_app)

# --- init (root-level command, mirrors typer's @app.command() in deploy/_commands.py) ---
_app.command(init, name="init")


# --- flow ---
from prefect.cli.flow import flow_app  # noqa: E402

_app.command(flow_app)


# --- flow-run ---
from prefect.cli.flow_run import flow_run_app  # noqa: E402

_app.command(flow_run_app)


# --- deployment ---
from prefect.cli.deployment import deployment_app  # noqa: E402

_app.command(deployment_app)


# --- server ---
from prefect.cli.server import server_app  # noqa: E402

_app.command(server_app)

# --- worker ---
from prefect.cli.worker import worker_app  # noqa: E402

_app.command(worker_app)

# --- shell ---
from prefect.cli.shell import shell_app  # noqa: E402

_app.command(shell_app)

# --- config ---
from prefect.cli.config import config_app  # noqa: E402

_app.command(config_app)

# --- profile ---
from prefect.cli.profile import profile_app  # noqa: E402

_app.command(profile_app)


# --- cloud ---
from prefect.cli.cloud import cloud_app  # noqa: E402

_app.command(cloud_app)


# --- work-pool ---
from prefect.cli.work_pool import work_pool_app  # noqa: E402

_app.command(work_pool_app)


# --- work-queue ---
from prefect.cli.work_queue import work_queue_app  # noqa: E402

_app.command(work_queue_app)


# --- variable ---
from prefect.cli.variable import variable_app  # noqa: E402

_app.command(variable_app)


# --- block ---
from prefect.cli.block import block_app  # noqa: E402

_app.command(block_app)


# --- concurrency-limit ---
from prefect.cli.concurrency_limit import concurrency_limit_app  # noqa: E402

_app.command(concurrency_limit_app)


# --- global-concurrency-limit ---
from prefect.cli.global_concurrency_limit import (  # noqa: E402
    global_concurrency_limit_app,
)

_app.command(global_concurrency_limit_app)


# --- artifact ---
from prefect.cli.artifact import artifact_app  # noqa: E402

_app.command(artifact_app)


# --- experimental ---
from prefect.cli.experimental import experimental_app  # noqa: E402

_app.command(experimental_app)


# --- automation ---
from prefect.cli.automation import automation_app  # noqa: E402

_app.command(automation_app)


# --- events ---
from prefect.cli.events import events_app  # noqa: E402

_app.command(events_app)


# --- task ---
from prefect.cli.task import task_app  # noqa: E402

_app.command(task_app)


# --- task-run ---
from prefect.cli.task_run import task_run_app  # noqa: E402

_app.command(task_run_app)


# --- api ---
from prefect.cli.api import api_app  # noqa: E402

_app.command(api_app)


# --- dashboard ---
from prefect.cli.dashboard import dashboard_app  # noqa: E402

_app.command(dashboard_app)


# --- dev ---
from prefect.cli.dev import dev_app  # noqa: E402

_app.command(dev_app)


# --- sdk ---
from prefect.cli.sdk import sdk_app  # noqa: E402

_app.command(sdk_app)


# --- transfer ---
from prefect.cli.transfer import transfer_app  # noqa: E402

_app.command(transfer_app)


# --- version ---
from prefect.cli.version import version  # noqa: E402

_app.command(version, name="version")
