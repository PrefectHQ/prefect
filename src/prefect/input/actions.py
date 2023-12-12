from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

import orjson

from prefect.client.utilities import inject_client
from prefect.context import FlowRunContext
from prefect.exceptions import PrefectHTTPStatusError
from prefect.utilities.asyncutils import sync_compatible

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient


def _ensure_flow_run_id(flow_run_id: Optional[UUID] = None) -> UUID:
    if flow_run_id:
        return flow_run_id

    context = FlowRunContext.get()
    if context is None or context.flow_run is None:
        raise RuntimeError("Must either provide a flow run ID or be within a flow run.")

    return context.flow_run.id


@sync_compatible
@inject_client
async def create_flow_run_input(
    key: str,
    value: Any,
    flow_run_id: Optional[UUID] = None,
    client: "PrefectClient" = None,
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
    flow_run_id = _ensure_flow_run_id(flow_run_id)

    await client.create_flow_run_input(
        flow_run_id=flow_run_id, key=key, value=orjson.dumps(value).decode()
    )


@sync_compatible
@inject_client
async def read_flow_run_input(
    key: str, flow_run_id: Optional[UUID] = None, client: "PrefectClient" = None
) -> Any:
    """Read a flow run input.

    Args:
        - key (str): the flow run input key
        - flow_run_id (UUID): the flow run ID
    """
    flow_run_id = _ensure_flow_run_id(flow_run_id)

    try:
        value = await client.read_flow_run_input(flow_run_id=flow_run_id, key=key)
    except PrefectHTTPStatusError as exc:
        if exc.response.status_code == 404:
            return None
        raise
    else:
        return orjson.loads(value)


@sync_compatible
@inject_client
async def delete_flow_run_input(
    key: str, flow_run_id: Optional[UUID] = None, client: "PrefectClient" = None
):
    """Delete a flow run input.

    Args:
        - flow_run_id (UUID): the flow run ID
        - key (str): the flow run input key
    """

    flow_run_id = _ensure_flow_run_id(flow_run_id)

    await client.delete_flow_run_input(flow_run_id=flow_run_id, key=key)
