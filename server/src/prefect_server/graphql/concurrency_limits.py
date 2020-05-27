from typing import Any

from graphql import GraphQLResolveInfo

from prefect_server import api
from prefect_server.utilities.graphql import mutation


@mutation.field("update_flow_concurrency_limit")
async def resolve_update_flow_concurrency_limit(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    return {
        "id": await api.concurrency_limits.update_flow_concurrency_limit(
            name=input["name"], limit=input["limit"]
        )
    }


@mutation.field("delete_flow_concurrency_limit")
async def resolve_delete_flow_concurrency_limit(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:

    return {
        "success": await api.concurrency_limits.delete_flow_concurrency_limit(
            input["flow_concurrency_limit_id"]
        )
    }
