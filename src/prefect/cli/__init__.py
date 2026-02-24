import os

# Cyclopts is the default CLI. Set PREFECT_CLI_TYPER=1 to fall back to typer.
_USE_TYPER = os.environ.get("PREFECT_CLI_TYPER", "").lower() in ("1", "true")

if _USE_TYPER:
    import prefect.settings
    from prefect.cli._typer_loader import load_typer_commands
    from prefect.cli.root import app

    load_typer_commands()

else:
    from prefect.cli._cyclopts import app
