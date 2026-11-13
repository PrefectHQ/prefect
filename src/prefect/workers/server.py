import logging
import threading
from contextlib import contextmanager
from typing import Any, Callable, Generator, Optional

import uvicorn
from fastapi import APIRouter, FastAPI, status
from fastapi.responses import JSONResponse

import prefect.types._datetime
from prefect.logging.loggers import get_logger
from prefect.settings import get_current_settings
from prefect.workers.base import (
    BaseWorker,
    _is_within_polling_window,  # pyright: ignore[reportPrivateUsage]
)

logger: "logging.Logger" = get_logger("workers.server")


class _WorkerStartupHealthcheck:  # pyright: ignore[reportUnusedClass]
    """
    Health of a worker process from the moment it starts, including before the
    worker itself is created.

    Until `worker` is set, health is measured from startup with the worker's
    polling window; after, the worker's own polling health is used.
    """

    def __init__(self, query_interval_seconds: float) -> None:
        self.query_interval_seconds = query_interval_seconds
        self.started_at = prefect.types._datetime.now("UTC")
        self.worker: Optional[BaseWorker[Any, Any, Any]] = None

    def __call__(self) -> bool:
        if self.worker is not None:
            return self.worker.is_worker_still_polling(
                query_interval_seconds=self.query_interval_seconds
            )
        return _is_within_polling_window(self.started_at, self.query_interval_seconds)


def _build_healthcheck_server(
    is_healthy: Callable[[], bool], log_level: str = "error"
) -> uvicorn.Server:
    app = FastAPI()
    router = APIRouter()

    def perform_health_check():
        if not is_healthy():
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


@contextmanager
def _run_healthcheck_server(  # pyright: ignore[reportUnusedFunction]
    is_healthy: Callable[[], bool], log_level: str = "error"
) -> Generator[None, None, None]:
    """
    Serve a healthcheck backed by `is_healthy` for the duration of the context.
    """
    server = _build_healthcheck_server(is_healthy, log_level)
    # Run the ASGI server in a separate thread so that uvicorn does not block
    # the main thread.
    thread = threading.Thread(
        name="healthcheck-server-thread", target=server.run, daemon=True
    )
    thread.start()
    try:
        yield
    finally:
        logger.debug("Stopping healthcheck server...")
        server.should_exit = True
        thread.join()
        logger.debug("Healthcheck server stopped.")


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
    return _build_healthcheck_server(
        lambda: worker.is_worker_still_polling(
            query_interval_seconds=query_interval_seconds
        ),
        log_level,
    )


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
