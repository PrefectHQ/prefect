"""Tests for flow run watching functionality"""

from __future__ import annotations

import asyncio

import pytest
from rich.console import Console
from typing_extensions import Self

import prefect.events.subscribers
from prefect import flow
from prefect.cli.flow_runs_watching import watch_flow_run
from prefect.client.orchestration import PrefectClient
from prefect.events import Event
from prefect.exceptions import FlowRunWaitTimeout, FlowRunWatchError
from prefect.flow_engine import run_flow_async
from prefect.states import Completed

pytestmark = [pytest.mark.usefixtures("hosted_api_server"), pytest.mark.clear_db]


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
    # The flow run is created in a terminal state but the subscriber won't
    # receive any new events for it, so watch_flow_run should time out. No
    # background flow task is needed to exercise the timeout path; spawning
    # one only introduces a race on cleanup cancellation.
    flow_run = await prefect_client.create_flow_run(flow=slow_flow, state=Completed())

    console = Console()

    with pytest.raises(FlowRunWaitTimeout, match="exceeded watch timeout"):
        await watch_flow_run(flow_run.id, console, timeout=1)


async def test_watch_flow_run_raises_when_stream_dies_before_completion(
    prefect_client: PrefectClient, monkeypatch
):
    """watch_flow_run must not report a non-terminal run as finished when the
    events/logs websocket dies before a terminal state is observed."""
    # A scheduled (non-terminal) flow run that is never actually executed.
    flow_run = await prefect_client.create_flow_run(flow=slow_flow)
    assert flow_run.state is not None and not flow_run.state.is_final()

    class DyingEventSubscriber:
        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *args) -> None:
            pass

        def __aiter__(self) -> Self:
            return self

        async def __anext__(self) -> Event:
            raise ConnectionError("events websocket died")

    class EmptyLogsSubscriber:
        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *args) -> None:
            pass

        def __aiter__(self) -> Self:
            return self

        async def __anext__(self):
            raise StopAsyncIteration

    monkeypatch.setattr(
        prefect.events.subscribers,
        "get_events_subscriber",
        lambda *args, **kwargs: DyingEventSubscriber(),
    )
    monkeypatch.setattr(
        prefect.events.subscribers,
        "get_logs_subscriber",
        lambda *args, **kwargs: EmptyLogsSubscriber(),
    )

    console = Console()

    with pytest.raises(FlowRunWatchError, match="before it reached a terminal state"):
        await watch_flow_run(flow_run.id, console)
