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
from typing import Dict, List, Optional

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
    name: str, limit: int, description: Optional[str] = None
) -> str:
    """
    Creates a new flow concurrency limit based on
    an execution environment's label.

    Args:
        - name (str): Name of the execution environment's label.
        - limit (int): Number of concurrent flow runs that can occur at once.
        - description (Optional[str]): Description of the flow concurrency limit
            intended for end-user clarificiation.

    Returns:
        - str: Id of the new flow concurrency limit

    Raises:
        - ValueError: If too low of a limit is requested.
        - ValueError: If a flow concurrency limit with the same name already exists.
    """

    if limit <= 0:
        raise ValueError(
            f"Invalid limit specification for new flow concurrency limit {name}.\
                Expected > 0 for being able to limit runs properly."
        )

    flow_concurrency_limit_id = await models.FlowConcurrencyLimit(
        name=name, limit=limit, description=description
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


async def get_available_flow_concurrency(
    execution_env_labels: List[str],
) -> Dict[str, int]:
    """
    Determines the number of open flow concurrency slots are available
    given a certain Execution Environment label.

    A `Flow` is allocated a slot of concurrency when it exists in
    the `Running` state for the Execution Environment, and will
    continue to occupy that slot until it transitions out of
    the `Running` state.

    Args:
        - execution_env_label (List[str]): List of environment execution
            labels to get their concurrency maximums.

    Returns:
        - Dict[str, int]: Number of available concurrency slots for each
            label that's passed in. If not found, the label won't be present
            in the output dictionary.
    """

    concurrency_limits = await models.FlowConcurrencyLimit.where(
        {"name": {"_in": execution_env_labels}}
    ).get({"id", "name", "limit"})
    if not concurrency_limits:
        return {}

    limits = {limit.name: limit.limit for limit in concurrency_limits}

    # Only count the resource as taken if the flow run is currently
    # in a running state and also is tagged with the environment tag.

    utilized_slots = {
        limit.name: await models.FlowRun.where(
            where={
                "flow": {"environment": {"_contains": {"labels": [limit.name]}}},
                "state": {"_in": RUNNING_STATES},
            }
        ).count()
        for limit in concurrency_limits
    }

    result = {label: limits[label] - used for label, used in utilized_slots.items()}

    return result
