from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, Callable, Optional

import uvicorn
from fastapi import APIRouter, FastAPI, status
from fastapi.responses import JSONResponse
from typing_extensions import Literal

from prefect.logging import get_logger
from prefect.settings import (
    PREFECT_RUNNER_POLL_FREQUENCY,
    PREFECT_RUNNER_SERVER_HOST,
    PREFECT_RUNNER_SERVER_LOG_LEVEL,
    PREFECT_RUNNER_SERVER_MISSED_POLLS_TOLERANCE,
    PREFECT_RUNNER_SERVER_PORT,
)
from prefect.types._datetime import now as now_fn
from prefect.utilities.asyncutils import run_coro_as_sync

if TYPE_CHECKING:
    import logging

    from prefect.runner import Runner

from pydantic import BaseModel

logger: "logging.Logger" = get_logger("runner.webserver")

RunnableEndpoint = Literal["deployment", "flow", "task"]


class RunnerGenericFlowRunRequest(BaseModel):
    entrypoint: str
    parameters: Optional[dict[str, Any]] = None
    parent_task_run_id: Optional[uuid.UUID] = None


def perform_health_check(
    runner: "Runner", delay_threshold: int | None = None
) -> Callable[..., JSONResponse]:
    if delay_threshold is None:
        delay_threshold = (
            PREFECT_RUNNER_SERVER_MISSED_POLLS_TOLERANCE.value()
            * PREFECT_RUNNER_POLL_FREQUENCY.value()
        )

    def _health_check():
        now = now_fn("UTC")
        poll_delay = (now - runner.last_polled).total_seconds()

        if TYPE_CHECKING:
            assert delay_threshold is not None

        if poll_delay > delay_threshold:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"message": "Runner is unresponsive at this time"},
            )
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "OK"})

    return _health_check


def run_count(runner: "Runner") -> Callable[..., int]:
    def _run_count() -> int:
        run_count = len(runner._flow_run_process_map)  # pyright: ignore[reportPrivateUsage]
        return run_count

    return _run_count


def shutdown(runner: "Runner") -> Callable[..., JSONResponse]:
    def _shutdown():
        runner.stop()
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "OK"})

    return _shutdown


async def build_server(runner: "Runner") -> FastAPI:
    """
    Build a FastAPI server for a runner.

    Args:
        runner: the runner this server interacts with and monitors
    """
    webserver = FastAPI()
    router = APIRouter()

    router.add_api_route(
        "/health", perform_health_check(runner=runner), methods=["GET"]
    )
    router.add_api_route("/run_count", run_count(runner=runner), methods=["GET"])
    router.add_api_route("/shutdown", shutdown(runner=runner), methods=["POST"])
    webserver.include_router(router)

    return webserver


def start_webserver(runner: "Runner", log_level: str | None = None) -> None:
    """
    Run a FastAPI server for a runner.

    Args:
        runner: the runner this server interacts with and monitors
        log_level: the log level to use for the server
    """
    host = PREFECT_RUNNER_SERVER_HOST.value()
    port = PREFECT_RUNNER_SERVER_PORT.value()
    log_level = log_level or PREFECT_RUNNER_SERVER_LOG_LEVEL.value()
    webserver = run_coro_as_sync(build_server(runner))
    if TYPE_CHECKING:
        assert webserver is not None, "webserver should be built"
        assert log_level is not None, "log_level should be set"

    uvicorn.run(
        webserver, host=host, port=port, log_level=log_level.lower()
    )  # Uvicorn supports only lowercase log_level
