# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


from typing import Any

from graphql import GraphQLResolveInfo

from prefect.utilities.graphql import EnumValue, decompress
from prefect_server import api
from prefect_server.database import models
from prefect_server.utilities.graphql import mutation
from prefect_server.utilities import context


@mutation.field("create_flow_from_compressed_string")
async def resolve_create_flow_from_compressed_string(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    try:
        serialized_flow = decompress(input["serialized_flow"])
    except:
        raise TypeError("Unable to decompress serialized flow")
    input["serialized_flow"] = serialized_flow
    return await resolve_create_flow(obj, info, input)


@mutation.field("create_flow")
async def resolve_create_flow(obj: Any, info: GraphQLResolveInfo, input: dict) -> dict:
    serialized_flow = input["serialized_flow"]
    version_group_id = input.get("version_group_id", None)
    set_schedule_active = input.get("set_schedule_active", True)
    description = input.get("description", None)

    # if no version_group_id is supplied, see if a flow with the same name exists
    new_version_group = True
    if not version_group_id:
        flow = await models.Flow.where(
            {"name": {"_eq": serialized_flow.get("name")},}
        ).first(
            order_by={"created": EnumValue("desc")}, selection_set={"version_group_id"}
        )
        if flow:
            version_group_id = flow.version_group_id  # type:ignore
            new_version_group = False
    # otherwise look the flow up directly using the version group ID
    else:
        flow = await models.Flow.where(
            {"version_group_id": {"_eq": version_group_id}}
        ).first(selection_set={"version_group_id"})
        if flow:
            new_version_group = False

    flow_id = await api.flows.create_flow(
        serialized_flow=serialized_flow,
        version_group_id=version_group_id,
        set_schedule_active=set_schedule_active,
        description=description,
    )

    # handle carryover of settings from the previous flow version
    flow = await models.Flow.where(id=flow_id).first({"version"})
    previous_flow = await models.Flow.where(
        {
            "version_group_id": {"_eq": version_group_id},
            "version": {"_eq": flow.version - 1},
        }
    ).first({"settings"})
    if previous_flow:
        await models.Flow.where(id=flow_id).update(
            set=dict(settings=previous_flow.settings)
        )

    # archive all other versions
    if version_group_id:
        all_other_unarchived_versions = await models.Flow.where(
            {
                "version_group_id": {"_eq": version_group_id},
                "id": {"_neq": flow_id},
                "archived": {"_eq": False},
            }
        ).get(
            {"id"}
        )  # type: Any

        for version in all_other_unarchived_versions:
            await api.flows.archive_flow(version.id)  # type: ignore

    return {"id": flow_id}


@mutation.field("delete_flow")
async def resolve_delete_flow(obj: Any, info: GraphQLResolveInfo, input: dict) -> dict:
    return {"success": await api.flows.delete_flow(flow_id=input["flow_id"])}


@mutation.field("archive_flow")
async def resolve_archive_flow(obj: Any, info: GraphQLResolveInfo, input: dict) -> dict:
    return {"success": await api.flows.archive_flow(flow_id=input["flow_id"])}


@mutation.field("disable_flow_heartbeat")
async def resolve_disable_heartbeat_for_flow(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    success = await api.flows.disable_heartbeat_for_flow(flow_id=input["flow_id"])
    return {"success": success}


@mutation.field("enable_flow_heartbeat")
async def resolve_enable_heartbeat_for_flow(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    success = await api.flows.enable_heartbeat_for_flow(flow_id=input["flow_id"])
    return {"success": success}
