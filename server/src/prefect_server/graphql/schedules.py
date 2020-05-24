# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


from typing import Any, List

from graphql import GraphQLResolveInfo

from prefect_server import api
from prefect_server.database import models
from prefect_server.utilities.graphql import mutation
from prefect_server.utilities import exceptions


@mutation.field("set_schedule_active")
async def resolve_set_schedule_active(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    return {"success": await api.schedules.set_active(schedule_id=input["schedule_id"])}


@mutation.field("set_schedule_inactive")
async def resolve_set_schedule_inactive(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    return {
        "success": await api.schedules.set_inactive(schedule_id=input["schedule_id"])
    }


@mutation.field("schedule_flow_runs")
async def resolve_schedule_flow_runs(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> List[dict]:
    run_ids = await api.schedules.schedule_flow_runs(
        schedule_id=input["schedule_id"],
        max_runs=input.get("max_runs"),
        seconds_since_last_checked=60,
    )
    return [{"id": i} for i in run_ids]
