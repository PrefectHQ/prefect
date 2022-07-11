from typing import Dict, Optional

from anyio.abc import TaskStatus

import prefect
from prefect.infrastructure.base import Infrastructure
from prefect.orion.schemas.core import FlowRun
from prefect.settings import get_current_settings

FLOW_RUN_ENTRYPOINT = ["python", "-m", "prefect.engine"]


def base_flow_run_labels(flow_run: FlowRun) -> Dict[str, str]:
    return {
        "prefect.io/flow-run-id": str(flow_run.id),
        "prefect.io/flow-run-name": flow_run.name,
        "prefect.io/version": prefect.__version__,
    }


def base_flow_run_environment(flow_run) -> Dict[str, str]:
    """
    Generate a dictionary of environment variables for a flow run job.
    """
    environment = get_current_settings().to_environment_variables(exclude_unset=True)
    environment["PREFECT__FLOW_RUN_ID"] = flow_run.id.hex
    return environment


async def submit_flow_run(
    flow_run: FlowRun,
    infrastructure: Infrastructure,
    task_status: Optional[TaskStatus] = None,
):
    # Update the infrastructure for this specific run
    infrastructure = infrastructure.copy(
        update={
            "env": {**base_flow_run_environment(flow_run), **infrastructure.env},
            "labels": {**base_flow_run_labels(flow_run), **infrastructure.labels},
            "name": infrastructure.name or flow_run.name,
        }
    )

    return await infrastructure.run(task_status=task_status)
