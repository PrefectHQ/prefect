import subprocess
import sys

import anyio

import prefect
from prefect.deployments import run_deployment


async def read_flow_run(flow_run_id):
    async with prefect.get_client() as client:
        return await client.read_flow_run(flow_run_id)


def main():
    try:
        subprocess.check_call(
            ["prefect", "work-pool", "create", "test-pool", "-t", "process"],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        flow_instance = prefect.flow.from_source(
            source="https://github.com/PrefectHQ/prefect-recipes.git",
            entrypoint="flows-starter/hello.py:hello",
        )

        flow_instance.deploy(
            name="demo-deployment",
            work_pool_name="test-pool",
            parameters={"name": "world"},
        )

        flow_run = run_deployment("hello/demo-deployment", timeout=0)

        subprocess.check_call(
            [
                "prefect",
                "flow-run",
                "execute",
                str(flow_run.id),
            ],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        flow_run = anyio.run(read_flow_run, flow_run.id)
        assert flow_run.state.is_completed(), flow_run.state

    finally:
        subprocess.check_call(
            ["prefect", "work-pool", "delete", "test-pool"],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )


if __name__ == "__main__":
    main()
