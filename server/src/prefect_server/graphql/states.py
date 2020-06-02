# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import asyncio
from typing import Any

from graphql import GraphQLResolveInfo

import prefect
from prefect.utilities.graphql import EnumValue
from prefect_server import api, config
from prefect_server.database import models
from prefect_server.utilities.graphql import mutation
from prefect_server.utilities import context, exceptions

state_schema = prefect.serialization.state.StateSchema()


@mutation.field("set_flow_run_states")
async def resolve_set_flow_run_states(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    """
    Sets the flow run state, first deserializing a State from the provided input.
    """

    async def set_state(state_input: dict) -> str:
        state = state_schema.load(state_input["state"])

        await api.states.set_flow_run_state(
            flow_run_id=state_input["flow_run_id"], state=state,
        )

        return {
            "id": state_input["flow_run_id"],
            "status": "SUCCESS",
            "message": None,
        }

    result = await asyncio.gather(
        *[set_state(state_input) for state_input in input["states"]],
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

        state = state_schema.load(state_input["state"])

        await api.states.set_task_run_state(
            task_run_id=state_input["task_run_id"], state=state,
        )

        return {
            "id": state_input["task_run_id"],
            "status": "SUCCESS",
            "message": None,
        }

    result = await asyncio.gather(
        *[set_state(state_input) for state_input in input["states"]],
    )

    return {"states": result}
