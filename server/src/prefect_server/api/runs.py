# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import datetime
from typing import Any, Dict, Iterable, List, Optional

import pendulum
import prefect
import ujson
from prefect.engine.state import Pending, Queued, Scheduled
from prefect.serialization.task import ParameterSchema
from prefect.utilities.graphql import EnumValue, parse_graphql_arguments, with_args

import prefect_server
from prefect_server import api, config
from prefect_server.database import hasura, models
from prefect_server.utilities import exceptions, names

SCHEDULED_STATES = [
    s.__name__
    for s in prefect.engine.state.__dict__.values()
    if isinstance(s, type) and issubclass(s, (Scheduled, Queued))
]


async def create_flow_run(
    flow_id: str = None,
    parameters: dict = None,
    context: dict = None,
    scheduled_start_time: datetime.datetime = None,
    flow_run_name: str = None,
    version_group_id: str = None,
) -> Any:
    """

    Creates a new flow run for an existing flow.

    Args:
        - flow_id (str): A string representing the current flow id
        - parameters (dict, optional): A dictionary of parameters that were specified for the flow
        - context (dict, optional): A dictionary of context values
        - scheduled_start_time (datetime.datetime): When the flow_run should be scheduled to run. If `None`,
            defaults to right now. Must be UTC.
        - flow_run_name (str, optional): An optional string representing this flow run
        - version_group_id (str, optional): An optional version group ID; if provided, will run the most
            recent unarchived version of the group
    """
    scheduled_start_time = scheduled_start_time or pendulum.now()

    if flow_id:
        where_clause = {"id": {"_eq": flow_id}}
    elif version_group_id:
        where_clause = {
            "version_group_id": {"_eq": version_group_id},
            "archived": {"_eq": False},
        }
    else:
        raise ValueError("One of flow_id or version_group_id must be provided.")

    flow = await models.Flow.where(where=where_clause).first(
        {"id": True, "archived": True, "parameters": True},
        order_by={"version": EnumValue("desc")},
    )  # type: Any

    if not flow:
        msg = (
            f"Flow {flow_id} not found"
            if flow_id
            else f"Version group {version_group_id} has no unarchived flows."
        )
        raise exceptions.NotFound(msg)
    elif flow.archived:
        raise ValueError(f"Flow {flow.id} is archived.")

    # check parameters
    parameters = parameters or {}
    required_parameters = [p["name"] for p in flow.parameters if p["required"]]
    missing = set(required_parameters).difference(parameters)
    if missing:
        raise ValueError(f"Required parameters were not supplied: {missing}")
    extra = set(parameters).difference([p["name"] for p in flow.parameters])
    if extra:
        raise ValueError(f"Extra parameters were supplied: {extra}")

    state = Scheduled(message="Flow run scheduled.", start_time=scheduled_start_time)

    run = models.FlowRun(
        flow_id=flow_id or flow.id,
        parameters=parameters,
        context=context or {},
        scheduled_start_time=scheduled_start_time,
        name=flow_run_name or names.generate_slug(2),
        states=[
            models.FlowRunState(
                **models.FlowRunState.fields_from_state(
                    Pending(message="Flow run created")
                )
            )
        ],
    )

    flow_run_id = await run.insert()

    # apply the flow run's initial state via `set_flow_run_state`
    await api.states.set_flow_run_state(flow_run_id=flow_run_id, state=state)

    return flow_run_id


async def get_or_create_task_run(
    flow_run_id: str, task_id: str, map_index: int = None
) -> str:
    """
    Since some task runs are created dynamically (when tasks are mapped, for example)
    we don't know if a task run exists the first time we query it. This function will take
    key information about a task run and create it if it doesn't already exist, returning its id.
    """

    if map_index is None:
        map_index = -1

    # try to load an existing task run
    task_run = await models.TaskRun.where(
        {
            "flow_run_id": {"_eq": flow_run_id},
            "task_id": {"_eq": task_id},
            "map_index": {"_eq": map_index},
        }
    ).first({"id"})

    if task_run:
        return task_run.id

    try:
        # load the cache_key
        task = await models.Task.where(id=task_id).first({"cache_key"})
        # create the task run
        return await models.TaskRun(
            flow_run_id=flow_run_id,
            task_id=task_id,
            map_index=map_index,
            cache_key=task.cache_key,
            states=[
                models.TaskRunState(
                    **models.TaskRunState.fields_from_state(
                        Pending(message="Task run created")
                    )
                )
            ],
        ).insert()

    except Exception:
        raise ValueError("Invalid ID")


