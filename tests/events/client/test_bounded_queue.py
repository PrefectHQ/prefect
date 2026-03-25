"""Tests for bounded EventsWorker queue."""

import logging

from prefect._internal.concurrency.services import QueueService


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
