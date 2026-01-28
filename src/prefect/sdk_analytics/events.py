"""
Event type definitions for SDK telemetry.
"""

from typing import Literal

# Quick Start Funnel events
SDKEvent = Literal[
    "sdk_imported",
    "first_flow_defined",
    "first_flow_run",
    "first_deployment_created",
    "first_schedule_created",
]
