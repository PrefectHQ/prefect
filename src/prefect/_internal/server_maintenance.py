"""
Process-wide record of requests waiting out Prefect API maintenance.

When the API answers with a `Prefect-Maintenance: true` header, the HTTP clients
retry indefinitely, sleeping for the `Retry-After` they were given. Health checks
read this record so that a process deliberately waiting is not reported as stuck.
"""

import datetime
import threading

import prefect.types._datetime

_backoff_ends_at: datetime.datetime | None = None
_backoff_lock = threading.Lock()


def record_maintenance_backoff(retry_seconds: float) -> None:
    """
    Record that a request is sleeping for `retry_seconds` before retrying a
    maintenance response.
    """
    global _backoff_ends_at
    ends_at = prefect.types._datetime.now("UTC") + datetime.timedelta(
        seconds=retry_seconds
    )
    with _backoff_lock:
        # Concurrent requests each back off; the latest end wins.
        if _backoff_ends_at is None or ends_at > _backoff_ends_at:
            _backoff_ends_at = ends_at


def maintenance_backoff_ends_at() -> datetime.datetime | None:
    """
    When the latest maintenance back-off in this process ends, or `None` if no
    request has backed off for maintenance.
    """
    with _backoff_lock:
        return _backoff_ends_at


def reset_maintenance_backoff() -> None:
    """Forget any recorded maintenance back-off (for tests)."""
    global _backoff_ends_at
    with _backoff_lock:
        _backoff_ends_at = None
