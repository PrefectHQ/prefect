"""Main CLI entry point for prefect-aws."""

import typer

from .ecs_worker import ecs_worker_app

app = typer.Typer(
    name="prefect-aws",
    help="CLI tool for deploying Prefect AWS infrastructure",
    no_args_is_help=True,
)

# Add the ecs-worker subcommand group
app.add_typer(ecs_worker_app, name="ecs-worker")


@app.command()
def version():
    """Show the version of prefect-aws."""
    try:
        from prefect_aws._version import __version__

        typer.echo(f"prefect-aws {__version__}")
    except ImportError:
        typer.echo("prefect-aws version unknown")


if __name__ == "__main__":
    app()
