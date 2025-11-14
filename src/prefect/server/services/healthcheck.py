import socket
from typing import Optional

import uvicorn
from fastapi import APIRouter, FastAPI, status
from fastapi.responses import JSONResponse

from prefect.settings import get_current_settings


def _is_port_available(host: str, port: int) -> bool:
    """Check if a port is available for binding."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return True
        except (socket.error, OSError):
            return False


def build_healthcheck_server(
    host: Optional[str] = None,
    port: Optional[int] = None,
    log_level: str = "error",
) -> uvicorn.Server:
    """
    Build a healthcheck FastAPI server for the Prefect background services.

    Args:
        host: The host address to bind to. If not provided, uses the setting value.
        port: The port to bind to. If not provided, uses the setting value.
        log_level: The log level for the uvicorn server. Defaults to "error".

    Returns:
        A configured uvicorn.Server instance.

    Raises:
        OSError: If the specified port is not available.
    """
    settings = get_current_settings()
    healthcheck_settings = settings.server.services.healthcheck_webserver

    host = host or healthcheck_settings.host
    port = port or healthcheck_settings.port

    if not _is_port_available(host, port):
        raise OSError(
            f"Port {port} on host {host} is already in use. "
            "Please specify a different port or stop the service using it."
        )

    app = FastAPI()
    router = APIRouter()

    def healthcheck() -> JSONResponse:
        """Healthcheck endpoint that returns OK status."""
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "OK"})

    router.add_api_route("/health", healthcheck, methods=["GET"])
    app.include_router(router)

    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level=log_level,
    )
    return uvicorn.Server(config=config)
