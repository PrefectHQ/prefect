# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import asyncio
from typing import Any

import prefect
from graphql import GraphQLResolveInfo
from prefect.utilities.graphql import EnumValue

from prefect_server import api, config
from prefect_server.database import models
from prefect_server.utilities import context, exceptions
from prefect_server.utilities.graphql import mutation

state_schema = prefect.serialization.state.StateSchema()


@mutation.field("set_flow_run_states")
async def resolve_set_flow_run_states(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    """
    Sets the flow run state, first deserializing a State from the provided input.
    """

    async def set_state(state_input: dict) -> str:
        try:
            state = state_schema.load(state_input["state"])

            result = await api.states.set_flow_run_state(
                flow_run_id=state_input["flow_run_id"], state=state,
            )
            result.update({"id": state_input["flow_run_id"], "message": None})
            return result

        except Exception as exc:
            return {
                # placing the error inside the payload will get GraphQL to return the data
                # AND raise an error, but this is fragile because it requires users to request
                # the ID field
                "id": exc,
                "status": "ERROR",
                "message": str(exc),
            }

    result = await asyncio.gather(
        *[set_state(state_input) for state_input in input["states"]],
        return_exceptions=True,
    )

    return {"states": result}


@mutation.field("set_task_run_states")
async def resolve_set_task_run_states(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    """
    Sets the task run state, first deserializing a State from the provided input.
    """

    async def set_state(state_input: dict) -> str:

        try:
            state = state_schema.load(state_input["state"])

            result = await api.states.set_task_run_state(
                task_run_id=state_input["task_run_id"], state=state,
            )
            result.update({"id": state_input["task_run_id"], "message": None})
            return result

        except Exception as exc:
            return {
                # placing the error inside the payload will get GraphQL to return the data
                # AND raise an error, but this is fragile because it requires users to request
                # the ID field
                "id": exc,
                "status": "ERROR",
                "message": str(exc),
            }

    result = await asyncio.gather(
        *[set_state(state_input) for state_input in input["states"]],
        return_exceptions=True,
    )

    return {"states": result}
