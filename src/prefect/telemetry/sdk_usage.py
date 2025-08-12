"""
SDK usage telemetry collection.

Collects anonymous usage metrics to help improve Prefect.
No personal or sensitive data is collected.
"""

import json
import platform
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

import prefect
from prefect.logging import get_logger
from prefect.settings import get_current_settings
from prefect.telemetry.state import TelemetryState

logger = get_logger(__name__)


@dataclass
class UsageEvent:
    """A single usage event."""

    event_type: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    data: Dict[str, Any] = field(default_factory=dict)


class SDKUsageCollector:
    """
    Collects SDK usage metrics for telemetry.

    This collector tracks:
    - Features used (decorators, options)
    - Block types (not values)
    - Exception types (not messages)
    - Environment info
    """

    _instance: Optional["SDKUsageCollector"] = None

    def __init__(self):
        self.settings = get_current_settings().telemetry
        self.state = TelemetryState()
        self.enabled = self.settings.enabled

        # Tracking data
        self._events: List[UsageEvent] = []
        self._features: Set[str] = set()
        self._block_types: Set[str] = set()
        self._exception_types: Set[str] = set()
        self._decorators_used: Dict[str, int] = defaultdict(int)

        if self.enabled:
            logger.debug(f"SDK telemetry enabled, session: {self.state.session_id}")

    @classmethod
    def get_instance(cls) -> "SDKUsageCollector":
        """Get or create singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def record_feature(self, feature: str) -> None:
        """Record usage of a feature."""
        if not self.enabled:
            return
        self._features.add(feature)
        logger.debug(f"Telemetry: recorded feature '{feature}'")

    def record_decorator(self, decorator_type: str, **kwargs) -> None:
        """Record usage of a decorator (flow/task)."""
        if not self.enabled:
            return

        self._decorators_used[decorator_type] += 1

        # Track specific features from kwargs
        if kwargs.get("retries"):
            self.record_feature(f"{decorator_type}_retries")
        if kwargs.get("cache_key_fn"):
            self.record_feature(f"{decorator_type}_caching")
        if kwargs.get("persist_result"):
            self.record_feature(f"{decorator_type}_persist_result")
        if kwargs.get("tags"):
            self.record_feature(f"{decorator_type}_tags")

        event = UsageEvent(
            event_type=f"{decorator_type}_defined",
            data={"feature_flags": list(kwargs.keys())},
        )
        self._events.append(event)
        logger.debug(f"Telemetry: recorded {decorator_type} decorator")

    def record_block_type(self, block_type: str) -> None:
        """Record usage of a block type."""
        if not self.enabled:
            return
        # Sanitize block type (remove credentials suffix, etc)
        clean_type = (
            block_type.lower().replace("-credentials", "").replace("_credentials", "")
        )
        self._block_types.add(clean_type)
        logger.debug(f"Telemetry: recorded block type '{clean_type}'")

    def record_exception(self, exc: Exception) -> None:
        """Record an exception type."""
        if not self.enabled:
            return
        exc_type = type(exc).__name__
        # Skip Prefect internal exceptions
        if not exc_type.startswith("Prefect"):
            self._exception_types.add(exc_type)
            logger.debug(f"Telemetry: recorded exception type '{exc_type}'")

    def get_payload(self) -> Dict[str, Any]:
        """Get the telemetry payload that would be sent."""
        return {
            "session_id": self.state.session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sdk_version": prefect.__version__,
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "os": platform.system().lower(),
            "os_version": platform.version(),
            "architecture": platform.machine(),
            "usage": {
                "features": sorted(list(self._features)),
                "block_types": sorted(list(self._block_types)),
                "exception_types": sorted(list(self._exception_types)),
                "decorators": dict(self._decorators_used),
                "event_count": len(self._events),
            },
            "events": [
                asdict(e) for e in self._events[-10:]
            ],  # Last 10 events for debugging
        }

    def preview(self) -> str:
        """Get a preview of what would be sent (for user inspection)."""
        payload = self.get_payload()
        # Remove session ID for preview
        payload["session_id"] = "<anonymous-session-id>"
        return json.dumps(payload, indent=2, sort_keys=True)

    def reset(self):
        """Reset collected data (useful for testing)."""
        self._events.clear()
        self._features.clear()
        self._block_types.clear()
        self._exception_types.clear()
        self._decorators_used.clear()


# Global accessor
def get_sdk_collector() -> SDKUsageCollector:
    """Get the SDK usage collector instance."""
    return SDKUsageCollector.get_instance()


# Convenience functions for instrumentation
def record_feature(feature: str) -> None:
    """Record a feature usage."""
    get_sdk_collector().record_feature(feature)


def record_decorator(decorator_type: str, **kwargs) -> None:
    """Record decorator usage."""
    get_sdk_collector().record_decorator(decorator_type, **kwargs)
