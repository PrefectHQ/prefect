import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent
from uuid import uuid4

import anyio
import uv

import prefect
from prefect.settings import PREFECT_API_URL


async def read_flow_run(flow_run_id):
    async with prefect.get_client() as client:
        return await client.read_flow_run(flow_run_id)


def test_auto_uv_runtime_sync_disables_bytecode_compilation(tmp_path: Path):
    project = tmp_path / "uv-project"
    project.mkdir()
    marker = tmp_path / "engine-env.txt"
    flow_file = project / "flow.py"
    flow_file.write_text(
        dedent(
            f"""
            import os
            from pathlib import Path

            from prefect import flow


            @flow
            def check_uv_compile_bytecode():
                value = os.environ.get("UV_COMPILE_BYTECODE")
                Path({str(marker)!r}).write_text(value or "")
                assert value == "0"
            """
        )
    )
    (project / "pyproject.toml").write_text(
        dedent(
            f"""
            [project]
            name = "prefect-uv-runtime-env"
            version = "0.1.0"
            requires-python = "=={sys.version_info.major}.{sys.version_info.minor}.*"
            dependencies = ["prefect"]
            """
        )
    )

    flow_name = f"uv-runtime-env-{uuid4()}"

    async def create_run():
        async with prefect.get_client() as client:
            flow_id = await client.create_flow_from_name(flow_name)
            deployment_id = await client.create_deployment(
                flow_id=flow_id,
                name="uv-runtime-env",
                entrypoint="flow.py:check_uv_compile_bytecode",
                pull_steps=[
                    {
                        "prefect.deployments.steps.set_working_directory": {
                            "directory": str(project)
                        }
                    }
                ],
            )
            return await client.create_flow_run_from_deployment(deployment_id)

    flow_run = anyio.run(create_run)
    env = os.environ.copy()
    api_url = PREFECT_API_URL.value()
    assert api_url is not None
    env["PREFECT_API_URL"] = api_url
    env["UV_COMPILE_BYTECODE"] = "1"

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
        env=env,
    )

    flow_run = anyio.run(read_flow_run, flow_run.id)
    assert flow_run.state.is_completed(), flow_run.state
    assert marker.read_text() == "0"
