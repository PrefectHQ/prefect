import inspect
import json
import os
import tempfile
from typing import Optional
from uuid import UUID

import typer

from prefect import Task, get_client
from prefect.cli._types import PrefectTyper
from prefect.cli.root import app
from prefect.client.schemas.filters import FlowRunFilter
from prefect.context import PrefectObjectRegistry
from prefect.deployments.steps.core import run_step
from prefect.logging.loggers import get_logger
from prefect.utilities.importtools import import_object


def load_task_from_entrypoint(
    deployment_entrypoint: str, task_function_name: str
) -> Task:
    with PrefectObjectRegistry(block_code_execution=True, capture_failures=True):
        path, _ = deployment_entrypoint.rsplit(":", maxsplit=1)
        task_entrypoint = f"{path}:{task_function_name}"
        try:
            task: Task = import_object(task_entrypoint)
        except AttributeError as exc:
            raise RuntimeError(
                f"Task function with name {task_function_name!r} not found at"
                f" {task_entrypoint!r}. "
            ) from exc
        if not isinstance(task, Task):
            raise RuntimeError(
                f"Function found at {task_entrypoint!r} is not a task. Make sure that"
                " it is decorated with '@task'."
            )
        return task


task_run_app = PrefectTyper(
    name="task-run", help="Commands for interacting with flow runs."
)
app.add_typer(task_run_app, aliases=["task-runs"])


@task_run_app.command()
async def execute(
    flow_run_id: Optional[UUID] = typer.Argument(
        None, help="ID of the task run to execute"
    ),
    task_to_run: str = typer.Argument(None, help="Name of the task to execute"),
    task_parameters: Optional[str] = typer.Option(
        None,
        "--task-parameters",
        "-p",
        help="JSON string of task parameters to pass to the task",
    ),
    pull_step: str = typer.Option(
        "prefect.deployments.steps.git_clone", help="Name of the pull step to execute"
    ),
):
    logger = get_logger("prefect.task_run.execute")

    # TODO: add more pull steps
    if pull_step not in ["prefect.deployments.steps.git_clone"]:
        raise RuntimeError(f"Pull step {pull_step!r} not supported.")

    async with get_client() as client:
        await client.read_flow_run(flow_run_id=flow_run_id)
        deployment = (
            await client.read_deployments(
                flow_run_filter=FlowRunFilter(id=dict(any_=[flow_run_id]))
            )
        )[0]

        if fetch_src_step := next(
            (step for step in deployment.pull_steps if pull_step in step), None
        ):
            step_inputs = fetch_src_step.get(pull_step, {})
            # TODO: add support for other pull steps
            branch, repo_url = step_inputs.get("branch", "main"), step_inputs.get(
                "repository", None
            )
            if not (repo_url and branch):
                raise RuntimeError(
                    f"Invalid inputs for pull step {pull_step!r}: {step_inputs!r}"
                )
        else:
            raise RuntimeError("Git clone step not found in deployment pull steps.")

        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)

            await run_step(fetch_src_step)

            repo_name = repo_url.split("/")[-1].replace(".git", "")
            task_entrypoint = f"{repo_name}-{branch}/{deployment.entrypoint}"
            task = load_task_from_entrypoint(task_entrypoint, task_to_run)

            logger.info(
                f"Task {task_to_run!r} retrieved from"
                f" {repo_url}/{deployment.entrypoint.split(':')[0]!r}"
            )

            task_state = task.with_options(persist_result=True)(
                **(json.loads(task_parameters) if task_parameters else {}),
                return_state=True,
            )
            state = await task_state if inspect.isawaitable(task_state) else task_state
            result = state.result()

            logger.info(
                f"Task {task_to_run!r} finished in {state.name!r} with result ="
                f" {await result.get()!r}"
            )
