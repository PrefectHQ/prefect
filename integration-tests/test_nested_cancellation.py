import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import UUID, uuid4

import uv

import prefect
from prefect import flow, get_client
from prefect.client.schemas.filters import FlowRunFilter, FlowRunFilterParentFlowRunId
from prefect.client.schemas.objects import FlowRun
from prefect.client.schemas.sorting import FlowRunSort
from prefect.settings import PREFECT_API_URL
from prefect.states import Cancelling

REPO_ROOT = Path(__file__).resolve().parents[1]
PARENT_HOOK_MARKER = "parent-cancelled"
CHILD_HOOK_MARKER = "child-cancelled"
CHILD_STARTED_MARKER = "child-started"
BACKGROUND_TASK_STARTED_MARKER = "background-task-started"
BACKGROUND_TASK_CANCELLED_MARKER = "background-task-cancelled"


def _write_marker(marker_dir: str, marker_name: str, flow_run_id: UUID) -> None:
    Path(marker_dir, marker_name).write_text(str(flow_run_id))


def parent_cancel_hook(flow, flow_run, state):
    _write_marker(flow_run.parameters["marker_dir"], PARENT_HOOK_MARKER, flow_run.id)


def child_cancel_hook(flow, flow_run, state):
    _write_marker(flow_run.parameters["marker_dir"], CHILD_HOOK_MARKER, flow_run.id)


@flow(on_cancellation=[child_cancel_hook], log_prints=True)
def child_flow(marker_dir: str):
    Path(marker_dir, CHILD_STARTED_MARKER).write_text("started")
    while True:
        time.sleep(0.2)


@flow(on_cancellation=[parent_cancel_hook], log_prints=True)
def parent_flow(marker_dir: str):
    child_flow(marker_dir)


@flow(on_cancellation=[child_cancel_hook], log_prints=True)
async def async_child_flow(marker_dir: str):
    Path(marker_dir, CHILD_STARTED_MARKER).write_text("started")
    while True:
        await asyncio.sleep(0.2)


@flow(on_cancellation=[parent_cancel_hook], log_prints=True)
async def async_parent_flow(marker_dir: str):
    await async_child_flow(marker_dir)


async def background_task(marker_dir: str) -> None:
    Path(marker_dir, BACKGROUND_TASK_STARTED_MARKER).write_text("started")
    try:
        while True:
            await asyncio.sleep(0.2)
    except asyncio.CancelledError:
        Path(marker_dir, BACKGROUND_TASK_CANCELLED_MARKER).write_text("cancelled")
        raise


@flow(log_prints=True)
async def async_flow_with_background_task(marker_dir: str):
    asyncio.create_task(background_task(marker_dir))
    await _wait_for_background_task_start(marker_dir)
    return "done"


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
        except Exception as exc:  # pragma: no cover - diagnostic path
            last_error = exc
            result = None

        if result:
            return result

        time.sleep(interval)

    if last_error is not None:
        raise AssertionError(message) from last_error
    raise AssertionError(message)


async def _wait_for_background_task_start(
    marker_dir: str,
    timeout: float = 10.0,
) -> None:
    deadline = time.monotonic() + timeout
    started_marker = Path(marker_dir, BACKGROUND_TASK_STARTED_MARKER)
    while time.monotonic() < deadline:
        if started_marker.exists():
            return
        await asyncio.sleep(0.05)
    raise TimeoutError("Background task never started.")


def _read_child_flow_runs(parent_flow_run_id: UUID) -> list[FlowRun]:
    with get_client(sync_client=True) as client:
        return client.read_flow_runs(
            flow_run_filter=FlowRunFilter(
                parent_flow_run_id=FlowRunFilterParentFlowRunId(
                    any_=[parent_flow_run_id]
                )
            ),
            sort=FlowRunSort.EXPECTED_START_TIME_ASC,
        )


def _read_flow_run(flow_run_id: UUID) -> FlowRun:
    with get_client(sync_client=True) as client:
        return client.read_flow_run(flow_run_id)


