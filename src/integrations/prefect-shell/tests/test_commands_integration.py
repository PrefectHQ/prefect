from __future__ import annotations

import asyncio
from uuid import UUID

import pytest
from prefect_shell.commands import ShellOperation

from prefect import flow
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import LogFilter, LogFilterFlowRunId
from prefect.context import get_run_context
from prefect.logging.handlers import APILogHandler
from prefect.settings import PREFECT_LOGGING_TO_API_ENABLED, temporary_settings

pytestmark = pytest.mark.integration


async def wait_for_flow_run_logs(
    flow_run_id: UUID, expected_count: int
) -> list[object]:
    for _ in range(30):
        async with get_client() as client:
            logs = await client.read_logs(
                log_filter=LogFilter(
                    flow_run_id=LogFilterFlowRunId(any_=[flow_run_id]),
                )
            )
        if len(logs) >= expected_count:
            return logs
        await asyncio.sleep(0.1)

    return logs


async def test_sync_streaming_output_is_sent_to_api():
    with temporary_settings(updates={PREFECT_LOGGING_TO_API_ENABLED: True}):

        @flow
        def test_flow() -> UUID:
            ShellOperation(
                commands=[
                    "echo out1",
                    "echo err1 >&2",
                    "echo out2",
                    "echo err2 >&2",
                ]
            ).run()
            return get_run_context().flow_run.id

        flow_run_id = test_flow()
        await APILogHandler.aflush()
        logs = await wait_for_flow_run_logs(flow_run_id, expected_count=6)

    messages = {log.message for log in logs}
    assert any("PID" in message and "stream output:" in message for message in messages)
    assert any("out1" in message for message in messages)
    assert any("out2" in message for message in messages)
    assert any("PID" in message and "stderr:" in message for message in messages)
    assert any("err1" in message for message in messages)
    assert any("err2" in message for message in messages)
