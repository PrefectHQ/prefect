# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import asyncio
import datetime
import json
from dataclasses import dataclass
from typing import Any, Optional

import pendulum
import prefect
from box import Box
from prefect.engine.state import Failed, Queued, Running, State
from prefect.utilities.graphql import EnumValue, with_args

from prefect_server import api, config
from prefect_server.database import hasura, models
from prefect_server.utilities.logging import get_logger

logger = get_logger("api")

state_schema = prefect.serialization.state.StateSchema()


async def set_flow_run_state(flow_run_id: str, state: State) -> None:
    """
    Updates a flow run state.

    If the flow's execution environment has a flow concurrency limit,
    this is the location that is ultimately responsible for ensuring
    no more than the allowed limit are `Running` at once.

    Args:
        - flow_run_id (str): the flow run id to update
        - state (State): the new state

    Raises:
        - ValueError: If the provided `flow_run_id` is `None`
        - ValueError: If the `flow_run` associated with the given
            `flow_run_id` can't be found
        - ValueError: If the flow is being transitioned to `Running`
            and there isn't an available concurrency slot if the
            flow's environment is concurrency limited.
    """

    if flow_run_id is None:
        raise ValueError(f"Invalid flow run ID.")

    flow_run = await models.FlowRun.where({"id": {"_eq": flow_run_id},}).first(
        {
            "id": True,
            "state": True,
            "name": True,
            "version": True,
            "flow": {"environment": True},
        }
    )

    if not flow_run:
        raise ValueError(f"Invalid flow run ID: {flow_run_id}.")

    # TODO: Figure out how to deal w/ feature flagging and only
    # do the concurrency check when there plugin is enabled
    if isinstance(state, Running):
        # Check whether the environment is concurrency constrained
        # or not.
        execution_env_labels = flow_run.flow.environment.get("labels")
        if execution_env_labels:
            limits = await api.concurrency_limits.get_available_flow_concurrency(
                execution_env_labels
            )

            # At least one environment doesn't have the required concurrency slot
            if not all([limits.get(label, 1) > 0 for label in execution_env_labels]):

                # More details for better logging
                unavailable_slots = [limit for limit in limits.values() if limit > 0]

                raise ValueError(
                    f"Unable to set flow run state to Running due \
                        to concurrency limit on environments: {unavailable_slots}"
                )

    # --------------------------------------------------------
    # insert the new state in the database
    # --------------------------------------------------------

    flow_run_state = models.FlowRunState(
        flow_run_id=flow_run_id,
        version=(flow_run.version or 0) + 1,
        state=type(state).__name__,
        timestamp=pendulum.now("UTC"),
        message=state.message,
        result=state.result,
        start_time=getattr(state, "start_time", None),
        serialized_state=state.serialize(),
    )

    await flow_run_state.insert()


async def set_task_run_state(task_run_id: str, state: State, force=False) -> None:
    """
    Updates a task run state.

    Args:
        - task_run_id (str): the task run id to update
        - state (State): the new state
        - false (bool): if True, avoids pipeline checks
    """

    if task_run_id is None:
        raise ValueError(f"Invalid task run ID.")

    task_run = await models.TaskRun.where({"id": {"_eq": task_run_id},}).first(
        {
            "id": True,
            "version": True,
            "state": True,
            "serialized_state": True,
            "flow_run": {"id": True, "state": True},
        }
    )

    if not task_run:
        raise ValueError(f"Invalid task run ID: {task_run_id}.")

    # ------------------------------------------------------
    # if the state is running, ensure the flow run is also running
    # ------------------------------------------------------
    if not force and state.is_running() and task_run.flow_run.state != "Running":
        raise ValueError(
            f"State update failed for task run ID {task_run_id}: provided "
            f"a running state but associated flow run {task_run.flow_run.id} is not "
            "in a running state."
        )

    # ------------------------------------------------------
    # if we have cached inputs on the old state, we need to carry them forward
    # ------------------------------------------------------
    if not state.cached_inputs and task_run.serialized_state.get("cached_inputs", None):
        # load up the old state's cached inputs and apply them to the new state
        serialized_state = state_schema.load(task_run.serialized_state)
        state.cached_inputs = serialized_state.cached_inputs

    # --------------------------------------------------------
    # prepare the new state for the database
    # --------------------------------------------------------

    task_run_state = models.TaskRunState(
        task_run_id=task_run.id,
        version=(task_run.version or 0) + 1,
        timestamp=pendulum.now("UTC"),
        message=state.message,
        result=state.result,
        start_time=getattr(state, "start_time", None),
        state=type(state).__name__,
        serialized_state=state.serialize(),
    )

    await task_run_state.insert()
