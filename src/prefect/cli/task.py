from typing import List

import typer

from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error
from prefect.cli.root import app
from prefect.task_worker import serve as task_serve
from prefect.utilities.importtools import import_object

task_app = PrefectTyper(name="task", help="Work with task scheduling.")
app.add_typer(task_app, aliases=["task"])


@task_app.command()
async def serve(
    entrypoints: List[str] = typer.Argument(
        ...,
        help="The paths to one or more tasks, in the form of `./path/to/file.py:task_func_name`.",
    ),
    limit: int = typer.Option(
        10,
        help="The maximum number of tasks that can be run concurrently. Defaults to 10.",
    ),
):
    """
    Serve the provided tasks so that their runs may be submitted to and
    executed in the engine.

    Args:
        entrypoints: List of strings representing the paths to one or more
            tasks. Each path should be in the format
            `./path/to/file.py:task_func_name`.
        limit: The maximum number of tasks that can be run concurrently.
    """
    tasks = []

    for entrypoint in entrypoints:
        if ".py:" not in entrypoint:
            exit_with_error(
                (
                    f"Error: Invalid entrypoint format {entrypoint!r}. It "
                    "must be of the form `./path/to/file.py:task_func_name`."
                )
            )

        try:
            tasks.append(import_object(entrypoint))
        except Exception:
            module, task_name = entrypoint.split(":")
            exit_with_error(
                f"Error: {module!r} has no function {task_name!r}.", style="red"
            )

    await task_serve(*tasks, limit=limit)
