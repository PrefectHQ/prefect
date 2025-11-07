from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import prefect.types._datetime
from prefect.client.orchestration import get_client
from prefect.server.events.filters import EventFilter, EventOccurredFilter

if TYPE_CHECKING:
    from prefect.testing.utilities import PrefectTestHarness


class TestReadEvents:
    async def test_read_events_with_filter(
        self, prefect_client: PrefectTestHarness
    ) -> None:
        """test querying events with a filter"""
        async with get_client() as client:
            # create a filter for recent events
            now = prefect.types._datetime.now("UTC")
            event_filter = EventFilter(
                occurred=EventOccurredFilter(
                    since=now - timedelta(days=1),
                    until=now,
                )
            )

            # query events
            result = await client.read_events(filter=event_filter, limit=10)

            # verify response structure
            assert result.events is not None
            assert isinstance(result.events, list)
            assert result.total is not None
            assert isinstance(result.total, int)

    async def test_read_events_without_filter(
        self, prefect_client: PrefectTestHarness
    ) -> None:
        """test querying events without a filter"""
        async with get_client() as client:
            # query events without filter
            result = await client.read_events(limit=5)

            # verify response structure
            assert result.events is not None
            assert isinstance(result.events, list)
            assert result.total is not None
            assert isinstance(result.total, int)

    async def test_read_events_respects_limit(
        self, prefect_client: PrefectTestHarness
    ) -> None:
        """test that limit parameter is respected"""
        async with get_client() as client:
            limit = 3
            result = await client.read_events(limit=limit)

            # verify we don't get more than limit
            assert len(result.events) <= limit
