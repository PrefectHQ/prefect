from typing import Union

import uvicorn
from fastapi import APIRouter, FastAPI, status
from fastapi.responses import JSONResponse

from prefect.settings import (
    PREFECT_WORKER_WEBSERVER_HOST,
    PREFECT_WORKER_WEBSERVER_PORT,
)
from prefect.workers.base import BaseWorker
from prefect.workers.process import ProcessWorker


def start_healthcheck_server(
    worker: Union[BaseWorker, ProcessWorker],
    query_interval_seconds: int,
    log_level: str = "error",
) -> None:
    """
    Run a healthcheck FastAPI server for a worker.

    Args:
        worker (BaseWorker | ProcessWorker): the worker whose health we will check
        log_level (str): the log level to use for the server
    """
    webserver = FastAPI()
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

    webserver.include_router(router)

    uvicorn.run(
        webserver,
        host=PREFECT_WORKER_WEBSERVER_HOST.value(),
        port=PREFECT_WORKER_WEBSERVER_PORT.value(),
        log_level=log_level,
    )
