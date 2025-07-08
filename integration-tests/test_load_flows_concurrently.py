import asyncio
from typing import Any

from prefect import Flow
from prefect.runner.storage import GitRepository


async def load_flow(entrypoint: str) -> Flow[..., Any]:
    return await Flow.from_source(  # type: ignore # sync_compatible causes issues
        source=GitRepository(
            url="https://github.com/PrefectHQ/examples.git",
        ),
        entrypoint=entrypoint,
    )


async def test_iteration():
    entrypoints = [
        "flows/hello_world.py:hello",
        "flows/whoami.py:whoami",
    ] * 5  # Load each flow 5 times concurrently
    futures = [load_flow(entrypoint) for entrypoint in entrypoints]
    flows = await asyncio.gather(*futures)
    return len(flows)


async def test_load_flows_concurrently():
    for i in range(10):  # Run 10 iterations
        try:
            count = await test_iteration()
            print(f"Iteration {i + 1}: Successfully loaded {count} flows")
        except Exception as e:
            print(f"Iteration {i + 1}: Failed with error: {str(e)}")
            return False
    return True
