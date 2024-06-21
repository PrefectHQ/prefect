from typing import TYPE_CHECKING, Any, Optional, Set
from uuid import UUID

import orjson
import pydantic

from prefect.client.utilities import client_injector
from prefect.context import FlowRunContext
from prefect.exceptions import PrefectHTTPStatusError
from prefect.utilities.asyncutils import sync_compatible

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient


from prefect._internal.pydantic.v2_schema import is_v2_model


def ensure_flow_run_id(flow_run_id: Optional[UUID] = None) -> UUID:
    if flow_run_id:
        return flow_run_id

    context = FlowRunContext.get()
    if context is None or context.flow_run is None:
        raise RuntimeError("Must either provide a flow run ID or be within a flow run.")

    return context.flow_run.id


@sync_compatible
async def create_flow_run_input_from_model(
    key: str,
    model_instance: pydantic.BaseModel,
    flow_run_id: Optional[UUID] = None,
    sender: Optional[str] = None,
):
    if sender is None:
        context = FlowRunContext.get()
        if context is not None and context.flow_run is not None:
            sender = f"prefect.flow-run.{context.flow_run.id}"

    if is_v2_model(model_instance):
        json_safe = orjson.loads(model_instance.model_dump_json())
    else:
        json_safe = orjson.loads(model_instance.json())

    await create_flow_run_input(
        key=key, value=json_safe, flow_run_id=flow_run_id, sender=sender
    )


@sync_compatible
@client_injector
async def create_flow_run_input(
    client: "PrefectClient",
    key: str,
    value: Any,
    flow_run_id: Optional[UUID] = None,
    sender: Optional[str] = None,
):
    """
    Create a new flow run input. The given `value` will be serialized to JSON
    and stored as a flow run input value.

    Args:
        - key (str): the flow run input key
        - value (Any): the flow run input value
        - flow_run_id (UUID): the, optional, flow run ID. If not given will
          default to pulling the flow run ID from the current context.
    """
    flow_run_id = ensure_flow_run_id(flow_run_id)

    await client.create_flow_run_input(
        flow_run_id=flow_run_id,
        key=key,
        sender=sender,
        value=orjson.dumps(value).decode(),
    )


@sync_compatible
@client_injector
async def filter_flow_run_input(
    client: "PrefectClient",
    key_prefix: str,
    limit: int = 1,
    exclude_keys: Optional[Set[str]] = None,
    flow_run_id: Optional[UUID] = None,
):
    if exclude_keys is None:
        exclude_keys = set()

    flow_run_id = ensure_flow_run_id(flow_run_id)

    return await client.filter_flow_run_input(
        flow_run_id=flow_run_id,
        key_prefix=key_prefix,
        limit=limit,
        exclude_keys=exclude_keys,
    )


@sync_compatible
@client_injector
async def read_flow_run_input(
    client: "PrefectClient", key: str, flow_run_id: Optional[UUID] = None
) -> Any:
    """Read a flow run input.

    Args:
        - key (str): the flow run input key
        - flow_run_id (UUID): the flow run ID
    """
    flow_run_id = ensure_flow_run_id(flow_run_id)

    try:
        value = await client.read_flow_run_input(flow_run_id=flow_run_id, key=key)
    except PrefectHTTPStatusError as exc:
        if exc.response.status_code == 404:
            return None
        raise
    else:
        return orjson.loads(value)


@sync_compatible
@client_injector
async def delete_flow_run_input(
    client: "PrefectClient", key: str, flow_run_id: Optional[UUID] = None
):
    """Delete a flow run input.

    Args:
        - flow_run_id (UUID): the flow run ID
        - key (str): the flow run input key
    """

    flow_run_id = ensure_flow_run_id(flow_run_id)

    await client.delete_flow_run_input(flow_run_id=flow_run_id, key=key)
