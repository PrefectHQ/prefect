"""
Injected orchestration dependencies
"""

ORCHESTRATION_DEPENDENCIES = {
    "task_policy": lambda: None,
    "flow_policy": lambda: None,
}


async def get_task_policy():
    provided_policy = ORCHESTRATION_DEPENDENCIES.get("task_policy", None)()

    if provided_policy is None:
        from prefect.orion.orchestration.core_policy import CoreTaskPolicy
        provided_policy = CoreTaskPolicy
    return provided_policy


async def get_flow_policy():
    provided_policy = ORCHESTRATION_DEPENDENCIES.get("flow_policy", None)()

    if provided_policy is None:
        from prefect.orion.orchestration.core_policy import CoreFlowPolicy
        provided_policy = CoreFlowPolicy
    return provided_policy
