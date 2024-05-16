import os
import subprocess
import sys

import anyio
from packaging.version import Version

import prefect

# The version oldest version this test runs with
SUPPORTED_VERSION = "2.6.0"


if Version(prefect.__version__) < Version(SUPPORTED_VERSION):
    raise NotImplementedError()


async def read_flow_run(flow_run_id):
    async with prefect.get_client() as client:
        return await client.read_flow_run(flow_run_id)


def main():
    if Version(prefect.__version__) >= Version("2.19.0"):
        from prefect.deployments import run_deployment

        try:
            TEST_SERVER_VERSION = os.environ.get(
                "TEST_SERVER_VERSION", prefect.__version__
            )
            # Work pool became GA in 2.8.0
            if Version(prefect.__version__) >= Version("2.8") and Version(
                TEST_SERVER_VERSION
            ) >= Version("2.8"):
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
