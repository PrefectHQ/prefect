# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import asyncio
import datetime
import json
from dataclasses import dataclass
from typing import Any, Optional

import pendulum
from box import Box

import prefect

from prefect.engine.state import Failed, Queued, State
from prefect_server import api, config
from prefect_server.database import hasura, models
from prefect.utilities.graphql import EnumValue, with_args
from prefect_server.utilities.logging import get_logger

logger = get_logger("api")

state_schema = prefect.serialization.state.StateSchema()


async def set_flow_run_state(flow_run_id: str, state: State) -> None:
    """
    Updates a flow run state.

    Args:
        - flow_run_id (str): the flow run id to update
        - state (State): the new state

    """

    if flow_run_id is None:
        raise ValueError(f"Invalid flow run ID.")

    flow_run = await models.FlowRun.where({"id": {"_eq": flow_run_id},}).first(
        {"id": True, "state": True, "name": True, "version": True,}
    )

    if not flow_run:
        raise ValueError(f"Invalid flow run ID: {flow_run_id}.")

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
