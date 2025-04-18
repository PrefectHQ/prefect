from __future__ import annotations

import inspect
import logging
from typing import Any, Optional

import typer

from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error
from prefect.cli.root import app
from prefect.logging import get_logger
from prefect.task_worker import serve as task_serve
from prefect.tasks import Task
from prefect.utilities.importtools import import_object, load_module

task_app: PrefectTyper = PrefectTyper(name="task", help="Work with task scheduling.")
app.add_typer(task_app, aliases=["task"])

logger: logging.Logger = get_logger("prefect.cli.task")


def _import_tasks_from_module(module: str) -> list[Task[Any, Any]]:
    mod = load_module(module)
    return [
        obj
        for _, obj in inspect.getmembers(mod)
        if isinstance(obj, Task) and not inspect.ismodule(obj)
    ]


@task_app.command()
async def serve(
    entrypoints: Optional[list[str]] = typer.Argument(
        None,
        help="The paths to one or more tasks, in the form of `./path/to/file.py:task_func_name`.",
    ),
    module: Optional[list[str]] = typer.Option(
        None,
        "--module",
        "-m",
        help="The module(s) to import the tasks from.",
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
        module: The module(s) to import the task definitions from.
        limit: The maximum number of tasks that can be run concurrently. Defaults to 10.
    """
    if (entrypoints and any(entrypoints)) and (module and any(module)):
        exit_with_error(
            "You may provide entrypoints or modules, but not both at the same time."
        )

    if not entrypoints and not module:
        exit_with_error(
            "You must provide either `path/to/file.py:task_func` or `--module module_name`."
        )

    tasks: list[Task[Any, Any]] = []

    if entrypoints:
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
                mod, task_name = entrypoint.split(":")
                exit_with_error(
                    f"Error: {mod!r} has no function {task_name!r}.", style="red"
                )

    elif module:
        for mod in module:
            try:
                module_tasks = _import_tasks_from_module(mod)
            except Exception as e:
                exit_with_error(
                    f"Module '{mod}' could not be imported. Please check the module name and try again.\n\n{e.__class__.__name__}: {e}"
                )
            plural = "s" if len(module_tasks) != 1 else ""
            logger.debug(f"Found {len(module_tasks)} task{plural} in {mod!r}.")
            tasks.extend(module_tasks)

    if not tasks:
        sources = (
            f"entrypoints: {entrypoints!r}" if entrypoints else f"modules: {module!r}"
        )
        exit_with_error(f"No tasks found to serve in {sources}.")

    await task_serve(*tasks, limit=limit)
