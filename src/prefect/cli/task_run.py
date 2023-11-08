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
    id: Optional[UUID] = typer.Argument(None, help="ID of the task run to execute")
):
    if id is None:
        environ_task_id = os.environ.get("PREFECT__TASK_RUN_ID")
        if environ_task_id:
            id = UUID(environ_task_id)

    if id is None:
        exit_with_error("Could not determine the ID of the task run to execute.")

    # await Runner().execute_flow_run(id)
