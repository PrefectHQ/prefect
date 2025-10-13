"""Tests for flow run watching functionality"""

from __future__ import annotations

import asyncio

import pytest
from rich.console import Console

from prefect import flow
from prefect.cli.flow_runs_watching import watch_flow_run
from prefect.client.orchestration import PrefectClient
from prefect.exceptions import FlowRunWaitTimeout
from prefect.flow_engine import run_flow_async
from prefect.states import Completed

pytestmark = pytest.mark.usefixtures("hosted_api_server")


@flow
async def successful_flow():
    """Simple flow that completes successfully"""
    return 42


@flow
async def failing_flow():
    """Simple flow that raises an error"""
    raise ValueError("Intentional test failure")


@flow
async def slow_flow():
    """Simple flow that takes a long time"""
    await asyncio.sleep(10)


async def test_watch_flow_run_exits_after_successful_completion(
    prefect_client: PrefectClient,
):
    """Test that watch_flow_run exits after flow run completes successfully"""
    flow_run = await prefect_client.create_flow_run(
        flow=successful_flow, state=Completed()
    )

    console = Console()

    # Start the flow in the background
    flow_task = asyncio.create_task(
        run_flow_async(
            flow=successful_flow,
            flow_run=flow_run,
            return_type="state",
        )
    )

    # Watch the flow run
    result = await watch_flow_run(flow_run.id, console)

    # Clean up
    await flow_task

    assert result.state.is_completed()
    assert result.id == flow_run.id


async def test_watch_flow_run_with_failed_state(prefect_client: PrefectClient):
    """Test that watch_flow_run returns flow run with failed state"""
    flow_run = await prefect_client.create_flow_run(
        flow=failing_flow, state=Completed()
    )

    console = Console()

    # Start the flow in the background
    flow_task = asyncio.create_task(
        run_flow_async(
            flow=failing_flow,
            flow_run=flow_run,
            return_type="state",
        )
    )

    # Watch the flow run
    result = await watch_flow_run(flow_run.id, console)

    # Clean up
    await flow_task

    assert result.state.is_failed()
    assert result.id == flow_run.id


async def test_watch_flow_run_timeout(prefect_client: PrefectClient):
    """Test that watch_flow_run raises timeout when flow run exceeds timeout"""
    flow_run = await prefect_client.create_flow_run(flow=slow_flow, state=Completed())

    console = Console()

    # Start the flow in the background
    flow_task = asyncio.create_task(
        run_flow_async(
            flow=slow_flow,
            flow_run=flow_run,
            return_type="state",
        )
    )

    # Start watching with a short timeout
    with pytest.raises(FlowRunWaitTimeout, match="exceeded watch timeout"):
        await watch_flow_run(flow_run.id, console, timeout=1)

    # Clean up - cancel the slow flow
    flow_task.cancel()
    try:
        await flow_task
    except asyncio.CancelledError:
        pass
