from __future__ import annotations

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import prefect.bundles as bundles_module
import prefect.runner._starter_bundle as starter_module
from prefect import flow
from prefect.bundles import create_bundle_for_flow_run
from prefect.bundles.execute import execute_bundle
from prefect.client.orchestration import PrefectClient
from prefect.logging.loggers import flow_run_logger


def _log_bundle_crashed_hook(flow: Any, flow_run: Any, state: Any) -> None:
    flow_run_logger(flow_run, flow).error("bundle crash hook ran")


async def test_execute_bundle_creates_executor_with_propose_submitting_false(
    prefect_client: PrefectClient,
):
    @flow
    def test_flow() -> str:
        return "ok"

    flow_run = await prefect_client.create_flow_run(test_flow)
    bundle: dict[str, Any] = {
        "flow_run": flow_run.model_dump(mode="json"),
    }

    captured_kwargs: dict[str, Any] = {}
    mock_submit = AsyncMock(return_value=None)

    from prefect.runner._flow_run_executor import FlowRunExecutorContext

    original_create_executor = FlowRunExecutorContext.create_executor

    def capture_create_executor(
        self_ctx: FlowRunExecutorContext, *args: Any, **kwargs: Any
    ) -> Any:
        captured_kwargs.update(kwargs)
        result = original_create_executor(self_ctx, *args, **kwargs)
        result.submit = mock_submit
        return result

    with patch.object(
        FlowRunExecutorContext,
        "create_executor",
        side_effect=capture_create_executor,
        autospec=True,
    ):
        await execute_bundle(bundle)

    assert captured_kwargs.get("propose_submitting") is False


@pytest.mark.usefixtures("use_hosted_api_server")
async def test_execute_bundle_preserves_failed_outcome(
    prefect_client: PrefectClient,
    caplog: pytest.LogCaptureFixture,
):
    @flow(on_crashed=[_log_bundle_crashed_hook])
    def failed_flow() -> None:
        raise ValueError("application failure")

    flow_run = await prefect_client.create_flow_run(failed_flow)
    with patch.object(
        bundles_module.subprocess,
        "check_output",
        MagicMock(return_value=b""),
    ):
        bundle = create_bundle_for_flow_run(failed_flow, flow_run)["bundle"]

    processes: list[Any] = []
    original_execute_bundle_in_subprocess = starter_module.execute_bundle_in_subprocess

    def tracking_execute_bundle(*args: Any, **kwargs: Any):
        process = original_execute_bundle_in_subprocess(*args, **kwargs)
        processes.append(process)
        return process

    with patch.object(
        starter_module,
        "execute_bundle_in_subprocess",
        side_effect=tracking_execute_bundle,
    ):
        infrastructure_result = await execute_bundle(bundle)

    flow_run = await prefect_client.read_flow_run(flow_run.id)
    assert processes[0].exitcode == 0
    assert infrastructure_result is None
    assert flow_run.state is not None
    assert flow_run.state.is_failed()
    assert "bundle crash hook ran" not in caplog.text
    assert "Process exited with status code: 1" not in caplog.text


@pytest.mark.usefixtures("use_hosted_api_server")
async def test_execute_bundle_preserves_crash_fallback(
    prefect_client: PrefectClient,
    caplog: pytest.LogCaptureFixture,
):
    @flow(on_crashed=[_log_bundle_crashed_hook])
    def crashed_flow() -> None:
        os._exit(7)

    flow_run = await prefect_client.create_flow_run(crashed_flow)
    with patch.object(
        bundles_module.subprocess,
        "check_output",
        MagicMock(return_value=b""),
    ):
        bundle = create_bundle_for_flow_run(crashed_flow, flow_run)["bundle"]

    processes: list[Any] = []
    original_execute_bundle_in_subprocess = starter_module.execute_bundle_in_subprocess

    def tracking_execute_bundle(*args: Any, **kwargs: Any):
        process = original_execute_bundle_in_subprocess(*args, **kwargs)
        processes.append(process)
        return process

    with patch.object(
        starter_module,
        "execute_bundle_in_subprocess",
        side_effect=tracking_execute_bundle,
    ):
        await execute_bundle(bundle)

    flow_run = await prefect_client.read_flow_run(flow_run.id)
    assert processes[0].exitcode == 7
    assert flow_run.state is not None
    assert flow_run.state.is_crashed()
    assert "bundle crash hook ran" in caplog.text
    assert "Process exited with status code: 7" in caplog.text
