"""
Base `prefect` command-line application and utilities
"""
import rich.console
import typer

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = rich.console.Console(highlight=False)


def version_callback(value: bool):
    if value:
        import prefect

        console.print(prefect.__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(None, "--version", "-v", callback=version_callback)
):
    return


@app.command()
def version():
    """Get the current Prefect version."""
    # TODO: expand this to a much richer display of version and system information
    import prefect

    console.print(prefect.__version__)


def exit_with_error(message, code=1, **kwargs):
    """
    Utility to print a stylized error message and exit with a non-zero code
    """
    kwargs.setdefault("style", "red")
    console.print(message, **kwargs)
    raise typer.Exit(code)


def exit_with_success(message, **kwargs):
    """
    Utility to print a stylized success message and exit with a zero code
    """
    kwargs.setdefault("style", "green")
    console.print(message, **kwargs)
    raise typer.Exit(0)
