"""
Injected orchestration dependencies
"""
from contextlib import contextmanager

ORCHESTRATION_DEPENDENCIES = {
    "task_policy": None,
    "flow_policy": None,
}


async def provide_task_policy():
    provided_policy = ORCHESTRATION_DEPENDENCIES.get("task_policy")

    if provided_policy is None:
        from prefect.orion.orchestration.core_policy import CoreTaskPolicy

        provided_policy = CoreTaskPolicy

    return provided_policy


async def provide_flow_policy():
    provided_policy = ORCHESTRATION_DEPENDENCIES.get("flow_policy")

    if provided_policy is None:
        from prefect.orion.orchestration.core_policy import CoreFlowPolicy

        provided_policy = CoreFlowPolicy

    return provided_policy


@contextmanager
def temporary_task_policy(tmp_task_policy):
    starting_task_policy = ORCHESTRATION_DEPENDENCIES["task_policy"]
    try:
        ORCHESTRATION_DEPENDENCIES["task_policy"] = tmp_task_policy
        yield
    finally:
        ORCHESTRATION_DEPENDENCIES["task_policy"] = starting_task_policy


@contextmanager
def temporary_flow_policy(tmp_flow_policy):
    starting_flow_policy = ORCHESTRATION_DEPENDENCIES["flow_policy"]
    try:
        ORCHESTRATION_DEPENDENCIES["flow_policy"] = tmp_flow_policy
        yield
    finally:
        ORCHESTRATION_DEPENDENCIES["flow_policy"] = starting_flow_policy
