"""
Base `prefect` command-line application and utilities
"""
import typer
import rich.console


app = typer.Typer()
console = rich.console.Console(highlight=False)


@app.command()
def version():
    """Get the current Prefect version"""
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
