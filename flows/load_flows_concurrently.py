import asyncio

from prefect import Flow
from prefect.runner.storage import GitRepository


async def load_flow(entrypoint: str) -> Flow[..., object]:
    return await Flow.from_source(  # type: ignore
        source=GitRepository(
            url="https://github.com/PrefectHQ/examples.git",
        ),
        entrypoint=entrypoint,
    )


async def test_iteration():
    entrypoints = [
        "flows/hello-world.py:hello",
        "flows/whoami.py:whoami",
    ] * 5  # Load each flow 5 times concurrently
    futures = [load_flow(entrypoint) for entrypoint in entrypoints]
    flows = await asyncio.gather(*futures)
    return len(flows)


async def run_stress_test():
    for i in range(10):  # Run 10 iterations
        try:
            count = await test_iteration()
            print(f"Iteration {i+1}: Successfully loaded {count} flows")
        except Exception as e:
            print(f"Iteration {i+1}: Failed with error: {str(e)}")
            return False
    return True


if __name__ == "__main__":
    success = asyncio.run(run_stress_test())
    print(f"\nStress test {'passed' if success else 'failed'}")
