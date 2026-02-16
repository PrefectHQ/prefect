import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import anyio
import uv

import prefect
from prefect.deployments import run_deployment
from prefect.runner.storage import GitRepository


async def read_flow_run(flow_run_id):
    async with prefect.get_client() as client:
        return await client.read_flow_run(flow_run_id)


def test_deploy():
    tmp_dir = Path(tempfile.mkdtemp())
    runner_dir = tmp_dir / "runner"
    runner_dir.mkdir()

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

        # Create GitRepository and set base path to temp directory
        # to avoid race conditions with parallel tests
        git_repo = GitRepository(
            url="https://github.com/PrefectHQ/examples.git",
        )
        git_repo.set_base_path(tmp_dir)

        flow_instance = prefect.flow.from_source(
            source=git_repo,
            entrypoint="flows/hello_world.py:hello",
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
            cwd=runner_dir,
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

        # Clean up temp directory
        shutil.rmtree(tmp_dir, ignore_errors=True)
