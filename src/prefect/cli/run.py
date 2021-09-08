import typer

from prefect.cli import app


@app.command()
def run():
    """
    Run a flow
    """
    ...
