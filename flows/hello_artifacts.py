import asyncio

from prefect import flow
from prefect.artifacts import acreate_markdown_artifact, create_markdown_artifact


@flow
def hello_artifacts():
    create_markdown_artifact("Hello, world!")


@flow
async def hello_artifacts_async_using_dispatch():
    await create_markdown_artifact("Hello, world!")  # type: ignore[reportGeneralTypeIssues]


@flow
async def hello_artifacts_async():
    await acreate_markdown_artifact("Hello, world!")


@flow
async def hello_artifacts_forced_sync():
    create_markdown_artifact("Hello, world!", _sync=True)  # type: ignore[reportCallIssue]


if __name__ == "__main__":
    hello_artifacts()
    asyncio.run(hello_artifacts_async_using_dispatch())
    asyncio.run(hello_artifacts_async())
    asyncio.run(hello_artifacts_forced_sync())
