import os
import sys

# Check for cyclopts CLI (migration in progress)
_USE_CYCLOPTS = os.environ.get("PREFECT_CLI_FAST", "").lower() in ("1", "true")

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

_CYCLOPTS_COMMANDS = {
    "config",
}


def _first_command(args: list[str]) -> str | None:
    it = iter(args)
    for token in it:
        if token == "--":
            return None
        if token in _FLAGS_WITH_VALUES:
            next(it, None)
            continue
        if token.startswith("-"):
            continue
        return token
    return None


def _should_delegate_to_typer(args: list[str]) -> bool:
    # No args means default help; keep Typer output until parity is established.
    if not args:
        return True
    if any(flag in args for flag in _DELEGATE_FLAGS):
        return True
    command = _first_command(args)
    return command not in _CYCLOPTS_COMMANDS


if _USE_CYCLOPTS:
    # New CLI implementation using cyclopts
    try:
        from prefect.cli._cyclopts import app as _cyclopts_app
    except ImportError as _cyclopts_import_error:
        if "cyclopts" in str(_cyclopts_import_error):
            raise ImportError(
                "The new CLI requires cyclopts. Install with: pip install prefect[fast-cli]"
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
    # Current CLI implementation using typer
    import prefect.settings
    from prefect.cli._typer_loader import load_typer_commands
    from prefect.cli.root import app

    load_typer_commands()
