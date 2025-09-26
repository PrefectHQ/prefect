"""
Health check server for Prefect services, following the same pattern as the worker health check.
"""

import uvicorn
from fastapi import APIRouter, FastAPI, status
from fastapi.responses import JSONResponse


def build_healthcheck_server(log_level: str = "error") -> uvicorn.Server:
    """
    Build a healthcheck FastAPI server for services.

    Unlike the worker healthcheck, this is a simple liveness check that
    returns 200 OK if the services are running.

    Args:
        log_level (str): the log level to use for the server

    Returns:
        uvicorn.Server: the configured server ready to run
    """
    app = FastAPI()
    router = APIRouter()

    def perform_health_check():
        # Simple liveness check - if we can respond, services are running
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "OK"})

    router.add_api_route("/health", perform_health_check, methods=["GET"])
    app.include_router(router)

    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=8080,
        log_level=log_level,
    )
    return uvicorn.Server(config=config)
