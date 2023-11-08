from typing import Optional
from uuid import UUID

import typer

from prefect.cli._types import PrefectTyper
from prefect.cli.root import app

task_run_app = PrefectTyper(
    name="task-run", help="Commands for interacting with flow runs."
)
app.add_typer(task_run_app, aliases=["task-runs"])


@task_run_app.command()
async def execute(
    id: Optional[UUID] = typer.Argument(None, help="ID of the flow run to execute")
):
    app.console.print("One task execution coming right up!")
