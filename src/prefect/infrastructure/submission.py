from typing import Dict, Optional

from anyio.abc import TaskStatus

import prefect
from prefect.infrastructure.base import Infrastructure
from prefect.orion.schemas.core import FlowRun

MIN_COMPAT_PREFECT_VERSION = "2.0b12"


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
    environment = {}
    environment["PREFECT__FLOW_RUN_ID"] = flow_run.id.hex
    return environment


def _prepare_infrastructure(
    flow_run: FlowRun, infrastructure: Infrastructure
) -> Infrastructure:
    # Update the infrastructure for this specific run
    return infrastructure.copy(
        update={
            "env": {**base_flow_run_environment(flow_run), **infrastructure.env},
            "labels": {**base_flow_run_labels(flow_run), **infrastructure.labels},
            "name": infrastructure.name or flow_run.name,
        }
    )


async def submit_flow_run(
    flow_run: FlowRun,
    infrastructure: Infrastructure,
    task_status: Optional[TaskStatus] = None,
):
    infrastructure = _prepare_infrastructure(flow_run, infrastructure)
    return await infrastructure.run(task_status=task_status)
