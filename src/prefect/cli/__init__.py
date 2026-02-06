import os
import sys

# Check for cyclopts CLI (migration in progress)
_USE_CYCLOPTS = os.environ.get("PREFECT_CLI_FAST", "").lower() in ("1", "true")

# Top-level flags that should always route to typer (until help parity).
# These are only checked BEFORE the first command token to avoid collisions
# with subcommand flags like `flow serve -v 1.0` or `flow-run logs -h`.
_DELEGATE_FLAGS = {
    "--help",
    "-h",
    "--version",
    "-v",
    "--install-completion",
    "--show-completion",
}

_FLAGS_WITH_VALUES = {
    "--profile",
    "-p",
}

# Commands that have been migrated to cyclopts.
# As commands are migrated, add them here so the router sends them
# to cyclopts instead of delegating to typer.
_CYCLOPTS_COMMANDS: set[str] = set()


def _should_delegate_to_typer(args: list[str]) -> bool:
    """Determine whether to route through typer or cyclopts.

    Only inspects tokens that appear before the first command name.
    This avoids intercepting subcommand flags like -v or -h that
    have different meanings in subcommands.
    """
    if not args:
        return True

    # Scan tokens before the first command to check for delegate flags
    it = iter(args)
    for token in it:
        if token == "--":
            return True
        if token in _FLAGS_WITH_VALUES:
            next(it, None)
            continue
        if token in _DELEGATE_FLAGS:
            return True
        if token.startswith("-"):
            # Unknown flag before any command — delegate to be safe
            continue
        # First non-flag token is the command name
        return token not in _CYCLOPTS_COMMANDS

    # No command found (only flags) — delegate
    return True


if _USE_CYCLOPTS:
    try:
        from prefect.cli._cyclopts import app as _cyclopts_app
    except ImportError as _cyclopts_import_error:
        if "cyclopts" in str(_cyclopts_import_error):
            raise ImportError(
                "The new CLI requires cyclopts. Install with: uv sync --extra fast-cli"
            ) from _cyclopts_import_error
        raise

    def app() -> None:
        if _should_delegate_to_typer(sys.argv[1:]):
            import prefect.settings
            from prefect.cli._typer_loader import load_typer_commands
            from prefect.cli.root import app as typer_app

            load_typer_commands()
            typer_app()
        else:
            _cyclopts_app()

else:
    import prefect.settings
    from prefect.cli._typer_loader import load_typer_commands
    from prefect.cli.root import app

    load_typer_commands()
