import asyncio
from uuid import UUID

from prefect import flow
from prefect.artifacts import (
    acreate_markdown_artifact,
    create_markdown_artifact,
)
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import FlowRunFilter, FlowRunFilterParentFlowRunId
from prefect.client.schemas.objects import Artifact
from prefect.context import FlowRunContext, get_run_context


@flow
def hello_artifacts():
    create_markdown_artifact("Hello, world!", key="hello-artifact-a")


@flow
async def hello_artifacts_async_using_dispatch():
    await create_markdown_artifact("Hello, world!", key="hello-artifact-b")  # type: ignore[reportGeneralTypeIssues]


@flow
async def hello_artifacts_async():
    await acreate_markdown_artifact("Hello, world!", key="hello-artifact-c")


@flow
async def hello_artifacts_forced_sync():
    create_markdown_artifact("Hello, world!", key="hello-artifact-d", _sync=True)  # type: ignore[reportCallIssue]


@flow
def parent_flow() -> UUID:
    hello_artifacts()
    asyncio.run(hello_artifacts_async_using_dispatch())
    asyncio.run(hello_artifacts_async())
    asyncio.run(hello_artifacts_forced_sync())
    ctx = get_run_context()
    assert isinstance(ctx, FlowRunContext) and ctx.flow_run is not None
    return ctx.flow_run.id


async def read_artifacts(flow_run_id: UUID) -> list[Artifact]:
    async with get_client() as client:
        artifacts = await client.read_artifacts(
            flow_run_filter=FlowRunFilter(
                parent_flow_run_id=FlowRunFilterParentFlowRunId(any_=[flow_run_id])
            )
        )
        return artifacts


if __name__ == "__main__":
    flow_run_id = parent_flow()
    artifacts = asyncio.run(read_artifacts(flow_run_id))
    assert len(artifacts) == 4, f"Expected 4 artifacts, got {len(artifacts)}"
