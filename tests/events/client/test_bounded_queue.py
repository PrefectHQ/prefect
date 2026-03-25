"""Tests for bounded EventsWorker queue."""

import logging
import uuid

from prefect._internal.concurrency.services import QueueService
from prefect.events.schemas.events import Event
from prefect.events.worker import EventsWorker


class BoundedTestService(QueueService[str]):
    """A test service with a bounded queue."""

    _max_queue_size = 3

    async def _handle(self, item: str) -> None:
        pass


class UnboundedTestService(QueueService[str]):
    """A test service with the default unbounded queue."""

    async def _handle(self, item: str) -> None:
        pass


class TestBoundedQueue:
    """Tests for the _max_queue_size class variable on QueueService."""

    def test_default_unbounded(self):
        """By default, _max_queue_size is 0 (unbounded)."""
        service = UnboundedTestService.__new__(UnboundedTestService)
        service.__init__()
        assert service._queue.maxsize == 0

    def test_bounded_queue_maxsize(self):
        """When _max_queue_size is set, the queue has that maxsize."""
        service = BoundedTestService.__new__(BoundedTestService)
        service.__init__()
        assert service._queue.maxsize == 3

    def test_drop_on_full_queue(self, caplog: logging.LoggerAdapter):
        """When the queue is full, send() drops the item with a warning."""
        service = BoundedTestService.__new__(BoundedTestService)
        service.__init__()
        service._started = True
        service._stopped = False

        # Fill the queue
        for i in range(3):
            service._queue.put_nowait(f"item-{i}")

        assert service._queue.full()

        # Next send should drop with warning, not raise
        with caplog.at_level(logging.WARNING):
            service.send("overflow-item")

        assert "queue is full" in caplog.text
        assert service._queue.qsize() == 3  # Still 3, overflow was dropped

    def test_unbounded_does_not_drop(self):
        """An unbounded queue never triggers the drop path."""
        service = UnboundedTestService.__new__(UnboundedTestService)
        service.__init__()
        service._started = True
        service._stopped = False

        # Put many items — should never raise queue.Full
        for i in range(100):
            service._queue.put_nowait(f"item-{i}")

        assert service._queue.qsize() == 100

    def test_reset_for_fork_preserves_maxsize(self):
        """After fork reset, the new queue retains the maxsize."""
        service = BoundedTestService.__new__(BoundedTestService)
        service.__init__()
        assert service._queue.maxsize == 3

        service.reset_for_fork()
        assert service._queue.maxsize == 3


class TestEventsWorkerInstanceAttribute:
    """Tests that EventsWorker sets _max_queue_size as an instance attribute."""

    def test_max_queue_size_is_instance_attribute(self):
        """_max_queue_size should be set on the instance, not the class."""
        original_class_value = EventsWorker.__dict__.get("_max_queue_size")
        worker = EventsWorker.__new__(EventsWorker)
        worker.__init__(
            client_type=type("FakeClient", (), {}),
            client_options=(()),
        )
        # The instance should have its own _max_queue_size
        assert "_max_queue_size" in worker.__dict__
        # The class variable should not have been mutated
        assert EventsWorker.__dict__.get("_max_queue_size") == original_class_value


class TestEventsWorkerOnItemDropped:
    """Tests that EventsWorker._on_item_dropped cleans up _context_cache."""

    def test_on_item_dropped_removes_context_cache_entry(self):
        """When an event is dropped, its _context_cache entry should be removed."""
        worker = EventsWorker.__new__(EventsWorker)
        worker.__init__(
            client_type=type("FakeClient", (), {}),
            client_options=(()),
        )

        event = Event(
            event="test.event",
            resource={"prefect.resource.id": f"test.{uuid.uuid4()}"},
        )

        # Simulate _prepare_item which adds to _context_cache
        prepared = worker._prepare_item(event)
        assert event.id in worker._context_cache

        # Simulate the drop
        worker._on_item_dropped(prepared)
        assert event.id not in worker._context_cache

    def test_on_item_dropped_noop_for_missing_id(self):
        """_on_item_dropped should not raise if the event id is not in cache."""
        worker = EventsWorker.__new__(EventsWorker)
        worker.__init__(
            client_type=type("FakeClient", (), {}),
            client_options=(()),
        )

        event = Event(
            event="test.event",
            resource={"prefect.resource.id": f"test.{uuid.uuid4()}"},
        )

        # Should not raise
        worker._on_item_dropped(event)
