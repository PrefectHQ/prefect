"""
Injected orchestration dependencies
"""
from contextlib import contextmanager

ORCHESTRATION_DEPENDENCIES = {
    "task_policy": None,
    "flow_policy": None,
    "task_orchestration_parameters": dict(),
    "flow_orchestration_parameters": dict(),
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


async def provide_task_orchestration_parameters():
    provided_parameters = ORCHESTRATION_DEPENDENCIES.get(
        "task_orchestration_parameters"
    )

    if provided_parameters is None:
        provided_parameters = dict()

    return provided_parameters


async def provide_flow_orchestration_parameters():
    provided_parameters = ORCHESTRATION_DEPENDENCIES.get(
        "flow_orchestration_parameters"
    )

    if provided_parameters is None:
        provided_parameters = dict()

    return provided_parameters


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


@contextmanager
def temporary_task_orchestration_parameters(tmp_orchestration_parameters):
    starting_task_orchestration_parameters = ORCHESTRATION_DEPENDENCIES[
        "task_orchestration_parameters"
    ]
    try:
        ORCHESTRATION_DEPENDENCIES[
            "task_orchestration_parameters"
        ] = tmp_orchestration_parameters
        yield
    finally:
        ORCHESTRATION_DEPENDENCIES[
            "task_orchestration_parameters"
        ] = starting_task_orchestration_parameters


@contextmanager
def temporary_flow_orchestration_parameters(tmp_orchestration_parameters):
    starting_flow_orchestration_parameters = ORCHESTRATION_DEPENDENCIES[
        "flow_orchestration_parameters"
    ]
    try:
        ORCHESTRATION_DEPENDENCIES[
            "flow_orchestration_parameters"
        ] = tmp_orchestration_parameters
        yield
    finally:
        ORCHESTRATION_DEPENDENCIES[
            "flow_orchestration_parameters"
        ] = starting_flow_orchestration_parameters
