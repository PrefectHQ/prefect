import shutil
import subprocess
import sys
from pathlib import Path

import anyio
import uv

import prefect
from prefect.deployments import run_deployment


async def read_flow_run(flow_run_id):
    async with prefect.get_client() as client:
        return await client.read_flow_run(flow_run_id)


def test_deploy():
    try:
        subprocess.check_call(
            [
                uv.find_uv_bin(),
                "run",
                "--isolated",
                "prefect",
                "work-pool",
                "create",
                "test-deploy-pool",
                "-t",
                "process",
            ],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        flow_instance = prefect.flow.from_source(
            source="https://github.com/PrefectHQ/prefect-recipes.git",
            entrypoint="flows-starter/hello.py:hello",
        )

        flow_instance.deploy(
            name="demo-deployment",
            work_pool_name="test-deploy-pool",
            parameters={"name": "world"},
        )

        flow_run = run_deployment("hello/demo-deployment", timeout=0)

        subprocess.check_call(
            [
                uv.find_uv_bin(),
                "run",
                "--isolated",
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
            [
                uv.find_uv_bin(),
                "run",
                "--isolated",
                "prefect",
                "--no-prompt",
                "work-pool",
                "delete",
                "test-deploy-pool",
            ],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        shutil.rmtree(
            Path(__file__).parent.parent / "prefect-recipes", ignore_errors=True
        )
