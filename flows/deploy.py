import shutil
import subprocess
import sys
from pathlib import Path
from uuid import UUID

import anyio

import prefect
from prefect import Flow
from prefect.client.schemas.objects import FlowRun
from prefect.deployments import run_deployment


async def read_flow_run(flow_run_id: UUID):
    async with prefect.get_client() as client:
        return await client.read_flow_run(flow_run_id)


def main():
    try:
        subprocess.check_call(
            ["prefect", "work-pool", "create", "test-deploy-pool", "-t", "process"],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        flow_instance = prefect.flow.from_source(
            source="https://github.com/PrefectHQ/prefect-recipes.git",
            entrypoint="flows-starter/hello.py:hello",
        )
        assert isinstance(flow_instance, Flow)

        flow_instance.deploy(
            name="demo-deployment",
            work_pool_name="test-deploy-pool",
            parameters={"name": "world"},
        )

        flow_run = run_deployment("hello/demo-deployment", timeout=0)
        assert isinstance(flow_run, FlowRun)

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
        assert flow_run.state is not None
        assert flow_run.state.is_completed(), flow_run.state

    finally:
        subprocess.check_call(
            ["prefect", "--no-prompt", "work-pool", "delete", "test-deploy-pool"],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        shutil.rmtree(
            Path(__file__).parent.parent / "prefect-recipes", ignore_errors=True
        )


if __name__ == "__main__":
    main()
