import os
import subprocess
import sys

from packaging.version import Version

import prefect

# The version oldest version this test runs with
SUPPORTED_VERSION = "2.6.0"


if Version(prefect.__version__) < Version(SUPPORTED_VERSION):
    raise NotImplementedError()


async def main():
    if Version(prefect.__version__) >= Version("2.13.0"):
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

                flow_instance = await prefect.flow.from_source(
                    source="https://github.com/PrefectHQ/prefect-recipes.git",
                    entrypoint="flows-starter/hello.py:hello",
                )

                await flow_instance.deploy(
                    name="demo-deployment",
                    work_pool_name="test-pool",
                )

                flow_run_state = flow_instance._run("demo-deployment")

                assert flow_run_state.is_completed(), flow_run_state

        finally:
            subprocess.check_call(
                ["prefect", "work-pool", "delete", "test-pool"],
                stdout=sys.stdout,
                stderr=sys.stderr,
            )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
