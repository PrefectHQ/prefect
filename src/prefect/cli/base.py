import typer
import rich.console


app = typer.Typer()
console = rich.console.Console(highlight=False)


@app.command()
def version():
    import prefect

    console.print(prefect.__version__)


def exit_with_error(message, code=1, **kwargs):
    kwargs.setdefault("style", "red")
    console.print(message, **kwargs)
    raise typer.Exit(code)


def exit_with_success(message, **kwargs):
    kwargs.setdefault("style", "green")
    console.print(message, **kwargs)
    raise typer.Exit(0)
