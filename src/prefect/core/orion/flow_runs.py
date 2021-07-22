from typing import TYPE_CHECKING, Iterable, Dict, Any

from prefect.orion import schemas
from prefect.core.utilities import sync
from prefect.core.orion.client import get_client
from prefect.core.orion.flows import create_flow

if TYPE_CHECKING:
    from prefect.core.flow import Flow


if TYPE_CHECKING:
    from prefect.core.flow import Flow
    from prefect.core.orion.client import Client


async def create_flow_run(
    flow: "Flow",
    parameters: Dict[str, Any] = None,
    context: dict = None,
    extra_tags: Iterable[str] = None,
    parent_task_run_id: str = None,
    client: "Client" = None,
) -> str:
    client = client or get_client()
    tags = set(flow.tags).union(extra_tags or [])
    parameters = parameters or {}
    context = context or {}

    # Retrieve the flow id
    flow_id = await create_flow(flow, client=client)

    flow_run_data = schemas.actions.FlowRunCreate(
        flow_id=flow_id,
        flow_version=flow.version,
        parameters=parameters,
        context=context,
        tags=list(tags),
        parent_task_run_id=parent_task_run_id,
    )

    response = await client.post("/flow_runs/", json=flow_run_data.json_dict())
    flow_run_id = response.json().get("id")
    if not flow_run_id:
        raise Exception(f"Malformed response: {response}")

    return flow_run_id


async def read_flow_run(
    flow_run_id: str, client: "Client" = None
) -> schemas.api.FlowRun:
    client = client or get_client()
    response = await client.get(f"/flow_runs/{flow_run_id}")
    return schemas.api.FlowRun(**response.json())


read_flow_run_sync = sync(read_flow_run)
create_flow_run_sync = sync(create_flow_run)
