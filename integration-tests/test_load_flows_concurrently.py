import asyncio
import tempfile
from pathlib import Path
from typing import Any

from prefect import Flow
from prefect.runner.storage import GitRepository


async def load_flow(entrypoint: str, base_dir: Path) -> Flow[..., Any]:
    source = GitRepository(
        url="https://github.com/PrefectHQ/examples.git",
    )
    source.set_base_path(base_dir)
    return await Flow.from_source(  # type: ignore # sync_compatible causes issues
        source=source,
        entrypoint=entrypoint,
    )


async def run_iteration():
    with tempfile.TemporaryDirectory() as tmpdir:
        entrypoints = [
            "flows/hello_world.py:hello",
            "flows/whoami.py:whoami",
        ] * 5  # Load each flow 5 times concurrently
        futures = [load_flow(entrypoint, Path(tmpdir)) for entrypoint in entrypoints]
        flows = await asyncio.gather(*futures)
        return len(flows)


async def test_load_flows_concurrently():
    for i in range(10):  # Run 10 iterations
        try:
            count = await run_iteration()
            print(f"Iteration {i + 1}: Successfully loaded {count} flows")
        except Exception as e:
            print(f"Iteration {i + 1}: Failed with error: {str(e)}")
            return False
    return True
