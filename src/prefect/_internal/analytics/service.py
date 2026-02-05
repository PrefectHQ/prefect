"""
Background analytics service for non-blocking event processing.

This module provides a singleton service that receives analytics events via a queue
and processes them in a background thread. The server analytics check is performed
once per process, off the main thread.
"""

import atexit
import os
import queue
import threading
from dataclasses import dataclass
from typing import Any, ClassVar

from prefect._internal.analytics.ci_detection import is_ci_environment
from prefect._internal.analytics.client import track_event


@dataclass
class AnalyticsEvent:
    """An analytics event to be processed by the background service."""

    event_name: str
    device_id: str
    extra_properties: dict[str, Any] | None = None


class AnalyticsService:
    """
    Background service for processing analytics events.

    This service:
    - Receives events via enqueue() which returns immediately (non-blocking)
    - Processes events in a background daemon thread
    - Performs the server analytics check once per process (with 5s timeout)
    - Caches the server check result in memory

    The service is lazily started when the first event is queued.
    """

    _instance: ClassVar["AnalyticsService | None"] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self) -> None:
        self._queue: queue.Queue[AnalyticsEvent | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._started = False
        self._analytics_enabled: bool | None = None
        self._analytics_checked = threading.Event()
        self._shutdown_requested = False
        self._instance_lock = threading.Lock()

    @classmethod
    def instance(cls) -> "AnalyticsService":
        """Get or create the singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    atexit.register(cls._instance.shutdown)
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance. Used for testing and fork safety."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance._shutdown_requested = True
                # Put None to wake up the thread if it's waiting
                try:
                    cls._instance._queue.put_nowait(None)
                except queue.Full:
                    pass
            cls._instance = None

    def enqueue(self, event: AnalyticsEvent) -> None:
        """
        Queue an event for processing. Returns immediately (non-blocking).

        Quick local checks (DO_NOT_TRACK, CI) are performed here to avoid
        queuing events that will never be sent.
        """
        # Quick local checks - these don't require network calls
        if not self._quick_enabled_check():
            return

        # Start the background thread on first event
        self._ensure_started()

        # Queue the event (non-blocking)
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            pass  # Drop event silently if queue is full

    def _quick_enabled_check(self) -> bool:
        """
        Quick non-blocking check of local telemetry settings.

        Returns False if DO_NOT_TRACK is set or we're in a CI environment.
        """
        do_not_track = os.environ.get("DO_NOT_TRACK", "").lower()
        if do_not_track in ("1", "true", "yes"):
            return False

        if is_ci_environment():
            return False

        return True

    def _ensure_started(self) -> None:
        """Start the background thread if not already running."""
        with self._instance_lock:
            if not self._started:
                self._started = True
                self._thread = threading.Thread(
                    target=self._run,
                    name="prefect-analytics",
                    daemon=True,
                )
                self._thread.start()

    def _run(self) -> None:
        """Background thread main loop."""
        try:
            # Check server analytics setting (5s timeout, off main thread)
            self._analytics_enabled = self._check_server_analytics()
            self._analytics_checked.set()

            if not self._analytics_enabled:
                # Drain the queue and exit - analytics are disabled
                self._drain_queue()
                return

            # Process events in a loop
            while not self._shutdown_requested:
                try:
                    event = self._queue.get(timeout=1.0)
                    if event is None:
                        # Shutdown signal or spurious wakeup
                        if self._shutdown_requested:
                            break
                        continue

                    self._process_event(event)
                    self._queue.task_done()
                except queue.Empty:
                    continue
                except Exception:
                    pass  # Silently ignore processing errors

        except Exception:
            self._analytics_checked.set()

    def _check_server_analytics(self) -> bool:
        """
        Check if the server has analytics enabled.

        When no API URL is configured, reads the local setting directly.
        When an API URL is set, queries the remote server using the Prefect client.
        """
        from prefect.settings.context import get_current_settings

        settings = get_current_settings()
        api_url = settings.api.url
        if not api_url:
            return settings.server.analytics_enabled

        try:
            from prefect.client.orchestration import get_client

            with get_client(sync_client=True) as client:
                response = client.request("GET", "/admin/settings")
                response.raise_for_status()
                server_settings = response.json()
                return server_settings.get("server", {}).get("analytics_enabled", False)
        except Exception:
            return False

    def _drain_queue(self) -> None:
        """Drain all events from the queue without processing them."""
        while True:
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                break

    def _process_event(self, event: AnalyticsEvent) -> None:
        """Process a single analytics event."""
        try:
            track_event(
                event_name=event.event_name,
                device_id=event.device_id,
                extra_properties=event.extra_properties,
            )
        except Exception:
            pass  # Silently ignore tracking errors

    def shutdown(self, timeout: float = 2.0) -> None:
        """
        Shutdown the service, flushing pending events.

        Args:
            timeout: Maximum time to wait for pending events to be processed.
        """
        self._shutdown_requested = True

        # Put None to wake up the thread if it's waiting
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def wait_for_analytics_check(self, timeout: float | None = None) -> bool | None:
        """
        Wait for the server analytics check to complete.

        Used primarily for testing. Returns the analytics enabled state,
        or None if the check hasn't completed within the timeout.
        """
        if self._analytics_checked.wait(timeout=timeout):
            return self._analytics_enabled
        return None


def _reset_after_fork() -> None:
    """Reset the service after a fork to avoid sharing state with parent."""
    AnalyticsService.reset()


# Register fork handler if available (Unix systems)
if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_reset_after_fork)
