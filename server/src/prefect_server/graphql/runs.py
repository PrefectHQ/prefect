# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import asyncio
import json
from typing import Any

from graphql import GraphQLResolveInfo

import prefect
from prefect.utilities.graphql import EnumValue
from prefect_server import api, config
from prefect_server.database import models
from prefect_server.utilities.graphql import mutation
from prefect_server.utilities import context, exceptions

state_schema = prefect.serialization.state.StateSchema()


@mutation.field("create_flow_run")
async def resolve_create_flow_run(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    """
    Input Args:
        - flowId: the flow id
        - parameters: the run parameters
        - context: the run context
        - scheduledStartTime: the scheduled start time; defaults to now
        - flowRunName: the flow run name
        - versionGroupId: the version group ID of the flow to run; if provided, will run the only
            unarchived version of the provided ID
    """

    flow_identifier = input.get("flow_id") or input.get("version_group_id")
    if not flow_identifier:
        raise ValueError("A flow id or version group ID must be provided.")

    # compute actual result
    result = {
        "id": await api.runs.create_flow_run(
            flow_id=input.get("flow_id"),
            parameters=input.get("parameters"),
            context=input.get("context"),
            scheduled_start_time=input.get("scheduled_start_time"),
            flow_run_name=input.get("flow_run_name"),
            version_group_id=input.get("version_group_id"),
        )
    }

    # return the result
    return result


@mutation.field("get_or_create_task_run")
async def resolve_get_or_create_task_run(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    return {
        "id": await api.runs.get_or_create_task_run(
            flow_run_id=input["flow_run_id"],
            task_id=input["task_id"],
            map_index=input.get("map_index"),
        )
    }


@mutation.field("delete_flow_run")
async def resolve_delete_flow_run(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    result = await models.FlowRun.where(id=input["flow_run_id"]).delete()
    return {"success": bool(result.affected_rows)}


@mutation.field("update_flow_run_heartbeat")
async def resolve_update_flow_run_heartbeat(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    # TODO: defer db writes
    asyncio.create_task(
        api.runs.update_flow_run_heartbeat(flow_run_id=input["flow_run_id"])
    )
    return {"success": True}


@mutation.field("update_task_run_heartbeat")
async def resolve_update_task_run_heartbeat(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    # TODO: defer db writes
    asyncio.create_task(
        api.runs.update_task_run_heartbeat(task_run_id=input["task_run_id"])
    )
    return {"success": True}


@mutation.field("get_runs_in_queue")
async def resolve_get_runs_in_queue(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    labels = input.get("labels", [])
    labels.sort()
    result = await api.runs.get_runs_in_queue(before=input.get("before"), labels=labels)
    return {"flow_run_ids": result}
