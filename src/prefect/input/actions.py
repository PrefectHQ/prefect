from typing import TYPE_CHECKING, Any, Optional, Set
from uuid import UUID

import orjson
import pydantic

from prefect._internal.compatibility.async_dispatch import async_dispatch
from prefect.client.orchestration import get_client
from prefect.client.utilities import client_injector
from prefect.context import FlowRunContext
from prefect.exceptions import PrefectHTTPStatusError

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient
    from prefect.client.schemas.objects import FlowRunInput

from prefect._internal.pydantic.v2_schema import is_v2_model


def ensure_flow_run_id(flow_run_id: Optional[UUID] = None) -> UUID:
    if flow_run_id:
        return flow_run_id

    context = FlowRunContext.get()
    if context is None or context.flow_run is None:
        raise RuntimeError("Must either provide a flow run ID or be within a flow run.")

    return context.flow_run.id


async def acreate_flow_run_input_from_model(
    key: str,
    model_instance: pydantic.BaseModel,
    flow_run_id: Optional[UUID] = None,
    sender: Optional[str] = None,
) -> None:
    """
    Create a new flow run input from a Pydantic model asynchronously.

    Args:
        key: the flow run input key
        model_instance: a Pydantic model instance to store
        flow_run_id: the flow run ID (defaults to current context)
        sender: optional sender identifier
    """
    if sender is None:
        context = FlowRunContext.get()
        if context is not None and context.flow_run is not None:
            sender = f"prefect.flow-run.{context.flow_run.id}"

    if is_v2_model(model_instance):
        json_safe = orjson.loads(model_instance.model_dump_json())
    else:
        json_safe = orjson.loads(model_instance.json())

    await acreate_flow_run_input(
        key=key, value=json_safe, flow_run_id=flow_run_id, sender=sender
    )


@async_dispatch(acreate_flow_run_input_from_model)
def create_flow_run_input_from_model(
    key: str,
    model_instance: pydantic.BaseModel,
    flow_run_id: Optional[UUID] = None,
    sender: Optional[str] = None,
) -> None:
    """
    Create a new flow run input from a Pydantic model.

    Args:
        key: the flow run input key
        model_instance: a Pydantic model instance to store
        flow_run_id: the flow run ID (defaults to current context)
        sender: optional sender identifier
    """
    if sender is None:
        context = FlowRunContext.get()
        if context is not None and context.flow_run is not None:
            sender = f"prefect.flow-run.{context.flow_run.id}"

    if is_v2_model(model_instance):
        json_safe = orjson.loads(model_instance.model_dump_json())
    else:
        json_safe = orjson.loads(model_instance.json())

    create_flow_run_input(
        key=key, value=json_safe, flow_run_id=flow_run_id, sender=sender
    )


@client_injector
async def acreate_flow_run_input(
    client: "PrefectClient",
    key: str,
    value: Any,
    flow_run_id: Optional[UUID] = None,
    sender: Optional[str] = None,
) -> None:
    """
    Create a new flow run input asynchronously.

    The given `value` will be serialized to JSON and stored as a flow run input value.

    Args:
        key: the flow run input key
        value: the flow run input value
        flow_run_id: the flow run ID (defaults to current context)
        sender: optional sender identifier
    """
    flow_run_id = ensure_flow_run_id(flow_run_id)

    await client.create_flow_run_input(
        flow_run_id=flow_run_id,
        key=key,
        sender=sender,
        value=orjson.dumps(value).decode(),
    )


@async_dispatch(acreate_flow_run_input)
def create_flow_run_input(
    key: str,
    value: Any,
    flow_run_id: Optional[UUID] = None,
    sender: Optional[str] = None,
) -> None:
    """
    Create a new flow run input.

    The given `value` will be serialized to JSON and stored as a flow run input value.

    Args:
        key: the flow run input key
        value: the flow run input value
        flow_run_id: the flow run ID (defaults to current context)
        sender: optional sender identifier
    """
    flow_run_id = ensure_flow_run_id(flow_run_id)

    with get_client(sync_client=True) as client:
        client.create_flow_run_input(
            flow_run_id=flow_run_id,
            key=key,
            sender=sender,
            value=orjson.dumps(value).decode(),
        )


