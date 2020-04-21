# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license

import asyncio
import uuid
from typing import Optional

import pendulum
import prefect
from prefect.engine.state import Finished, Running
from prefect.utilities.graphql import with_args

from prefect_server.database import models

RUNNING_STATES = [
    state.__name__
    for state in prefect.engine.state.__dict__.values()
    if isinstance(state, type) and issubclass(state, (Running))
]


async def create_resource_pool(
    name: str, slots: int, description: Optional[str] = None
) -> str:
    """
    Creates a new resource pool.

    Args:
        - name (str): Name of the new resource pool
        - slots (int): Number of arbitrary resources that exist
            in the pool.
        - description (Optional[str]): Description of the resource
            pool intended for end-user clarificiation.

    Returns:
        - str: Id of the new resource pool

    Raises:
        - ValueError: If too few slots are requested.
        - ValueError: If a pool with the same name already exists.
    """

    if slots <= 0:
        raise ValueError(
            f"Invalid slot specification for new resource pool {name}.\
                Expected > 0 for being able to limit resources properly."
        )

    resource_pool_id = await models.ResourcePool(
        name=name, slots=slots, description=description
    ).insert()

    return resource_pool_id


async def delete_resource_pool(resource_pool_id: str) -> bool:
    """
    Deletes the resource pool associated with the given ID. If
    no pool is found with the given ID, False is returned.

    TODO: Decide on how to handle edge cases around deltes. We can
        either decide to delete resources that exist and _not_ check
        current Flows and Tasks, so that they'd no longer be limited
        by this resource, but that would result in the Flows and Tasks
        being tagged with resources that no longer exist. Or, we could
        scan through basically every flow, task, flow run, and task run
        that exists to check for the resource before allowing deletes, which
        sounds awfully inefficient.

    Args:
        - resource_pool_id (str): ID of the resource pool

    Returns:
        - bool: Whether the delete was succcessful.
    """

    result = await models.ResourcePool.where(id=resource_pool_id).delete()
    return bool(result.affected_rows)


async def get_available_resources(
    resource_pool_id: Optional[str] = None, pool_name: Optional[str] = None
) -> int:
    """
    Determines whether a Resource is available or not and returns
    the number of available resources.

    Both a `Flow` and a `Task` can take up a Resource, so we
    count the number of non-completed `FlowRuns` and `TaskRuns`.
    However, due to needing to decide how to integrate a `Resource` allocation
    limit with those of `Task.tags`, this won't be checking
    `TaskRuns` for resource limits.

    Args:
        - resource_pool_id (Optional[str]): ID of the resource pool
        - pool_name (Optional[str]): Name of the resource pool

    Raises:
        - TypeError: If neither `resource_pool_id` or `pool_name` are
            specified.
        - ValueError: If a resource pool can't be found with the
            provided `resource_pool_id` or `pool_name`.

    Returns:
        - int: Number of available resources in the pool
    """
    if resource_pool_id is None and pool_name is None:
        raise TypeError(
            "Must specify either resource_pool_id or pool_name. Got None for both."
        )

    if resource_pool_id is not None:
        where_clause = {"id": {"_eq": resource_pool_id}}
        error_message = f"Unable to find resource pool with id: {resource_pool_id}"
    else:
        where_clause = {"name": {"_eq": pool_name}}
        error_message = f"Unable to find resource pool with name: {pool_name}"

    pool = await models.ResourcePool.where(where=where_clause).first(
        {"id", "name", "slots"}
    )
    if pool is None:
        raise ValueError(error_message)

    # Only count the resource as taken if the flow run is currently
    # in a running state and also is tagged with the resource.
    utilized_resources = await models.FlowRun.where(
        where={
            "flow": {"settings": {"_contains": {"resources": [pool.name]}}},
            "state": {"_in": RUNNING_STATES},
        }
    ).count()

    available_resources = pool.slots - utilized_resources
    if available_resources > 0:
        return available_resources
    else:
        return 0
