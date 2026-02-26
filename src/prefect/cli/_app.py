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
# Command registrations (lazy-loaded via cyclopts 4.x string imports)
# =============================================================================
# Each string is resolved only when the command is actually invoked,
# avoiding the cost of importing all 25+ command modules at startup.

_app.command("prefect.cli.deploy:deploy_app", name="deploy")
_app.command("prefect.cli.deploy:init", name="init")
_app.command("prefect.cli.flow:flow_app", name="flow", alias="flows")
_app.command("prefect.cli.flow_run:flow_run_app", name="flow-run", alias="flow-runs")
_app.command(
    "prefect.cli.deployment:deployment_app", name="deployment", alias="deployments"
)
_app.command("prefect.cli.server:server_app", name="server")
_app.command("prefect.cli.worker:worker_app", name="worker")
_app.command("prefect.cli.shell:shell_app", name="shell")
_app.command("prefect.cli.config:config_app", name="config")
_app.command("prefect.cli.profile:profile_app", name="profile", alias="profiles")
_app.command("prefect.cli.cloud:cloud_app", name="cloud")
_app.command(
    "prefect.cli.work_pool:work_pool_app", name="work-pool", alias="work-pools"
)
_app.command(
    "prefect.cli.work_queue:work_queue_app", name="work-queue", alias="work-queues"
)
_app.command("prefect.cli.variable:variable_app", name="variable")
_app.command("prefect.cli.block:block_app", name="block", alias="blocks")
_app.command(
    "prefect.cli.concurrency_limit:concurrency_limit_app",
    name="concurrency-limit",
    alias="concurrency-limits",
)
_app.command(
    "prefect.cli.global_concurrency_limit:global_concurrency_limit_app",
    name="global-concurrency-limit",
    alias="gcl",
)
_app.command("prefect.cli.artifact:artifact_app", name="artifact")
_app.command("prefect.cli.experimental:experimental_app", name="experimental")
_app.command(
    "prefect.cli.automation:automation_app", name="automation", alias="automations"
)
_app.command("prefect.cli.events:events_app", name="events", alias="event")
_app.command("prefect.cli.task:task_app", name="task")
_app.command("prefect.cli.task_run:task_run_app", name="task-run", alias="task-runs")
_app.command("prefect.cli.api:api_app", name="api")
_app.command("prefect.cli.dashboard:dashboard_app", name="dashboard")
_app.command("prefect.cli.dev:dev_app", name="dev")
_app.command("prefect.cli.sdk:sdk_app", name="sdk")
_app.command("prefect.cli.transfer:transfer_app", name="transfer")
_app.command("prefect.cli.version:version", name="version")