@client_injector
async def afilter_flow_run_input(
    client: "PrefectClient",
    key_prefix: str,
    limit: int = 1,
    exclude_keys: Optional[Set[str]] = None,
    flow_run_id: Optional[UUID] = None,
) -> "list[FlowRunInput]":
    """
    Filter flow run inputs by key prefix asynchronously.

    Args:
        key_prefix: prefix to filter keys by
        limit: maximum number of results to return
        exclude_keys: keys to exclude from results
        flow_run_id: the flow run ID (defaults to current context)

    Returns:
        List of matching FlowRunInput objects
    """
    if exclude_keys is None:
        exclude_keys = set()

    flow_run_id = ensure_flow_run_id(flow_run_id)

    return await client.filter_flow_run_input(
        flow_run_id=flow_run_id,
        key_prefix=key_prefix,
        limit=limit,
        exclude_keys=exclude_keys,
    )


@async_dispatch(afilter_flow_run_input)
def filter_flow_run_input(
    key_prefix: str,
    limit: int = 1,
    exclude_keys: Optional[Set[str]] = None,
    flow_run_id: Optional[UUID] = None,
) -> "list[FlowRunInput]":
    """
    Filter flow run inputs by key prefix.

    Args:
        key_prefix: prefix to filter keys by
        limit: maximum number of results to return
        exclude_keys: keys to exclude from results
        flow_run_id: the flow run ID (defaults to current context)

    Returns:
        List of matching FlowRunInput objects
    """
    if exclude_keys is None:
        exclude_keys = set()

    flow_run_id = ensure_flow_run_id(flow_run_id)

    with get_client(sync_client=True) as client:
        return client.filter_flow_run_input(
            flow_run_id=flow_run_id,
            key_prefix=key_prefix,
            limit=limit,
            exclude_keys=exclude_keys,
        )


@client_injector
async def aread_flow_run_input(
    client: "PrefectClient", key: str, flow_run_id: Optional[UUID] = None
) -> Any:
    """
    Read a flow run input asynchronously.

    Args:
        key: the flow run input key
        flow_run_id: the flow run ID (defaults to current context)

    Returns:
        The deserialized input value, or None if not found
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


@async_dispatch(aread_flow_run_input)
def read_flow_run_input(key: str, flow_run_id: Optional[UUID] = None) -> Any:
    """
    Read a flow run input.

    Args:
        key: the flow run input key
        flow_run_id: the flow run ID (defaults to current context)

    Returns:
        The deserialized input value, or None if not found
    """
    flow_run_id = ensure_flow_run_id(flow_run_id)

    with get_client(sync_client=True) as client:
        try:
            value = client.read_flow_run_input(flow_run_id=flow_run_id, key=key)
        except PrefectHTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise
        else:
            return orjson.loads(value)


@client_injector
async def adelete_flow_run_input(
    client: "PrefectClient", key: str, flow_run_id: Optional[UUID] = None
) -> None:
    """
    Delete a flow run input asynchronously.

    Args:
        key: the flow run input key
        flow_run_id: the flow run ID (defaults to current context)
    """
    flow_run_id = ensure_flow_run_id(flow_run_id)

    await client.delete_flow_run_input(flow_run_id=flow_run_id, key=key)


@async_dispatch(adelete_flow_run_input)
def delete_flow_run_input(key: str, flow_run_id: Optional[UUID] = None) -> None:
    """
    Delete a flow run input.

    Args:
        key: the flow run input key
        flow_run_id: the flow run ID (defaults to current context)
    """
    flow_run_id = ensure_flow_run_id(flow_run_id)

    with get_client(sync_client=True) as client:
        client.delete_flow_run_input(flow_run_id=flow_run_id, key=key)