def _run_flow_run_execute_cancellation_test(
    *,
    tmp_path: Path,
    entrypoint: str,
):
    api_url = PREFECT_API_URL.value()
    assert api_url, "PREFECT_API_URL must be configured for integration tests."
    cli_env = {**os.environ, "PREFECT_API_URL": api_url}

    work_pool_name = f"nested-cancel-pool-{uuid4()}"
    deployment_name = f"nested-cancel-deployment-{uuid4()}"
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    execution_log_path = tmp_path / "flow-run-execute.log"

    work_pool_created = False
    deployment_id: UUID | None = None
    parent_flow_run_id: UUID | None = None
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
            entrypoint=entrypoint,
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
            parent_flow_run = client.create_flow_run_from_deployment(deployment_id)
            parent_flow_run_id = parent_flow_run.id

        execution_log = execution_log_path.open("w")
        execution_process = subprocess.Popen(
            [
                uv.find_uv_bin(),
                "run",
                "--isolated",
                "prefect",
                "flow-run",
                "execute",
                str(parent_flow_run_id),
            ],
            stdout=execution_log,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=REPO_ROOT,
            env=cli_env,
        )

        _wait_for(
            lambda: (
                flow_run
                if (flow_run := _read_flow_run(parent_flow_run_id)).state
                and flow_run.state.is_running()
                else None
            ),
            timeout=90,
            message=(
                "Parent flow run never entered RUNNING.\n"
                f"Execution log:\n{_worker_output(execution_log_path)}"
            ),
        )

        child_flow_run = _wait_for(
            lambda: (
                child_runs[0]
                if Path(marker_dir, CHILD_STARTED_MARKER).exists()
                and len(
                    child_runs := [
                        run
                        for run in _read_child_flow_runs(parent_flow_run_id)
                        if run.state and run.state.is_running()
                    ]
                )
                == 1
                else None
            ),
            timeout=90,
            message=(
                "Child subflow never entered RUNNING.\n"
                f"Execution log:\n{_worker_output(execution_log_path)}"
            ),
        )

        with get_client(sync_client=True) as client:
            client.set_flow_run_state(parent_flow_run_id, Cancelling())

        return_code = execution_process.wait(timeout=120)
        assert return_code == 0, (
            f"`prefect flow-run execute` exited with code {return_code}.\n"
            f"Execution log:\n{_worker_output(execution_log_path)}"
        )

        parent_terminal_run = _wait_for(
            lambda: (
                flow_run
                if (flow_run := _read_flow_run(parent_flow_run_id)).state
                and flow_run.state.is_cancelled()
                else None
            ),
            timeout=60,
            message=(
                "Parent flow run did not reach CANCELLED.\n"
                f"Execution log:\n{_worker_output(execution_log_path)}"
            ),
        )
        child_terminal_run = _wait_for(
            lambda: (
                flow_run
                if any(
                    run.id == child_flow_run.id
                    and run.state
                    and run.state.is_cancelled()
                    for run in _read_child_flow_runs(parent_flow_run_id)
                )
                and (
                    flow_run := next(
                        run
                        for run in _read_child_flow_runs(parent_flow_run_id)
                        if run.id == child_flow_run.id
                    )
                )
                else None
            ),
            timeout=60,
            message=(
                "Child subflow run did not reach CANCELLED.\n"
                f"Execution log:\n{_worker_output(execution_log_path)}"
            ),
        )

        assert parent_terminal_run.state and parent_terminal_run.state.is_cancelled()
        assert child_terminal_run.state and child_terminal_run.state.is_cancelled()
        # Hook execution and Cancelled-state persistence are independent side
        # effects of the same cancel sequence, so on rare occasions the state
        # can be visible to us before the hook's marker file is. Wait for the
        # markers instead of asserting synchronously.
        _wait_for(
            lambda: Path(marker_dir, PARENT_HOOK_MARKER).exists(),
            timeout=30,
            message=(
                "Parent on_cancellation hook did not write its marker.\n"
                f"Execution log:\n{_worker_output(execution_log_path)}"
            ),
        )
        _wait_for(
            lambda: Path(marker_dir, CHILD_HOOK_MARKER).exists(),
            timeout=30,
            message=(
                "Child on_cancellation hook did not write its marker.\n"
                f"Execution log:\n{_worker_output(execution_log_path)}"
            ),
        )
        assert Path(marker_dir, PARENT_HOOK_MARKER).read_text() == str(
            parent_flow_run_id
        )
        assert Path(marker_dir, CHILD_HOOK_MARKER).read_text() == str(child_flow_run.id)

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


def _run_flow_run_execute_background_task_shutdown_test(
    *,
    tmp_path: Path,
    entrypoint: str,
):
    api_url = PREFECT_API_URL.value()
    assert api_url, "PREFECT_API_URL must be configured for integration tests."
    cli_env = {**os.environ, "PREFECT_API_URL": api_url}

    work_pool_name = f"background-task-pool-{uuid4()}"
    deployment_name = f"background-task-deployment-{uuid4()}"
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
            entrypoint=entrypoint,
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

        return_code = execution_process.wait(timeout=120)
        assert return_code == 0, (
            f"`prefect flow-run execute` exited with code {return_code}.\n"
            f"Execution log:\n{_worker_output(execution_log_path)}"
        )

        terminal_run = _wait_for(
            lambda: (
                run
                if (run := _read_flow_run(flow_run_id)).state
                and run.state.is_completed()
                else None
            ),
            timeout=60,
            message=(
                "Flow run did not reach COMPLETED.\n"
                f"Execution log:\n{_worker_output(execution_log_path)}"
            ),
        )

        assert terminal_run.state and terminal_run.state.is_completed()
        assert Path(marker_dir, BACKGROUND_TASK_STARTED_MARKER).exists(), (
            "Background task never started.\n"
            f"Execution log:\n{_worker_output(execution_log_path)}"
        )
        assert Path(marker_dir, BACKGROUND_TASK_CANCELLED_MARKER).exists(), (
            "Background task was not cancelled during asyncio.run shutdown.\n"
            f"Execution log:\n{_worker_output(execution_log_path)}"
        )

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


def test_flow_run_execute_cancellation_runs_nested_subflow_hooks(tmp_path: Path):
    _run_flow_run_execute_cancellation_test(
        tmp_path=tmp_path,
        entrypoint="integration-tests/test_nested_cancellation.py:parent_flow",
    )


def test_flow_run_execute_cancellation_runs_nested_async_subflow_hooks(
    tmp_path: Path,
):
    _run_flow_run_execute_cancellation_test(
        tmp_path=tmp_path,
        entrypoint="integration-tests/test_nested_cancellation.py:async_parent_flow",
    )


def test_flow_run_execute_async_flow_cleans_up_background_tasks(tmp_path: Path):
    _run_flow_run_execute_background_task_shutdown_test(
        tmp_path=tmp_path,
        entrypoint="integration-tests/test_nested_cancellation.py:async_flow_with_background_task",
    )
