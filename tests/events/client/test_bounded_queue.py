import logging
import queue
import uuid

import pytest

from prefect.events import Event
from prefect.events.worker import EventsWorker
from prefect.settings import Settings, temporary_settings
from prefect.settings.legacy import _get_settings_fields


def make_event() -> Event:
    return Event(
        event="vogon.poetry.read",
        resource={"prefect.resource.id": f"poem.{uuid.uuid4()}"},
    )


class TestBoundedQueue:
    """Tests for bounded queue behavior in QueueService and EventsWorker."""

    def test_default_max_queue_size_is_10000(self):
        """The default setting for worker_queue_max_size should be 10000."""
        settings = Settings()
        assert settings.events.worker_queue_max_size == 10000

    def test_max_queue_size_env_var(self, monkeypatch: pytest.MonkeyPatch):
        """The setting can be configured via environment variable."""
        monkeypatch.setenv("PREFECT_EVENTS_WORKER_QUEUE_MAX_SIZE", "500")
        settings = Settings()
        assert settings.events.worker_queue_max_size == 500

    def test_max_queue_size_zero_means_unbounded(self, monkeypatch: pytest.MonkeyPatch):
        """Setting worker_queue_max_size to 0 means unbounded queue."""
        monkeypatch.setenv("PREFECT_EVENTS_WORKER_QUEUE_MAX_SIZE", "0")
        settings = Settings()
        assert settings.events.worker_queue_max_size == 0

    def test_events_worker_uses_setting_for_queue_size(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """EventsWorker should read the max queue size from settings."""
        max_size = EventsWorker._get_max_queue_size()
        # Default is 10000
        assert max_size == 10000

    def test_queue_service_send_drops_when_full(
        self,
        caplog: pytest.LogCaptureFixture,
        asserting_events_worker: EventsWorker,
    ):
        """When the queue is full, new items should be dropped with a warning."""
        # Manually set a small queue to test the full behavior
        asserting_events_worker._queue = queue.Queue(maxsize=3)

        # Fill the queue
        for _ in range(3):
            asserting_events_worker._queue.put_nowait(make_event())

        # Now the queue is full; sending another should drop with warning
        with caplog.at_level(logging.WARNING):
            asserting_events_worker.send(make_event())

        assert "queue is full" in caplog.text
        assert asserting_events_worker._queue.qsize() == 3

    def test_queue_service_send_succeeds_when_not_full(
        self,
        asserting_events_worker: EventsWorker,
    ):
        """Items should be enqueued normally when the queue is not full."""
        # Manually set a small queue
        asserting_events_worker._queue = queue.Queue(maxsize=3)

        event = make_event()
        asserting_events_worker.send(event)

        assert asserting_events_worker._queue.qsize() == 1

    def test_unbounded_queue_accepts_many_items(
        self,
        asserting_events_worker: EventsWorker,
    ):
        """With maxsize=0 (unbounded), the queue should accept many items."""
        asserting_events_worker._queue = queue.Queue(maxsize=0)

        for _ in range(1000):
            asserting_events_worker.send(make_event())

        assert asserting_events_worker._queue.qsize() == 1000

    def test_setting_name_is_valid(self):
        """The setting PREFECT_EVENTS_WORKER_QUEUE_MAX_SIZE should be discoverable."""
        settings_fields = _get_settings_fields(Settings)
        assert "PREFECT_EVENTS_WORKER_QUEUE_MAX_SIZE" in settings_fields
