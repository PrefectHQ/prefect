"""Tests for flow run watching functionality"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from rich.console import Console
from typing_extensions import Self

from prefect.cli.flow_runs_watching import watch_flow_run
from prefect.client.schemas.objects import Log
from prefect.events import Event, Resource

pytestmark = pytest.mark.usefixtures("disable_hosted_api_server")


class MockFlowRunSubscriber:
    """Mock FlowRunSubscriber for testing"""

    def __init__(self, items: list[Log | Event]):
        self.items = items
        self._index = 0

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args) -> None:
        pass

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> Log | Event:
        if self._index >= len(self.items):
            raise StopAsyncIteration
        item = self.items[self._index]
        self._index += 1
        return item


async def test_watch_flow_run_exits_after_terminal_event(monkeypatch):
    """Test that watch_flow_run exits after receiving a terminal event"""
    from unittest.mock import AsyncMock

    from prefect.client.schemas.objects import FlowRun
    from prefect.states import Completed

    flow_run_id = uuid4()

    log1 = Log(
        id=uuid4(),
        name="test.logger",
        level=20,
        message="Starting flow",
        timestamp=datetime.now(timezone.utc),
        flow_run_id=flow_run_id,
    )

    event1 = Event(
        id=uuid4(),
        occurred=datetime.now(timezone.utc) + timedelta(seconds=1),
        event="prefect.flow-run.Running",
        resource=Resource(
            root={"prefect.resource.id": f"prefect.flow-run.{flow_run_id}"}
        ),
        payload={},
    )

    log2 = Log(
        id=uuid4(),
        name="test.logger",
        level=20,
        message="Flow finishing",
        timestamp=datetime.now(timezone.utc) + timedelta(seconds=2),
        flow_run_id=flow_run_id,
    )

    terminal_event = Event(
        id=uuid4(),
        occurred=datetime.now(timezone.utc) + timedelta(seconds=3),
        event="prefect.flow-run.Completed",
        resource=Resource(
            root={"prefect.resource.id": f"prefect.flow-run.{flow_run_id}"}
        ),
        payload={},
    )

    mock_subscriber = MockFlowRunSubscriber([log1, event1, log2, terminal_event])

    def mock_flow_run_subscriber(*args, **kwargs):
        return mock_subscriber

    flow_run = FlowRun(id=flow_run_id, flow_id=uuid4(), state=Completed())
    mock_client = AsyncMock()
    mock_client.read_flow_run = AsyncMock(return_value=flow_run)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    import prefect.cli.flow_runs_watching

    monkeypatch.setattr(
        prefect.cli.flow_runs_watching, "FlowRunSubscriber", mock_flow_run_subscriber
    )

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def mock_get_client_ctx(*args, **kwargs):
        yield mock_client

    monkeypatch.setattr(
        "prefect.cli.flow_runs_watching.get_client", mock_get_client_ctx
    )

    console = Console()

    start = asyncio.get_event_loop().time()
    result = await watch_flow_run(flow_run_id, console)
    duration = asyncio.get_event_loop().time() - start

    assert duration < 2.0
    assert result == flow_run


async def test_watch_flow_run_handles_empty_stream(monkeypatch):
    """Test that watch_flow_run handles empty stream gracefully"""
    from unittest.mock import AsyncMock

    from prefect.client.schemas.objects import FlowRun
    from prefect.states import Completed

    flow_run_id = uuid4()

    mock_subscriber = MockFlowRunSubscriber([])

    def mock_flow_run_subscriber(*args, **kwargs):
        return mock_subscriber

    flow_run = FlowRun(id=flow_run_id, flow_id=uuid4(), state=Completed())
    mock_client = AsyncMock()
    mock_client.read_flow_run = AsyncMock(return_value=flow_run)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    import prefect.cli.flow_runs_watching

    monkeypatch.setattr(
        prefect.cli.flow_runs_watching, "FlowRunSubscriber", mock_flow_run_subscriber
    )

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def mock_get_client_ctx(*args, **kwargs):
        yield mock_client

    monkeypatch.setattr(
        "prefect.cli.flow_runs_watching.get_client", mock_get_client_ctx
    )

    console = Console()

    result = await watch_flow_run(flow_run_id, console)
    assert result == flow_run


async def test_watch_flow_run_with_failed_state(monkeypatch):
    """Test that watch_flow_run returns flow run with failed state"""
    from unittest.mock import AsyncMock

    from prefect.client.schemas.objects import FlowRun
    from prefect.states import Failed

    flow_run_id = uuid4()

    terminal_event = Event(
        id=uuid4(),
        occurred=datetime.now(timezone.utc),
        event="prefect.flow-run.Failed",
        resource=Resource(
            root={"prefect.resource.id": f"prefect.flow-run.{flow_run_id}"}
        ),
        payload={},
    )

    mock_subscriber = MockFlowRunSubscriber([terminal_event])

    def mock_flow_run_subscriber(*args, **kwargs):
        return mock_subscriber

    flow_run = FlowRun(id=flow_run_id, flow_id=uuid4(), state=Failed())
    mock_client = AsyncMock()
    mock_client.read_flow_run = AsyncMock(return_value=flow_run)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    import prefect.cli.flow_runs_watching

    monkeypatch.setattr(
        prefect.cli.flow_runs_watching, "FlowRunSubscriber", mock_flow_run_subscriber
    )

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def mock_get_client_ctx(*args, **kwargs):
        yield mock_client

    monkeypatch.setattr(
        "prefect.cli.flow_runs_watching.get_client", mock_get_client_ctx
    )

    console = Console()

    result = await watch_flow_run(flow_run_id, console)
    assert result.state.is_failed()
    assert result == flow_run
