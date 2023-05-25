from fastapi import FastAPI, APIRouter
from typing import Union
import uvicorn

from prefect.workers.base import BaseWorker
from prefect.workers.process import ProcessWorker


def start_healthcheck_server(
    worker: Union[BaseWorker, ProcessWorker], run_once: bool, log_level: str = "error"
) -> None:
    """
    Run a healthcheck FastAPI server for a worker.

    Args:
        worker (BaseWorker | ProcessWorker): the worker to check health for
        run_once (bool): if True, skip starting the webserver
        log_level (str): the log level to use for the server
    """
    if not run_once:
        webserver = FastAPI()
        router = APIRouter()

        router.add_api_route("/health", worker.check_last_polled, methods=["GET"])
        router.add_api_route("/info", worker.get_status, methods=["GET"])

        webserver.include_router(router)

        uvicorn.run(webserver, host="0.0.0.0", port=8080, log_level=log_level)
