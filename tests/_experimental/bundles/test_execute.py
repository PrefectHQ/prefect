from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

from prefect import flow
from prefect.bundles.execute import execute_bundle
from prefect.client.orchestration import PrefectClient


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
