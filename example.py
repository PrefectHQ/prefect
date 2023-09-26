import asyncio

from prefect import flow
from prefect.deployments.runner import RunnerDeployment
from prefect.mounts import GitRepositoryMount
from prefect.runner import serve


@flow(log_prints=True)
def local_flow():
    print("I'm a locally defined flow!")


async def main():
    await serve(
        local_flow.to_deployment("test-local"),
        await RunnerDeployment.from_remote(
            url="https://github.com/desertaxle/demo.git",
            entrypoint="flow.py:my_flow",
            name="test-remote",
        ),
        await RunnerDeployment.from_mount(
            mount=GitRepositoryMount(
                repository="https://github.com/desertaxle/demo.git"
            ),
            entrypoint="another.py:hello",
            name="test-remote",
            parameters={"name": "world"},
        ),
    )


if __name__ == "__main__":
    asyncio.run(main())
