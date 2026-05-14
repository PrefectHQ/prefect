import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import UUID, uuid4

import uv

import prefect
from prefect import flow, get_client, task
from prefect.client.schemas.objects import FlowRun
from prefect.flow_runs import suspend_flow_run
from prefect.settings import PREFECT_API_URL

REPO_ROOT = Path(__file__).resolve().parents[1]
STARTED_MARKER = "flow-started"
COMPLETED_MARKER = "flow-completed"
TASK_MARKER_PREFIX = "task-"
# Keep enough task boundaries that the in-subprocess FlowRunSuspendingObserver
# has time to receive the Suspended event via the events websocket before the
# flow completes.  The original 30 × 0.2 s ≈ 6 s window was too narrow under
# CI load; 150 × 0.2 s ≈ 30 s absorbs realistic event-propagation latency.
TASK_COUNT = 150
TASK_SLEEP = 0.2


@task
def write_task_marker(marker_dir: str, index: int) -> None:
    Path(marker_dir, f"{TASK_MARKER_PREFIX}{index}").write_text("done")
    time.sleep(TASK_SLEEP)


@flow(log_prints=True, persist_result=True)
def externally_suspended_flow(marker_dir: str) -> None:
    Path(marker_dir, STARTED_MARKER).write_text("started")
    for index in range(TASK_COUNT):
        write_task_marker(marker_dir, index)
    Path(marker_dir, COMPLETED_MARKER).write_text("completed")


def _worker_output(log_path: Path) -> str:
    if not log_path.exists():
        return "<no worker log>"
    return log_path.read_text()[-4000:]


def _wait_for(
    predicate,
    *,
    timeout: float,
    message: str,
    interval: float = 0.2,
):
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            result = predicate()
        except Exception as exc:
            last_error = exc
            result = None

        if result:
            return result

        time.sleep(interval)

    if last_error is not None:
        raise AssertionError(message) from last_error
    raise AssertionError(message)


def _read_flow_run(flow_run_id: UUID) -> FlowRun:
    with get_client(sync_client=True) as client:
        return client.read_flow_run(flow_run_id)


def _task_marker_count(marker_dir: Path) -> int:
    return len(list(marker_dir.glob(f"{TASK_MARKER_PREFIX}*")))


def test_external_suspension_stops_flow_run_at_next_task_boundary(tmp_path: Path):
    api_url = PREFECT_API_URL.value()
    assert api_url, "PREFECT_API_URL must be configured for integration tests."
    cli_env = {**os.environ, "PREFECT_API_URL": api_url}

    work_pool_name = f"suspension-pool-{uuid4()}"
    deployment_name = f"suspension-deployment-{uuid4()}"
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    execution_log_path = tmp_path / "flow-run-execute.log"

    work_pool_created = False
    deployment_id: UUID | None = None
    flow_run_id: UUID | None = None
    execution_process: subprocess.Popen[str] | None = None
    execution_log = None

    try:
        subprocess.check_call(
            [
                uv.find_uv_bin(),
                "run",
                "--isolated",
                "prefect",
                "work-pool",
                "create",
                work_pool_name,
                "-t",
                "process",
            ],
            stdout=sys.stdout,
            stderr=sys.stderr,
            cwd=REPO_ROOT,
            env=cli_env,
        )
        work_pool_created = True

        deployment_id = prefect.flow.from_source(
            source=str(REPO_ROOT),
            entrypoint="integration-tests/test_flow_suspension.py:externally_suspended_flow",
        ).deploy(
            name=deployment_name,
            work_pool_name=work_pool_name,
            parameters={"marker_dir": str(marker_dir)},
            build=False,
            push=False,
            print_next_steps=False,
            ignore_warnings=True,
        )

        with get_client(sync_client=True) as client:
            flow_run = client.create_flow_run_from_deployment(deployment_id)
            flow_run_id = flow_run.id

        execution_log = execution_log_path.open("w")
        execution_process = subprocess.Popen(
            [
                uv.find_uv_bin(),
                "run",
                "--isolated",
                "prefect",
                "flow-run",
                "execute",
                str(flow_run_id),
            ],
            stdout=execution_log,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=REPO_ROOT,
            env=cli_env,
        )

        _wait_for(
            lambda: (
                _task_marker_count(marker_dir)
                if Path(marker_dir, STARTED_MARKER).exists()
                and _task_marker_count(marker_dir) > 0
                and (flow_run := _read_flow_run(flow_run_id)).state
                and flow_run.state.is_running()
                else None
            ),
            timeout=90,
            message=(
                "Flow run did not start and complete an initial task boundary.\n"
                f"Execution log:\n{_worker_output(execution_log_path)}"
            ),
        )

        suspend_flow_run(flow_run_id=flow_run_id)

        return_code = execution_process.wait(timeout=120)
        assert return_code == 0, (
            f"`prefect flow-run execute` exited with code {return_code}.\n"
            f"Execution log:\n{_worker_output(execution_log_path)}"
        )

        suspended_run = _wait_for(
            lambda: (
                flow_run
                if (flow_run := _read_flow_run(flow_run_id)).state
                and flow_run.state.is_paused()
                and flow_run.state.name == "Suspended"
                else None
            ),
            timeout=60,
            message=(
                "Flow run did not reach Suspended.\n"
                f"Execution log:\n{_worker_output(execution_log_path)}"
            ),
        )

        task_marker_count = _task_marker_count(marker_dir)
        assert suspended_run.state and suspended_run.state.name == "Suspended"
        assert 0 < task_marker_count < TASK_COUNT, (
            f"Expected suspension before all tasks completed, got {task_marker_count}"
            f" task markers.\nExecution log:\n{_worker_output(execution_log_path)}"
        )
        assert not Path(marker_dir, COMPLETED_MARKER).exists()

    finally:
        if execution_process is not None and execution_process.poll() is None:
            execution_process.terminate()
            try:
                execution_process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                execution_process.kill()
                execution_process.wait(timeout=20)

        if execution_log is not None:
            execution_log.close()

        if deployment_id is not None:
            with get_client(sync_client=True) as client:
                client.delete_deployment(deployment_id)

        if work_pool_created:
            subprocess.check_call(
                [
                    uv.find_uv_bin(),
                    "run",
                    "--isolated",
                    "prefect",
                    "--no-prompt",
                    "work-pool",
                    "delete",
                    work_pool_name,
                ],
                stdout=sys.stdout,
                stderr=sys.stderr,
                cwd=REPO_ROOT,
                env=cli_env,
            )
