import pendulum
import uvicorn
from fastapi import APIRouter, FastAPI, status
from fastapi.responses import JSONResponse
from functools import partial


def perform_health_check(runner, delay_threshold: int = 15) -> JSONResponse:
    def _health_check():
        now = pendulum.now("utc")
        poll_delay = (now - runner.last_polled).total_seconds()

        if poll_delay > delay_threshold:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"message": "Runner is unresponsive at this time"},
            )
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "OK"})
    return _health_check

def start_webserver(
    runner,
    log_level: str = "error",
) -> None:
    """
    Run a FastAPI server for a runner.

    Args:
        runner (Runner): the runner this server interacts with and monitors
        log_level (str): the log level to use for the server
    """
    webserver = FastAPI()
    router = APIRouter()

    router.add_api_route("/health", perform_health_check(runner=runner), methods=["GET"])

    webserver.include_router(router)

    uvicorn.run(webserver, host="0.0.0.0", port=8080, log_level=log_level)
