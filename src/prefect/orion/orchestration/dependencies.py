"""
Injected orchestration dependencies
"""

ORCHESTRATION_DEPENDENCIES = {
    "task_policy": lambda: None
}


async def get_task_policy():
    provided_policy = ORCHESTRATION_DEPENDENCIES["task_policy"]()

    if provided_policy is None:
        from prefect.orion.orchestration.core_policy import CoreTaskPolicy
        provided_policy = CoreTaskPolicy
    return provided_policy
