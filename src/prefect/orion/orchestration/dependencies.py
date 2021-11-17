"""
Injected orchestration dependencies
"""

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
