import os
from pathlib import Path
from typing import Any

import prefect
from prefect.client.schemas.objects import FlowRun, State
from prefect.flows import Flow

from .utils import get_output


@prefect.flow(name="test")
def test_flow():
    return get_output()


@prefect.flow(name="test")
def prod_flow():
    return get_output()


def mark_crashed_hook(
    flow: Flow[Any, Any], flow_run: FlowRun, state: State[Any]
) -> None:
    if marker_path := os.environ.get("PREFECT_TEST_PROCESS_WORKER_CRASH_MARKER"):
        Path(marker_path).touch()


@prefect.flow(name="failed", on_crashed=[mark_crashed_hook])
def failed_flow() -> None:
    raise ValueError("application failure")
