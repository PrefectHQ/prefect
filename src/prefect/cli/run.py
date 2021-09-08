import typer

from prefect.cli.base import app


@app.command()
def run(path: str = None, module: str = None, deployment: str = None):
    """
    Run a flow or deployment
    """
    ...
