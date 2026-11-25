"""Runs a real flow through the entrypoint, in the forked child, against the test harness."""

import contextvars
import logging
import sys
import textwrap
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from uuid import UUID

import pytest
from prefect_aws.microvm import entrypoint

import prefect.context
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import LogFilter, LogFilterFlowRunId
from prefect.flows import load_flow_from_entrypoint
from prefect.states import Pending, StateType

pytestmark = [
    pytest.mark.skipif(sys.platform == "win32", reason="The MicroVM entrypoint forks."),
    pytest.mark.filterwarnings(
        "ignore:This process .* is multi-threaded:DeprecationWarning"
    ),
]

FLOW_SOURCE = textwrap.dedent(
    """
    from prefect import flow, get_run_logger


    @flow
    def microvm_child_test_flow():
        logger = get_run_logger()
        logger.info("info line from the MicroVM child test flow")
        logger.debug("debug line from the MicroVM child test flow")
        return 42
    """
)
UNREACHABLE_API_URL = "http://127.0.0.1:9/api"

PostRunHook = Callable[..., threading.Thread]


@pytest.fixture
def flow_entrypoint(tmp_path: Path) -> str:
    flow_file = tmp_path / "microvm_child_test_flow.py"
    flow_file.write_text(FLOW_SOURCE)
    return f"{flow_file}:microvm_child_test_flow"


@pytest.fixture
def settings_resolved_before_run(
    monkeypatch: pytest.MonkeyPatch, api_from_environment: str
) -> Iterator[None]:
    """
    Leave the process configured as it is in a MicroVM before `/run`: global
    settings with no usable API URL, and the `prefect` logger at INFO.
    """
    # On macOS, a forked child of a multithreaded process crashes in the system
    # proxy lookup; a proxy variable in the environment skips that lookup.
    monkeypatch.setenv("no_proxy", "*")
    monkeypatch.setenv("PREFECT_API_URL", UNREACHABLE_API_URL)
    prefect.context.refresh_global_settings_context()
    monkeypatch.setenv("PREFECT_API_URL", api_from_environment)

    prefect_logger = logging.getLogger("prefect")
    previous_level = prefect_logger.level
    prefect_logger.setLevel(logging.INFO)
    try:
        yield
    finally:
        prefect_logger.setLevel(previous_level)


def create_pending_flow_run(entrypoint: str) -> UUID:
    flow = load_flow_from_entrypoint(entrypoint)
    with get_client(sync_client=True) as client:
        return client.create_flow_run(flow, state=Pending()).id


def read_log_messages(flow_run_id: UUID) -> list[str]:
    with get_client(sync_client=True) as client:
        logs = client.read_logs(
            LogFilter(flow_run_id=LogFilterFlowRunId(any_=[flow_run_id]))
        )
    return [log.message for log in logs]


def run_main_for(
    monkeypatch: pytest.MonkeyPatch,
    post_run_hook: PostRunHook,
    port: int,
    flow_run_id: UUID,
    run_env: dict[str, str],
) -> int:
    # Registered so that the values `/run` writes are undone after the test.
    for name, value in run_env.items():
        monkeypatch.setenv(name, value)
    poster = post_run_hook(port, flow_run_id, run_env)
    # An empty context has no harness settings, so the parent and child read
    # the global settings, as they do in a MicroVM.
    exit_code = contextvars.Context().run(entrypoint.main, port)
    poster.join(timeout=10)
    return exit_code


@pytest.mark.usefixtures("settings_resolved_before_run")
def test_flow_run_completes_in_the_child_with_its_logs_in_the_api(
    monkeypatch: pytest.MonkeyPatch,
    flow_entrypoint: str,
    post_run_hook: PostRunHook,
    hook_port: int,
):
    flow_run_id = create_pending_flow_run(flow_entrypoint)
    # The deployment path: `load_flow` reads the entrypoint from the environment,
    # which stands in for the deployment's code here.
    run_env = {
        "PREFECT__FLOW_ENTRYPOINT": flow_entrypoint,
        "PREFECT_LOGGING_LEVEL": "DEBUG",
    }

    exit_code = run_main_for(
        monkeypatch, post_run_hook, hook_port, flow_run_id, run_env
    )

    assert exit_code == 0
    with get_client(sync_client=True) as client:
        state = client.read_flow_run(flow_run_id).state
    assert state is not None
    assert state.type == StateType.COMPLETED
    messages = read_log_messages(flow_run_id)
    assert "info line from the MicroVM child test flow" in messages
    assert "debug line from the MicroVM child test flow" in messages


@pytest.mark.usefixtures("settings_resolved_before_run")
def test_flow_load_failure_is_logged_to_the_flow_run(
    monkeypatch: pytest.MonkeyPatch,
    flow_entrypoint: str,
    tmp_path: Path,
    post_run_hook: PostRunHook,
    hook_port: int,
):
    flow_run_id = create_pending_flow_run(flow_entrypoint)
    run_env = {"PREFECT__FLOW_ENTRYPOINT": f"{tmp_path / 'missing.py'}:microvm_flow"}

    exit_code = run_main_for(
        monkeypatch, post_run_hook, hook_port, flow_run_id, run_env
    )

    assert exit_code == 1
    with get_client(sync_client=True) as client:
        state = client.read_flow_run(flow_run_id).state
    assert state is not None
    assert state.type == StateType.CRASHED
    [message] = read_log_messages(flow_run_id)
    assert message.startswith(
        "Unexpected exception encountered when trying to load flow\nTraceback"
    )
    assert "missing.py" in message
