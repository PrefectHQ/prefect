# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license

import asyncio
import uuid
from typing import Optional

import pendulum
import prefect
from prefect.utilities.graphql import with_args

from prefect_server.database import models


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
