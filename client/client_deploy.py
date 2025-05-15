"""
This PR tests the code path for remote execution works for prefect-client. Because of prefect-client's reduced
dependency set, we need to guard against accidentally adding extraneous dependencies to this code path.
"""

import asyncio
import inspect
from pathlib import Path
from typing import TYPE_CHECKING

from prefect import Flow, get_client
from prefect.client.schemas.actions import WorkPoolCreate
from prefect.exceptions import ObjectNotFound
from prefect.runner.runner import Runner


async def main():
    async with get_client() as client:
        # Check if the smoke-test work pool exists
        try:
            await client.read_work_pool("smoke-test")
        except ObjectNotFound:
            # Create the work pool if it doesn't exist
            await client.create_work_pool(
                WorkPoolCreate(name="smoke-test", type="process")
            )

        # Deploy the flow
        smoke_test_flow = await Flow.afrom_source(
            source=Path(__file__).resolve().parent,
            entrypoint="client_flow.py:smoke_test_flow",
        )

        coro = smoke_test_flow.deploy(
            name="prefect-client-smoke-test",
            work_pool_name="smoke-test",
            print_next_steps=False,
        )
        if TYPE_CHECKING:
            assert inspect.iscoroutine(coro)

        deployment_id = await coro

        # Execute a run via a runner
        flow_run = await client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        await Runner().execute_flow_run(flow_run.id)


if __name__ == "__main__":
    asyncio.run(main())
