# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license

"""
Flow Concurrency Tags, or Execution Environment Tags are
a means of limiting the number of concurrent flow runs. Each
flow can be tagged with execution environment labels, and thus
limit the concurrent number of flows that can execute in a given
environment at once. The main use of limiting concurrent flow
runs is to not overwhelm user infrastructure with a ton of
flow runs all at once.
"""

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


async def create_flow_concurrency_limit(
    name: str, slots: int, description: Optional[str] = None
) -> str:
    """
    Creates a new flow concurrency limit based on
    an execution environment's label.

    Args:
        - name (str): Name of the execution environment's label.
        - slots (int): Number of concurrent flow runs that can occur at once.
        - description (Optional[str]): Description of the flow concurrency limit
            intended for end-user clarificiation.

    Returns:
        - str: Id of the new flow concurrency limit

    Raises:
        - ValueError: If too few slots are requested.
        - ValueError: If a flow concurrency limit with the same name already exists.
    """

    if slots <= 0:
        raise ValueError(
            f"Invalid slot specification for new flow concurrency limit {name}.\
                Expected > 0 for being able to limit runs properly."
        )

    flow_concurrency_limit_id = await models.FlowConcurrencyLimit(
        name=name, slots=slots, description=description
    ).insert()

    return flow_concurrency_limit_id


async def delete_flow_concurrency_limit(flow_concurrency_limit_id: str) -> bool:
    """
    Deletes the flow concurrency limit with the given ID. If
    no flow concurrency limit is found with the given ID, False is returned.

    Args:
        - flow_concurrency_limit_id (str): ID of the flow_concurrency_limit object.

    Returns:
        - bool: Whether the delete was succcessful.
    """

    result = await models.FlowConcurrencyLimit.where(
        id=flow_concurrency_limit_id
    ).delete()
    return bool(result.affected_rows)


async def get_available_flow_concurrency(execution_env_label: str) -> int:
    """
    Determines the number of open flow concurrency slots are available
    given a certain Execution Environment label.

    A `Flow` is allocated a slot of concurrency when it exists in
    the `Running` state for the Execution Environment, and will
    continue to occupy that slot until it transitions out of
    the `Running` state.

    Args:
        - execution_env_label (Optional[str]): Name of the 

    Raises:
        - ValueError: If a flow concurrency limit can't be found with the
            provided `execution_env_label`.

    Returns:
        - int: Number of available concurrency slots for the label
    """

    where_clause = {"name": {"_eq": execution_env_label}}

    concurrency_limit = await models.FlowConcurrencyLimit.where(
        where=where_clause
    ).first({"id", "name", "slots"})
    if concurrency_limit is None:
        raise ValueError(
            f"Unable to find execution environment with label: {execution_env_label}"
        )

    # Only count the resource as taken if the flow run is currently
    # in a running state and also is tagged with the resource.
    utilized_resources = await models.FlowRun.where(
        where={
            "flow": {
                "settings": {
                    "_contains": {"concurrency_limits": [concurrency_limit.name]}
                }
            },
            "state": {"_in": RUNNING_STATES},
        }
    ).count()

    available_resources = concurrency_limit.slots - utilized_resources
    if available_resources > 0:
        return available_resources
    else:
        return 0
