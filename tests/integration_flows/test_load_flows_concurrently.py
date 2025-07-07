import asyncio
from typing import Any

from prefect import Flow
from prefect.runner.storage import GitRepository


async def load_flow(entrypoint: str) -> Flow[..., Any]:
    return await Flow.from_source(
        source=GitRepository(url="https://github.com/PrefectHQ/examples.git"),
        entrypoint=entrypoint,
    )


async def test_iteration():
    entrypoints = ["flows/hello-world.py:hello", "flows/whoami.py:whoami"] * 5
    futures = [load_flow(entrypoint) for entrypoint in entrypoints]
    flows = await asyncio.gather(*futures)
    return len(flows)


async def run_stress_test():
    for i in range(10):
        try:
            count = await test_iteration()
            print(f"Iteration {i + 1}: Successfully loaded {count} flows")
        except Exception as e:
            print(f"Iteration {i + 1}: Failed with error: {str(e)}")
            return False
    return True


def test_load_flows_concurrently():
    """Test for load_flows_concurrently."""
    success = asyncio.run(run_stress_test())
    print(f"\nStress test {('passed' if success else 'failed')}")
