import asyncio
import inspect
import uuid
from typing import Any, Dict, List, Optional, Set, Union

import anyio
import httpx
from typing_extensions import Literal

from prefect.client.orchestration import get_client
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


async def get_current_run_count() -> int:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://{PREFECT_RUNNER_SERVER_HOST.value()}"
            f":{PREFECT_RUNNER_SERVER_PORT.value()}/run_count"
        )
        response.raise_for_status()
        return response.json()


async def _submit_flow_to_runner(
    flow: Flow,
    parameters: Dict[str, Any],
    # capture_errors: bool = SETTING.value()?
) -> uuid.UUID:
    """
    Run a callable in the background via the runner webserver.

    Args:
        prefect_callable: the callable to run, e.g. a flow or task
        parameters: the keyword arguments to pass to the callable
        timeout: the maximum time to wait for the callable to finish
        poll_interval: the interval (in seconds) to wait between polling the callable
    """
    from prefect.engine import (
        _dynamic_key_for_task_run,
        collect_task_run_inputs,
        resolve_inputs,
    )

    async with get_client() as client:
        parent_flow_run_context = FlowRunContext.get()

        task_inputs = {
            k: await collect_task_run_inputs(v) for k, v in parameters.items()
        }

        dummy_task = Task(name=flow.name, fn=flow.fn, version=flow.version)
        parent_task_run = await client.create_task_run(
            task=dummy_task,
            flow_run_id=parent_flow_run_context.flow_run.id,
            dynamic_key=_dynamic_key_for_task_run(parent_flow_run_context, dummy_task),
            task_inputs=task_inputs,
            state=Pending(),
        )

        parameters = await resolve_inputs(parameters)

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

        flow_run_id = response.json()["flow_run_id"]

        return uuid.UUID(flow_run_id)


@sync_compatible
async def submit_to_runner(
    prefect_callable: Union[Flow, Task],
    parameters: Dict[str, Any],
) -> uuid.UUID:
    """
    Run a callable in the background via the runner webserver.

    Args:
        prefect_callable: the callable to run (only flows are supported for now, but eventually tasks)
        parameters: the keyword arguments to pass to the callable,
    """

    flow_run_id = await _submit_flow_to_runner(prefect_callable, parameters)

    if inspect.isawaitable(flow_run_id):
        return await flow_run_id
    else:
        return flow_run_id


@sync_compatible
async def submit_many_to_runner(
    prefect_callable: Union[Flow, Task], parameters_list: List[Dict[str, Any]]
) -> List[uuid.UUID]:
    """
    Run multiple callables in the background via the runner webserver, respecting the run limit.

    Args:
        prefect_callable: the callable to run (flows or tasks)
        parameters_list: a list of dictionaries, each representing keyword arguments to pass to the callable.
    """

    n_current_runs = await get_current_run_count()
    available_slots = max(0, PREFECT_RUNNER_PROCESS_LIMIT.value() - n_current_runs)

    submitted_run_ids = []
    for parameters in parameters_list[:available_slots]:
        flow_run_id = await submit_to_runner(prefect_callable, parameters)
        if inspect.isawaitable(flow_run_id):
            flow_run_id = await flow_run_id
        submitted_run_ids.append(flow_run_id)

    if (diff := len(parameters_list) - available_slots) > 0:
        logger.warning(
            f"The last {diff} runs were not submitted to the runner,"
            f" as all of the available {PREFECT_RUNNER_PROCESS_LIMIT.value()}"
            " slots were occupied. To increase the number of available slots,"
            " configure the `PREFECT_RUNNER_PROCESS_LIMIT` setting."
        )

    return submitted_run_ids


@sync_compatible
async def wait_for_submitted_runs(
    flow_run_ids: Optional[Set[uuid.UUID]] = None,
    task_run_ids: Optional[Set[uuid.UUID]] = None,
    timeout: Optional[float] = None,
    poll_interval: float = 3.0,
):
    """
    Wait for completion of any provided flow and task runs, as well as runs submitted to the
    current runner webserver, within a timeout.

    Args:
        flow_run_ids: Additional flow run IDs to wait for.
        task_run_ids: Additional task run IDs to wait for. # TODO: /task/run endpoint
        timeout: How long to wait for completion of all runs (seconds).
        poll_interval: How long to wait between polling each run's state (seconds).
    """
    flow_run_ids = flow_run_ids or set()
    if task_run_ids:
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

    async with anyio.move_on_after(timeout), get_client() as client:
        response = await client._client.get(
            f"http://{PREFECT_RUNNER_SERVER_HOST.value()}"
            f":{PREFECT_RUNNER_SERVER_PORT.value()}/run_response_details"
        )
        response.raise_for_status()
        fetched_ids = response.json()

        fetched_flow_run_ids: Set[uuid.UUID] = {
            flow_run_id
            for run_details in fetched_ids
            if (flow_run_id := run_details.get("flow_run_id"))
        }

        flow_run_ids.update(fetched_flow_run_ids)

        await asyncio.gather(
            *(wait_for_final_state("flow", run_id) for run_id in flow_run_ids)
        )
