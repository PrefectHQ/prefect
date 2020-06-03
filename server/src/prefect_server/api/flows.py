# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import asyncio
import copy
import uuid

import prefect
from prefect.engine.state import Finished
from prefect.utilities.graphql import EnumValue, with_args
from prefect.utilities.serialization import to_qualified_name
from prefect_server import api, config
from prefect_server.database import hasura, models
from prefect_server.utilities import context


async def _update_flow_setting(flow_id: str, key: str, value: any) -> bool:
    """
    Updates a single setting for a flow

    Args:
        - flow_id (str): the flow id
        - key (str): the flow setting key
        - value (str): the desired value for the given key

    Returns:
        - bool: if the update succeeded

    Raises:
        - ValueError: if flow ID is not provided or invalid
    """
    if flow_id is None:
        raise ValueError("Invalid flow ID")

    # retrieve current settings so that we only update provided keys
    flow = await models.Flow.where(id=flow_id).first({"settings"})

    # if we don't have permission to view the flow, we shouldn't be able to update it
    if not flow:
        raise ValueError("Invalid flow ID")

    flow.settings[key] = value  # type: ignore

    # update with new settings
    result = await models.Flow.where(id=flow_id).update(
        set={"settings": flow.settings}
    )  # type: ignore

    return bool(result.affected_rows)  # type:ignore


async def create_flow(
    serialized_flow: dict,
    version_group_id: str = None,
    set_schedule_active: bool = True,
    description: str = None,
) -> str:
    """
    Add a flow to the database.

    Args:
        - serialized_flow (dict): A dictionary of information used to represent a flow
        - version_group_id (str): A version group to add the Flow to
        - set_schedule_active (bool): Whether to set the flow's schedule to active
        - description (str): a description of the flow being created

    Returns:
        str: The id of the new flow

    Raises:
        - ValueError: if the flow's version of Prefect Core falls below the cutoff

    """

    # validate that the flow can be deserialized
    try:
        # pass a copy because the load mutates the payload
        f = prefect.serialization.flow.FlowSchema().load(copy.deepcopy(serialized_flow))
    except Exception as exc:
        raise ValueError(f"Invalid flow: {exc}")
    required_parameters = [p for p in f.parameters() if p.required]
    if f.schedule is not None and required_parameters:
        required_names = {p.name for p in required_parameters}
        if not all(
            [
                required_names <= set(c.parameter_defaults.keys())
                for c in f.schedule.clocks
            ]
        ):
            raise ValueError("Can not schedule a flow that has required parameters.")

    # set up task detail info
    reference_tasks = f.reference_tasks()
    root_tasks = f.root_tasks()
    terminal_tasks = f.terminal_tasks()
    task_info = {
        t["slug"]: {"type": t["type"], "trigger": t["trigger"]}
        for t in serialized_flow["tasks"]
    }
    for t in f.tasks:
        task_info[t.slug].update(
            mapped=any(e.mapped for e in f.edges_to(t)),
            is_reference_task=(t in reference_tasks),
            is_root_task=(t in root_tasks),
            is_terminal_task=(t in terminal_tasks),
        )

    # set up versioning
    version_group_id = version_group_id or str(uuid.uuid4())
    version_where = {"version_group_id": {"_eq": version_group_id}}

    version = (await models.Flow.where(version_where).max({"version"}))["version"] or 0

    # precompute task ids to make edges easy to add to database
    task_ids = {t.slug: str(uuid.uuid4()) for t in f.tasks}
    flow_id = await models.Flow(
        name=f.name,
        serialized_flow=serialized_flow,
        environment=serialized_flow.get("environment"),
        core_version=serialized_flow.get("environment", {}).get("__version__"),
        storage=serialized_flow.get("storage"),
        parameters=serialized_flow.get("parameters"),
        version_group_id=version_group_id,
        version=version + 1,
        archived=False,
        description=description,
        settings={"heartbeat_enabled": True},
        schedules=[
            models.Schedule(
                schedule=serialized_flow.get("schedule"),
                active=set_schedule_active,
                schedule_start=f.schedule.start_date,
                schedule_end=f.schedule.end_date,
            )
        ]
        if f.schedule
        else [],
        tasks=[
            models.Task(
                id=task_ids[t.slug],
                name=t.name,
                slug=t.slug,
                type=task_info[t.slug]["type"],
                max_retries=t.max_retries,
                tags=list(t.tags),
                retry_delay=t.retry_delay,
                trigger=task_info[t.slug]["trigger"]["fn"],
                mapped=task_info[t.slug]["mapped"],
                auto_generated=getattr(t, "auto_generated", False),
                cache_key=t.cache_key,
                is_reference_task=task_info[t.slug]["is_reference_task"],
                is_root_task=task_info[t.slug]["is_root_task"],
                is_terminal_task=task_info[t.slug]["is_terminal_task"],
            )
            for t in f.tasks
        ],
        edges=[
            models.Edge(
                upstream_task_id=task_ids[e.upstream_task.slug],
                downstream_task_id=task_ids[e.downstream_task.slug],
                key=e.key,
                mapped=e.mapped,
            )
            for e in f.edges
        ],
    ).insert()

    # schedule runs
    if set_schedule_active and f.schedule:
        schedule = await models.Schedule.where({"flow_id": {"_eq": flow_id}}).first(
            {"id"}
        )
        await api.schedules.schedule_flow_runs(schedule_id=schedule.id)

    return flow_id


