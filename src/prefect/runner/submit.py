import asyncio
import inspect
import uuid
from typing import Any, Dict, List, Optional, Union, overload

import anyio
import httpx
from typing_extensions import Literal

from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import FlowRunFilter, TaskRunFilter
from prefect.client.schemas.objects import FlowRun
from prefect.context import FlowRunContext
from prefect.flows import Flow
from prefect.logging import get_logger
from prefect.settings import (
    PREFECT_RUNNER_PROCESS_LIMIT,
    PREFECT_RUNNER_SERVER_HOST,
    PREFECT_RUNNER_SERVER_PORT,
)
from prefect.states import Pending
from prefect.tasks import Task
from prefect.utilities.asyncutils import sync_compatible

logger = get_logger("webserver")


async def _submit_flow_to_runner(
    flow: Flow,
    parameters: Dict[str, Any],
    retry_failed_submissions: bool = True,
) -> FlowRun:
    """
    Run a flow in the background via the runner webserver.

    Args:
        flow: the flow to create a run for and execute in the background
        parameters: the keyword arguments to pass to the callable
        timeout: the maximum time to wait for the callable to finish
        poll_interval: the interval (in seconds) to wait between polling the callable

    Returns:
        A `FlowRun` object representing the flow run that was submitted.
    """
    from prefect.utilities.engine import (
        _dynamic_key_for_task_run,
        collect_task_run_inputs,
        resolve_inputs,
    )

    async with get_client() as client:
        if not retry_failed_submissions:
            # TODO - configure the client to not retry 429s coming from the
            # webserver
            pass

        parent_flow_run_context = FlowRunContext.get()

        task_inputs = {
            k: await collect_task_run_inputs(v) for k, v in parameters.items()
        }
        parameters = await resolve_inputs(parameters)
        dummy_task = Task(name=flow.name, fn=flow.fn, version=flow.version)
        parent_task_run = await client.create_task_run(
            task=dummy_task,
            flow_run_id=(
                parent_flow_run_context.flow_run.id if parent_flow_run_context else None
            ),
            dynamic_key=(
                _dynamic_key_for_task_run(parent_flow_run_context, dummy_task)
                if parent_flow_run_context
                else str(uuid.uuid4())
            ),
            task_inputs=task_inputs,
            state=Pending(),
        )

        response = await client._client.post(
            (
                f"http://{PREFECT_RUNNER_SERVER_HOST.value()}"
                f":{PREFECT_RUNNER_SERVER_PORT.value()}"
                "/flow/run"
            ),
            json={
                "entrypoint": flow._entrypoint,
                "parameters": flow.serialize_parameters(parameters),
                "parent_task_run_id": str(parent_task_run.id),
            },
        )
        response.raise_for_status()

        return FlowRun.model_validate(response.json())


@overload
def submit_to_runner(
    prefect_callable: Union[Flow, Task],
    parameters: Dict[str, Any],
    retry_failed_submissions: bool = True,
) -> FlowRun:
    ...


@overload
def submit_to_runner(
    prefect_callable: Union[Flow, Task],
    parameters: List[Dict[str, Any]],
    retry_failed_submissions: bool = True,
) -> List[FlowRun]:
    ...


@sync_compatible
async def submit_to_runner(
    prefect_callable: Union[Flow, Task],
    parameters: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None,
    retry_failed_submissions: bool = True,
) -> Union[FlowRun, List[FlowRun]]:
    """
    Submit a callable in the background via the runner webserver one or more times.

    Args:
        prefect_callable: the callable to run (only flows are supported for now, but eventually tasks)
        parameters: keyword arguments to pass to the callable. May be a list of dictionaries where
            each dictionary represents a discrete invocation of the callable
        retry_failed_submissions: Whether to retry failed submissions to the runner webserver.
    """
    if not isinstance(prefect_callable, (Flow, Task)):
        raise TypeError(
            "The `submit_to_runner` utility only supports submitting flows and tasks."
        )

    parameters = parameters or {}
    if isinstance(parameters, List):
        return_single = False
    elif isinstance(parameters, dict):
        parameters = [parameters]
        return_single = True
    else:
        raise TypeError("Parameters must be a dictionary or a list of dictionaries.")

    submitted_runs = []
    unsubmitted_parameters = []

    for p in parameters:
        try:
            flow_run = await _submit_flow_to_runner(
                prefect_callable, p, retry_failed_submissions
            )
            if inspect.isawaitable(flow_run):
                flow_run = await flow_run
            submitted_runs.append(flow_run)
        except httpx.ConnectError as exc:
            raise RuntimeError(
                "Failed to connect to the `Runner` webserver. Ensure that the server is"
                " running and reachable. You can run the webserver either by starting"
                " your `serve` process with `webserver=True`, or by setting"
                " `PREFECT_RUNNER_SERVER_ENABLE=True`."
            ) from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                unsubmitted_parameters.append(p)
            else:
                raise exc

    if unsubmitted_parameters:
        logger.warning(
            f"Failed to submit {len(unsubmitted_parameters)} runs to the runner, as all"
            f" of the available {PREFECT_RUNNER_PROCESS_LIMIT.value()} slots were"
            " occupied. To increase the number of available slots, configure"
            " the`PREFECT_RUNNER_PROCESS_LIMIT` setting."
        )

    # If one run was submitted, return the corresponding FlowRun directly
    if return_single:
        return submitted_runs[0]
    return submitted_runs


@sync_compatible
async def wait_for_submitted_runs(
    flow_run_filter: Optional[FlowRunFilter] = None,
    task_run_filter: Optional[TaskRunFilter] = None,
    timeout: Optional[float] = None,
    poll_interval: float = 3.0,
):
    """
    Wait for completion of any provided flow runs (eventually task runs), as well as subflow runs
    of the current flow run (if called from within a flow run and subflow runs exist).

    Args:
        flow_run_filter: A filter to apply to the flow runs to wait for.
        task_run_filter: A filter to apply to the task runs to wait for. # TODO: /task/run
        timeout: How long to wait for completion of all runs (seconds).
        poll_interval: How long to wait between polling each run's state (seconds).
    """

    parent_flow_run_id = ctx.flow_run.id if (ctx := FlowRunContext.get()) else None

    if task_run_filter:
        raise NotImplementedError("Waiting for task runs is not yet supported.")

    async def wait_for_final_state(
        run_type: Literal["flow", "task"], run_id: uuid.UUID
    ):
        read_run_method = getattr(client, f"read_{run_type}_run")
        while True:
            run = await read_run_method(run_id)
            if run.state and run.state.is_final():
                return run_id
            await anyio.sleep(poll_interval)

    async with get_client() as client:
        with anyio.move_on_after(timeout):
            flow_runs_to_wait_for = (
                await client.read_flow_runs(flow_run_filter=flow_run_filter)
                if flow_run_filter
                else []
            )

            if parent_flow_run_id is not None:
                subflow_runs = await client.read_flow_runs(
                    flow_run_filter=FlowRunFilter(
                        parent_flow_run_id=dict(any_=[parent_flow_run_id])
                    )
                )

                flow_runs_to_wait_for.extend(subflow_runs)

            await asyncio.gather(
                *(wait_for_final_state("flow", run.id) for run in flow_runs_to_wait_for)
            )
