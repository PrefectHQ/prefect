"""
Injected orchestration dependencies
"""
from contextlib import contextmanager

ORCHESTRATION_DEPENDENCIES = {
    "task_policy_provider": None,
    "flow_policy_provider": None,
    "task_orchestration_parameters_provider": None,
    "flow_orchestration_parameters_provider": None,
}


async def provide_task_policy():
    policy_provider = ORCHESTRATION_DEPENDENCIES.get("task_policy_provider")

    if policy_provider is None:
        from prefect.orion.orchestration.core_policy import CoreTaskPolicy

        return CoreTaskPolicy

    return await policy_provider()


async def provide_flow_policy():
    policy_provider = ORCHESTRATION_DEPENDENCIES.get("flow_policy_provider")

    if policy_provider is None:
        from prefect.orion.orchestration.core_policy import CoreFlowPolicy

        return CoreFlowPolicy

    return await policy_provider()


async def provide_task_orchestration_parameters():
    parameter_provider = ORCHESTRATION_DEPENDENCIES.get(
        "task_orchestration_parameters_provider"
    )

    if parameter_provider is None:
        return dict()

    return await parameter_provider()


async def provide_flow_orchestration_parameters():
    parameter_provider = ORCHESTRATION_DEPENDENCIES.get(
        "flow_orchestration_parameters_provider"
    )

    if parameter_provider is None:
        return dict()

    return await parameter_provider()


@contextmanager
def temporary_task_policy(tmp_task_policy):
    starting_task_policy = ORCHESTRATION_DEPENDENCIES["task_policy_provider"]

    async def policy_lambda():
        return tmp_task_policy

    try:
        ORCHESTRATION_DEPENDENCIES["task_policy_provider"] = policy_lambda
        yield
    finally:
        ORCHESTRATION_DEPENDENCIES["task_policy_provider"] = starting_task_policy


@contextmanager
def temporary_flow_policy(tmp_flow_policy):
    starting_flow_policy = ORCHESTRATION_DEPENDENCIES["flow_policy_provider"]

    async def policy_lambda():
        return tmp_flow_policy

    try:
        ORCHESTRATION_DEPENDENCIES["flow_policy_provider"] = policy_lambda
        yield
    finally:
        ORCHESTRATION_DEPENDENCIES["flow_policy_provider"] = starting_flow_policy


@contextmanager
def temporary_task_orchestration_parameters(tmp_orchestration_parameters):
    starting_task_orchestration_parameters = ORCHESTRATION_DEPENDENCIES[
        "task_orchestration_parameters_provider"
    ]

    async def parameter_lambda():
        return tmp_orchestration_parameters

    try:
        ORCHESTRATION_DEPENDENCIES[
            "task_orchestration_parameters_provider"
        ] = parameter_lambda
        yield
    finally:
        ORCHESTRATION_DEPENDENCIES[
            "task_orchestration_parameters_provider"
        ] = starting_task_orchestration_parameters


@contextmanager
def temporary_flow_orchestration_parameters(tmp_orchestration_parameters):
    starting_flow_orchestration_parameters = ORCHESTRATION_DEPENDENCIES[
        "flow_orchestration_parameters_provider"
    ]

    async def parameter_lambda():
        return tmp_orchestration_parameters

    try:
        ORCHESTRATION_DEPENDENCIES[
            "flow_orchestration_parameters_provider"
        ] = parameter_lambda
        yield
    finally:
        ORCHESTRATION_DEPENDENCIES[
            "flow_orchestration_parameters_provider"
        ] = starting_flow_orchestration_parameters
