from typing import List

import typer

from prefect.cli._types import PrefectTyper
from prefect.cli.root import app
from prefect.task_server import serve as task_serve
from prefect.utilities.importtools import import_object

task_app = PrefectTyper(name="task", help="Commands for working with task scheduling.")
app.add_typer(task_app, aliases=["task"])


@task_app.command()
async def serve(
    entrypoints: List[str] = typer.Argument(
        ...,
        help="The paths to one or more tasks, in the form of `./path/to/file.py:task_func_name`.",
    ),
):
    """
    Starts a task server that runs scheduled tasks.

    This command initiates a task server which will monitor and execute the specified tasks.

    Args:
        entrypoints: List of strings representing the paths to one or more
            tasks. Each path should be in the format
            `./path/to/file.py:task_func_name`.
    """
    tasks = []

    for entrypoint in entrypoints:
        if ".py:" not in entrypoint:
            app.console.print(
                (
                    f"Error: Invalid entrypoint format {entrypoint!r}. It "
                    "must be of the form `./path/to/file.py:task_func_name`."
                ),
                style="red",
            )
            raise typer.Exit(1)

        try:
            tasks.append(import_object(entrypoint))
        except Exception:
            module, task_name = entrypoint.split(":")
            app.console.print(
                f"Error: {module!r} has no function {task_name!r}.", style="red"
            )
            raise typer.Exit(1)

    await task_serve(*tasks)
