import json

import typer

from prefect.utilities.asyncutils import run_coro_as_sync


def execute_bundle_from_file(key: str):
    """
    Loads a bundle from a file and executes it.

    Args:
        key: The key of the bundle to execute.
    """
    with open(key, "r") as f:
        bundle = json.load(f)

    from prefect.runner.runner import Runner

    run_coro_as_sync(Runner().execute_bundle(bundle))


def _execute_bundle_from_file(key: str = typer.Option(...)):
    """
    Loads a bundle from a file and executes it.

    Args:
        key: The key of the bundle to execute.
    """
    execute_bundle_from_file(key)


if __name__ == "__main__":
    typer.run(_execute_bundle_from_file)
