from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Tuple

import httpx
import pendulum
import uvicorn
from prefect._vendor.fastapi import APIRouter, FastAPI, HTTPException, status
from prefect._vendor.fastapi.responses import JSONResponse
from typing_extensions import Literal

from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect.client.orchestration import get_client
from prefect.flows import load_flow_from_entrypoint
from prefect.runner.utils import (
    inject_schemas_into_openapi,
)
from prefect.settings import (
    PREFECT_EXPERIMENTAL_ENABLE_EXTRA_RUNNER_ENDPOINTS,
    PREFECT_RUNNER_POLL_FREQUENCY,
    PREFECT_RUNNER_SERVER_HOST,
    PREFECT_RUNNER_SERVER_LOG_LEVEL,
    PREFECT_RUNNER_SERVER_MISSED_POLLS_TOLERANCE,
    PREFECT_RUNNER_SERVER_PORT,
)
from prefect.utilities.asyncutils import sync_compatible
from prefect.utilities.hashing import hash_objects
from prefect.utilities.validation import validate_values_conform_to_schema

if TYPE_CHECKING:
    from prefect.client.schemas.responses import DeploymentResponse
    from prefect.runner import Runner

if HAS_PYDANTIC_V2:
    from pydantic.v1 import BaseModel
else:
    from pydantic import BaseModel


RunnableEndpoint = Literal["deployment", "flow", "task"]


class RunnerGenericFlowRunRequest(BaseModel):
    entrypoint: str
    parameters: Optional[Dict[str, Any]] = None


def _hash_prefect_callable(prefect_callable: Callable) -> str:
    return hash_objects(prefect_callable.fn.__name__, prefect_callable.fn.__code__)


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


async def _build_endpoint_for_deployment(
    deployment: "DeploymentResponse", runner: "Runner"
) -> Callable:
    async def _create_flow_run_for_deployment(
        body: Optional[Dict[Any, Any]] = None
    ) -> JSONResponse:
        body = body or {}
        if deployment.enforce_parameter_schema and deployment.parameter_openapi_schema:
            try:
                validate_values_conform_to_schema(
                    body, deployment.parameter_openapi_schema
                )
            except ValueError as exc:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail=f"Error creating flow run: {exc}",
                )

        async with get_client() as client:
            flow_run = await client.create_flow_run_from_deployment(
                deployment_id=deployment.id, parameters=body
            )
        runner.execute_in_background(runner.execute_flow_run, flow_run.id)

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={"flow_run_id": str(flow_run.id)},
        )

    return _create_flow_run_for_deployment


async def get_deployment_router(
    runner: "Runner",
) -> Tuple[APIRouter, Dict[str, Dict]]:
    from prefect import get_client

    router = APIRouter()
    schemas = {}
    async with get_client() as client:
        for deployment_id in runner._deployment_ids:
            deployment = await client.read_deployment(deployment_id)
            router.add_api_route(
                f"/deployment/{deployment.id}/run",
                await _build_endpoint_for_deployment(deployment, runner),
                methods=["POST"],
                name=f"Create flow run for deployment {deployment.name}",
                description=(
                    "Trigger a flow run for a deployment as a background task on the"
                    " runner."
                ),
                summary=f"Run {deployment.name}",
            )

            # Used for updating the route schemas later on
            schemas[f"{deployment.name}-{deployment_id}"] = (
                deployment.parameter_openapi_schema
            )
            schemas[deployment_id] = deployment.name
    return router, schemas


def _build_generic_endpoint_for_flows(runner: "Runner") -> Callable:
    async def _create_flow_run_for_flow_from_fqn(
        body: RunnerGenericFlowRunRequest,
    ) -> JSONResponse:
        flow = load_flow_from_entrypoint(body.entrypoint)

        async with get_client() as client:
            flow_run = await client.create_flow_run(
                flow=flow, parameters=body.parameters
            )

        runner.execute_in_background(
            runner.execute_flow_run, flow_run.id, body.entrypoint
        )

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={"flow_run_id": str(flow_run.id)},
        )

    return _create_flow_run_for_flow_from_fqn


@sync_compatible
async def build_server(runner: "Runner") -> FastAPI:
    """
    Build a FastAPI server for a runner.

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

    if PREFECT_EXPERIMENTAL_ENABLE_EXTRA_RUNNER_ENDPOINTS.value():
        deployments_router, deployment_schemas = await get_deployment_router(runner)
        webserver.include_router(deployments_router)
        webserver.add_api_route(
            "/flow/run",
            _build_generic_endpoint_for_flows(runner=runner),
            methods=["POST"],
            name="Run flow in background",
            description="Trigger any flow run as a background task on the runner.",
            summary="Run flow",
        )

        def customize_openapi():
            if webserver.openapi_schema:
                return webserver.openapi_schema

            openapi_schema = inject_schemas_into_openapi(webserver, deployment_schemas)
            webserver.openapi_schema = openapi_schema
            return webserver.openapi_schema

        webserver.openapi = customize_openapi

    return webserver


def start_webserver(runner: "Runner", log_level: Optional[str] = None) -> None:
    """
    Run a FastAPI server for a runner.

    Args:
        runner (Runner): the runner this server interacts with and monitors
        log_level (str): the log level to use for the server
    """
    host = PREFECT_RUNNER_SERVER_HOST.value()
    port = PREFECT_RUNNER_SERVER_PORT.value()
    log_level = log_level or PREFECT_RUNNER_SERVER_LOG_LEVEL.value()
    webserver = build_server(runner)
    uvicorn.run(webserver, host=host, port=port, log_level=log_level)


@sync_compatible
async def submit_to_runner(
    prefect_callable: Callable,
    fn_kwargs: Dict[str, Any],
    # capture_errors: bool = SETTING.value()?
) -> None:
    """
    Run a callable in the background via the runner webserver.

    Args:
        prefect_callable: the callable to run, e.g. a flow or task
        fn_kwargs: the keyword arguments to pass to the callable
    """
    object_type = prefect_callable.__class__.__name__.lower()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            (
                f"http://{PREFECT_RUNNER_SERVER_HOST.value()}"
                f":{PREFECT_RUNNER_SERVER_PORT.value()}"
                f"/{object_type}/run"
            ),
            json={
                "entrypoint": prefect_callable._entrypoint,
                "parameters": fn_kwargs,
            },
        )
        response.raise_for_status()
