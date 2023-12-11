import typing as t
import uuid

import pendulum
import uvicorn
from prefect._vendor.fastapi import APIRouter, FastAPI, status
from prefect._vendor.fastapi.openapi.utils import get_openapi
from prefect._vendor.fastapi.responses import JSONResponse

from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect.client.orchestration import get_client
from prefect.settings import (
    PREFECT_RUNNER_POLL_FREQUENCY,
    PREFECT_RUNNER_SERVER_HOST,
    PREFECT_RUNNER_SERVER_LOG_LEVEL,
    PREFECT_RUNNER_SERVER_MISSED_POLLS_TOLERANCE,
    PREFECT_RUNNER_SERVER_PORT,
)
from prefect.utilities.asyncutils import sync_compatible

if t.TYPE_CHECKING:
    from prefect.deployments import Deployment
    from prefect.runner import Runner


if HAS_PYDANTIC_V2:
    pass
else:
    pass


def perform_health_check(runner, delay_threshold: int = None) -> JSONResponse:
    if delay_threshold is None:
        delay_threshold = (
            PREFECT_RUNNER_SERVER_MISSED_POLLS_TOLERANCE.value()
            * PREFECT_RUNNER_POLL_FREQUENCY.value()
        )

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


def run_count(runner) -> int:
    def _run_count():
        run_count = len(runner._flow_run_process_map)
        return run_count

    return _run_count


def shutdown(runner) -> int:
    def _shutdown():
        runner.stop()
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "OK"})

    return _shutdown


async def __run_deployment(deployment: "Deployment"):
    async def _create_flow_run_for_deployment(body: t.Dict[t.Any, t.Any]):  # type: ignore
        async with get_client() as client:
            await client.create_flow_run_from_deployment(
                deployment_id=deployment.id, parameters=body
            )

    return _create_flow_run_for_deployment


@sync_compatible
async def get_deployment_router(
    runner: "Runner",
) -> t.Tuple[APIRouter, t.Dict[str, t.Dict]]:
    from prefect import get_client

    router = APIRouter()
    schemas = {}
    async with get_client() as client:
        for deployment_id in runner._deployment_ids:
            deployment = await client.read_deployment(deployment_id)
            router.add_api_route(
                f"/deployment/{deployment.id}/run",
                await __run_deployment(deployment),
                methods=["POST"],
            )

            # Used for updating the route schemas later on
            schemas[deployment.name] = deployment.parameter_openapi_schema
            schemas[deployment.id] = deployment.name
    return router, schemas


def _inject_schemas_into_generated_openapi(webserver: FastAPI, schemas: t.Dict):
    openapi_schema = get_openapi(
        title="FastAPI Prefect Runner", version="2.5.0", routes=webserver.routes
    )

    # Place the deployment schema into the schema references
    for name, schema in schemas.items():
        try:
            if isinstance(name, str):
                uuid.UUID(name)
        except ValueError:
            pass
        else:
            continue

        openapi_schema["components"]["schemas"][name] = schema

    # Update the route schema to reference the deployment schema
    for path, remainder in openapi_schema["paths"].items():
        if not path.startswith("/deployment"):
            continue

        deployment_id = uuid.UUID(path.split("/")[2])
        deployment_name = schemas[deployment_id]
        remainder["post"]["requestBody"] = {
            "content": {
                "application/json": {
                    "schema": {"$ref": f"#/components/schemas/{deployment_name}"}
                }
            }
        }
        if "parameters" in remainder["post"]:
            del remainder["post"]["parameters"]

        openapi_schema["paths"][path] = remainder

        # TODO: Need to add nested schemas somehwhere in components.schemas

    return openapi_schema


def start_webserver(
    runner: "Runner",
    log_level: str = None,
) -> None:
    """
    Run a FastAPI server for a runner.

    Args:
        runner (Runner): the runner this server interacts with and monitors
        log_level (str): the log level to use for the server
    """
    webserver = FastAPI()
    router = APIRouter()

    router.add_api_route(
        "/health", perform_health_check(runner=runner), methods=["GET"]
    )
    router.add_api_route("/run_count", run_count(runner=runner), methods=["GET"])
    router.add_api_route("/shutdown", shutdown(runner=runner), methods=["POST"])
    webserver.include_router(router)

    deployments_router, deployment_schemas = get_deployment_router(runner)
    webserver.include_router(deployments_router)

    host = PREFECT_RUNNER_SERVER_HOST.value()
    port = PREFECT_RUNNER_SERVER_PORT.value()
    log_level = log_level or PREFECT_RUNNER_SERVER_LOG_LEVEL.value()

    def customize_openapi():
        if webserver.openapi_schema:
            return webserver.openapi_schema

        openapi_schema = _inject_schemas_into_generated_openapi(
            webserver, deployment_schemas
        )
        webserver.openapi_schema = openapi_schema
        return webserver.openapi_schema

    webserver.openapi = customize_openapi
    uvicorn.run(webserver, host=host, port=port, log_level=log_level)