async def update_flow_run_heartbeat(flow_run_id: str) -> None:
    """
    Updates the heartbeat of a flow run.

    Args:
        - flow_run_id (str): the flow run id

    Raises:
        - ValueError: if the flow_run_id is invalid
    """

    result = await models.FlowRun.where(id=flow_run_id).update(
        set={"heartbeat": pendulum.now("utc")}
    )
    if not result.affected_rows:
        raise ValueError("Invalid flow run ID")


async def update_task_run_heartbeat(task_run_id: str) -> None:
    """
    Updates the heartbeat of a task run. Also sets the corresponding flow run heartbeat.

    Args:
        - task_run_id (str): the task run id

    Raises:
        - ValueError: if the task_run_id is invalid
    """
    result = await models.TaskRun.where(id=task_run_id).update(
        set={"heartbeat": pendulum.now("utc")}
    )
    if not result.affected_rows:
        raise ValueError("Invalid task run ID")


async def get_runs_in_queue(
    before: datetime = None, labels: Iterable[str] = None
) -> List[str]:

    if before is None:
        before = pendulum.now("UTC")

    labels = labels or []

    flow_runs = await models.FlowRun.where(
        {
            # EITHER
            "_or": [
                # The flow run is scheduled
                {
                    "current_state": {
                        "state": {"_in": SCHEDULED_STATES},
                        "start_time": {"_lte": str(before)},
                    }
                },
                # one of the flow run's task runs is scheduled
                # and the flow run is running
                {
                    "current_state": {"state": {"_eq": "Running"}},
                    "task_runs": {
                        "current_state": {
                            "state": {"_in": SCHEDULED_STATES},
                            "start_time": {"_lte": str(before)},
                        }
                    },
                },
            ]
        }
    ).get(
        {"id": True, "flow": {"environment": True, "settings": True}},
        order_by=[{"current_state": {"start_time": EnumValue("asc")}}],
        # get extra in case labeled or resource constrained runs don't show up at the top
        limit=config.queued_runs_returned_limit * 4,
    )

    # See if any flows are resource constrained and find current available resources
    concurrency_limits = set()
    for flow_run in flow_runs:
        flow_concurrency_limits = flow_run.flow.settings.get("concurrency_limits") or []
        for flow_concurrency_limit in flow_concurrency_limits:
            concurrency_limits.add(flow_concurrency_limit)

    available_resource_utilization = {
        flow_concurrency_limit: await api.concurrency_limits.get_available_flow_concurrency(
            flow_concurrency_limit
        )
        for flow_concurrency_limit in concurrency_limits
    }

    counter = 0
    final_flow_runs = []

    # The concurrency checks occuring here are _not_ the end-all-be-all
    # for ensuring flow concurrency. The checks occur here to ensure we
    # don't have agents pulling runs that  Without these checks here,
    # a situation where _only_ flow runs that _don't_ have available
    # concurrency slots are returned is possible when there are
    # runs in the queue that _could_ be submitted for execution.

    for flow_run in flow_runs:
        if counter == config.queued_runs_returned_limit:
            continue

        run_labels = flow_run.flow.environment.get("labels") or []

        # if the run labels are a superset of the provided labels, skip
        if set(run_labels) - set(labels):
            continue

        # if the run has no labels but labels were provided, skip
        if not run_labels and labels:
            continue

        # Required concurrency slots of this flow run
        flow_concurrency_limits = flow_run.flow.settings.get("concurrency_limits") or []
        if flow_concurrency_limits:
            # if the execution environment has available concurrency for all
            # of the concurrency slots this flow run requires.
            if not all(
                [
                    available_resource_utilization[concurrency_limit] > 0
                    for concurrency_limit in flow_concurrency_limits
                ]
            ):
                # The run doesn't have the available concurrency slots, so we
                # bail early and don't count towards the number
                # in the queue.

                continue
            else:

                for concurrency_limit in flow_concurrency_limits:
                    available_resource_utilization[concurrency_limit] -= 1

        final_flow_runs.append(flow_run.id)
        counter += 1

    return final_flow_runs
