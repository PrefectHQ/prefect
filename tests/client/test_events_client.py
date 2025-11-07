from datetime import timedelta
from typing import TYPE_CHECKING

import prefect.types._datetime
from prefect.client.orchestration import get_client
from prefect.events.filters import EventFilter, EventOccurredFilter

if TYPE_CHECKING:
    from prefect.testing.utilities import PrefectTestHarness


class TestReadEventsAsync:
    async def test_read_events_with_filter(
        self, prefect_client: "PrefectTestHarness"
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
        self, prefect_client: "PrefectTestHarness"
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
        self, prefect_client: "PrefectTestHarness"
    ) -> None:
        """test that limit parameter is respected"""
        async with get_client() as client:
            limit = 3
            result = await client.read_events(limit=limit)

            # verify we don't get more than limit
            assert len(result.events) <= limit

    async def test_read_events_page(self, prefect_client: "PrefectTestHarness") -> None:
        """test paginating through events"""
        async with get_client() as client:
            # get first page with small limit
            first_page = await client.read_events(limit=5)

            # if there's a next page, fetch it
            if first_page.next_page:
                second_page = await client.read_events_page(first_page.next_page)

                # verify we got events
                assert second_page.events is not None
                assert isinstance(second_page.events, list)
                assert second_page.total is not None
                assert isinstance(second_page.total, int)

    async def test_get_next_page(self, prefect_client: "PrefectTestHarness") -> None:
        """test using EventPage.get_next_page() method"""
        async with get_client() as client:
            # get first page with small limit
            first_page = await client.read_events(limit=5)

            # fetch next page using the method on EventPage
            second_page = await first_page.get_next_page(client)

            if second_page:
                # verify we got events
                assert second_page.events is not None
                assert isinstance(second_page.events, list)
                assert second_page.total is not None
                assert isinstance(second_page.total, int)


class TestReadEventsSync:
    def test_read_events_with_filter(
        self, sync_prefect_client: "PrefectTestHarness"
    ) -> None:
        """test querying events with a filter using sync client"""
        with get_client(sync_client=True) as client:
            # create a filter for recent events
            now = prefect.types._datetime.now("UTC")
            event_filter = EventFilter(
                occurred=EventOccurredFilter(
                    since=now - timedelta(days=1),
                    until=now,
                )
            )

            # query events
            result = client.read_events(filter=event_filter, limit=10)

            # verify response structure
            assert result.events is not None
            assert isinstance(result.events, list)
            assert result.total is not None
            assert isinstance(result.total, int)

    def test_read_events_without_filter(
        self, sync_prefect_client: "PrefectTestHarness"
    ) -> None:
        """test querying events without a filter using sync client"""
        with get_client(sync_client=True) as client:
            # query events without filter
            result = client.read_events(limit=5)

            # verify response structure
            assert result.events is not None
            assert isinstance(result.events, list)
            assert result.total is not None
            assert isinstance(result.total, int)

    def test_read_events_respects_limit(
        self, sync_prefect_client: "PrefectTestHarness"
    ) -> None:
        """test that limit parameter is respected using sync client"""
        with get_client(sync_client=True) as client:
            limit = 3
            result = client.read_events(limit=limit)

            # verify we don't get more than limit
            assert len(result.events) <= limit

    def test_read_events_page(self, sync_prefect_client: "PrefectTestHarness") -> None:
        """test paginating through events using sync client"""
        with get_client(sync_client=True) as client:
            # get first page with small limit
            first_page = client.read_events(limit=5)

            # if there's a next page, fetch it
            if first_page.next_page:
                second_page = client.read_events_page(first_page.next_page)

                # verify we got events
                assert second_page.events is not None
                assert isinstance(second_page.events, list)
                assert second_page.total is not None
                assert isinstance(second_page.total, int)

    def test_get_next_page_sync(
        self, sync_prefect_client: "PrefectTestHarness"
    ) -> None:
        """test using EventPage.get_next_page_sync() method"""
        with get_client(sync_client=True) as client:
            # get first page with small limit
            first_page = client.read_events(limit=5)

            # fetch next page using the method on EventPage
            second_page = first_page.get_next_page_sync(client)

            if second_page:
                # verify we got events
                assert second_page.events is not None
                assert isinstance(second_page.events, list)
                assert second_page.total is not None
                assert isinstance(second_page.total, int)
