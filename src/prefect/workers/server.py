from typing import Any

import uvicorn
from fastapi import APIRouter, FastAPI, status
from fastapi.responses import JSONResponse

from prefect.settings import get_current_settings
from prefect.workers.base import BaseWorker


def build_healthcheck_server(
    worker: BaseWorker[Any, Any, Any],
    query_interval_seconds: float,
    log_level: str = "error",
) -> uvicorn.Server:
    """
    Build a healthcheck FastAPI server for a worker.

    Args:
        worker (BaseWorker | ProcessWorker): the worker whose health we will check
        log_level (str): the log
    """
    app = FastAPI()
    router = APIRouter()

    def perform_health_check():
        did_recently_poll = worker.is_worker_still_polling(
            query_interval_seconds=query_interval_seconds
        )

        if not did_recently_poll:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"message": "Worker may be unresponsive at this time"},
            )
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "OK"})

    router.add_api_route("/health", perform_health_check, methods=["GET"])

    app.include_router(router)

    settings = get_current_settings()
    config = uvicorn.Config(
        app=app,
        host=settings.worker.webserver.host,
        port=settings.worker.webserver.port,
        log_level=log_level,
        loop="asyncio",  # prevent uvloop from setting global policy
    )
    return uvicorn.Server(config=config)


def start_healthcheck_server(
    worker: BaseWorker[Any, Any, Any],
    query_interval_seconds: float,
    log_level: str = "error",
) -> None:
    """
    Run a healthcheck FastAPI server for a worker.

    Args:
        worker (BaseWorker | ProcessWorker): the worker whose health we will check
        log_level (str): the log level to use for the server
    """
    server = build_healthcheck_server(worker, query_interval_seconds, log_level)
    server.run()
