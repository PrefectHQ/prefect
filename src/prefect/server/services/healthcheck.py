"""
Healthcheck server for Prefect services.
"""

from datetime import datetime
from typing import Dict

import uvicorn
from fastapi import APIRouter, FastAPI, status
from fastapi.responses import JSONResponse

from prefect.settings import (
    PREFECT_SERVER_SERVICES_HEALTHCHECK_HOST,
    PREFECT_SERVER_SERVICES_HEALTHCHECK_PORT,
)
from prefect.types._datetime import now


class ServicesHealthMonitor:
    """
    Monitors the health of running services by tracking their last activity.
    """

    def __init__(self):
        self._last_activity: Dict[str, datetime] = {}

    def record_activity(self, service_name: str) -> None:
        """Record that a service has performed its loop."""
        self._last_activity[service_name] = now("UTC")

    def is_healthy(self, service_name: str, threshold_seconds: float) -> bool:
        """
        Check if a service is healthy based on its last activity.

        Args:
            service_name: The name of the service to check
            threshold_seconds: Maximum seconds since last activity before considered unhealthy

        Returns:
            True if the service has been active within the threshold, False otherwise
        """
        last_activity = self._last_activity.get(service_name)
        if last_activity is None:
            return False

        time_since_activity = (now("UTC") - last_activity).total_seconds()
        return time_since_activity <= threshold_seconds

    def get_all_statuses(self, threshold_seconds: float) -> Dict[str, bool]:
        """Get health status for all tracked services."""
        return {
            name: self.is_healthy(name, threshold_seconds)
            for name in self._last_activity
        }


def build_services_healthcheck_server(
    health_monitor: ServicesHealthMonitor,
    log_level: str = "error",
) -> uvicorn.Server:
    """
    Build a healthcheck FastAPI server for services.

    Args:
        health_monitor: The health monitor tracking service activity
        log_level: The log level for the uvicorn server

    Returns:
        A configured uvicorn server
    """
    app = FastAPI()
    router = APIRouter()

    def perform_health_check():
        # Check if any services have been recorded
        if not health_monitor._last_activity:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"message": "No services have reported activity yet"},
            )

        # Get status of all services (using 2x loop interval as threshold)
        statuses = health_monitor.get_all_statuses(threshold_seconds=120)

        # If any service is unhealthy, return 503
        unhealthy_services = [name for name, healthy in statuses.items() if not healthy]
        if unhealthy_services:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "message": "Some services are unhealthy",
                    "unhealthy_services": unhealthy_services,
                    "all_statuses": statuses,
                },
            )

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "All services are healthy",
                "statuses": statuses,
            },
        )

    router.add_api_route("/health", perform_health_check, methods=["GET"])
    app.include_router(router)

    config = uvicorn.Config(
        app=app,
        host=PREFECT_SERVER_SERVICES_HEALTHCHECK_HOST.value(),
        port=PREFECT_SERVER_SERVICES_HEALTHCHECK_PORT.value(),
        log_level=log_level,
    )
    return uvicorn.Server(config=config)
