"""
Process-wide record of requests waiting out Prefect API maintenance.

When the API answers with a `Prefect-Maintenance: true` header, the HTTP clients
retry indefinitely, sleeping for the `Retry-After` they were given. Health checks
read this record so that a process deliberately waiting is not reported as stuck.
"""

import datetime
import threading

import prefect.types._datetime

_MAINTENANCE_BACKOFF_ENDS_AT: datetime.datetime | None = None
_MAINTENANCE_BACKOFF_LOCK = threading.Lock()


def record_maintenance_backoff(retry_seconds: float) -> None:
    """
    Record that a request is sleeping for `retry_seconds` before retrying a
    maintenance response.
    """
    global _MAINTENANCE_BACKOFF_ENDS_AT
    ends_at = prefect.types._datetime.now("UTC") + datetime.timedelta(
        seconds=retry_seconds
    )
    with _MAINTENANCE_BACKOFF_LOCK:
        # Concurrent requests each back off; the latest end wins.
        if (
            _MAINTENANCE_BACKOFF_ENDS_AT is None
            or ends_at > _MAINTENANCE_BACKOFF_ENDS_AT
        ):
            _MAINTENANCE_BACKOFF_ENDS_AT = ends_at


def maintenance_backoff_ends_at() -> datetime.datetime | None:
    """
    When the latest maintenance back-off in this process ends, or `None` if no
    request has backed off for maintenance.
    """
    with _MAINTENANCE_BACKOFF_LOCK:
        return _MAINTENANCE_BACKOFF_ENDS_AT


def _clear_maintenance_backoff() -> None:
    """Forget any recorded maintenance back-off (for tests)."""
    global _MAINTENANCE_BACKOFF_ENDS_AT
    with _MAINTENANCE_BACKOFF_LOCK:
        _MAINTENANCE_BACKOFF_ENDS_AT = None