async def delete_flow(flow_id: str) -> bool:
    """
    Deletes a flow.

    Args:
        - flow_id (str): the flow id

    Returns:
        - bool: if the delete succeeded

    Raises:
        - ValueError: if a flow ID is not provided
    """
    if not flow_id:
        raise ValueError("Must provide flow ID.")

    # delete the flow
    result = await models.Flow.where(id=flow_id).delete()
    return bool(result.affected_rows)


async def archive_flow(flow_id: str) -> bool:
    """
    Archives a flow.

    Archiving a flow prevents it from scheduling new runs. It also:
        - deletes any currently scheduled runs
        - resets the "last scheduled run time" of any schedules

    Args:
        - flow_id (str): the flow id

    Returns:
        - bool: if the update succeeded

    Raises:
        - ValueError: if a flow ID is not provided
    """
    if not flow_id:
        raise ValueError("Must provide flow ID.")

    result = await models.Flow.where({"id": {"_eq": flow_id}}).update(
        set={"archived": True}
    )
    if not result.affected_rows:
        return False

    # delete scheduled flow runs
    await models.FlowRun.where(
        {"flow_id": {"_eq": flow_id}, "state": {"_eq": "Scheduled"}}
    ).delete()

    # reset last scheduled run time
    await models.Schedule.where({"flow_id": {"_eq": flow_id}}).update(
        set={"last_scheduled_run_time": None}
    )

    return True


async def unarchive_flow(flow_id: str) -> bool:
    """
    Unarchives a flow.

    Args:
        - flow_id (str): the flow id

    Returns:
        - bool: if the update succeeded

    Raises:
        - ValueError: if a flow ID is not provided
    """
    if not flow_id:
        raise ValueError("Must provide flow ID.")

    result = await models.Flow.where({"id": {"_eq": flow_id}}).update(
        set={"archived": False}
    )
    return bool(result.affected_rows)  # type: ignore


async def enable_heartbeat_for_flow(flow_id: str) -> bool:
    """
    Enables heartbeats for a flow

    Args:
        - flow_id (str): the flow id

    Returns:
        - bool: if the update succeeded

    Raises:
        - ValueError: if flow ID is not provided or invalid
    """
    await _update_flow_setting(flow_id=flow_id, key="disable_heartbeat", value=False)

    return await _update_flow_setting(
        flow_id=flow_id, key="heartbeat_enabled", value=True
    )


async def disable_heartbeat_for_flow(flow_id: str) -> bool:
    """
    Disables heartbeats for a flow

    Args:
        - flow_id (str): the flow id

    Returns:
        - bool: if the update succeeded

    Raises:
        - ValueError: if flow ID is not provided or invalid
    """
    await _update_flow_setting(flow_id=flow_id, key="disable_heartbeat", value=True)

    return await _update_flow_setting(
        flow_id=flow_id, key="heartbeat_enabled", value=False
    )
