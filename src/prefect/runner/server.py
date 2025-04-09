from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Coroutine, Hashable, Optional

import uvicorn
from fastapi import APIRouter, FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from typing_extensions import Literal

from prefect._internal.compatibility.deprecated import deprecated_callable
from prefect._internal.schemas.validators import validate_values_conform_to_schema
from prefect.client.orchestration import get_client
from prefect.exceptions import MissingFlowError, ScriptError
from prefect.flows import Flow, load_flow_from_entrypoint
from prefect.logging import get_logger
from prefect.runner.utils import (
    inject_schemas_into_openapi,
)
from prefect.settings import (
    PREFECT_RUNNER_POLL_FREQUENCY,
    PREFECT_RUNNER_SERVER_HOST,
    PREFECT_RUNNER_SERVER_LOG_LEVEL,
    PREFECT_RUNNER_SERVER_MISSED_POLLS_TOLERANCE,
    PREFECT_RUNNER_SERVER_PORT,
)
from prefect.types._datetime import now as now_fn
from prefect.utilities.asyncutils import run_coro_as_sync
from prefect.utilities.importtools import load_script_as_module

if TYPE_CHECKING:
    import logging

    from prefect.client.schemas.responses import DeploymentResponse
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


async def _build_endpoint_for_deployment(
    deployment: "DeploymentResponse", runner: "Runner"
) -> Callable[..., Coroutine[Any, Any, JSONResponse]]:
    async def _create_flow_run_for_deployment(
        body: Optional[dict[Any, Any]] = None,
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
            logger.info(
                f"Created flow run {flow_run.name!r} from deployment"
                f" {deployment.name!r}"
            )
        runner.execute_in_background(runner.execute_flow_run, flow_run.id)
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={"flow_run_id": str(flow_run.id)},
        )

    return _create_flow_run_for_deployment


async def get_deployment_router(
    runner: "Runner",
) -> tuple[APIRouter, dict[Hashable, Any]]:
    router = APIRouter()
    schemas: dict[Hashable, Any] = {}
    async with get_client() as client:
        for deployment_id in runner._deployment_ids:  # pyright: ignore[reportPrivateUsage]
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


async def get_subflow_schemas(runner: "Runner") -> dict[str, dict[str, Any]]:
    """
    Load available subflow schemas by filtering for only those subflows in the
    deployment entrypoint's import space.
    """
    schemas: dict[str, dict[str, Any]] = {}
    async with get_client() as client:
        for deployment_id in runner._deployment_ids:  # pyright: ignore[reportPrivateUsage]
            deployment = await client.read_deployment(deployment_id)
            if deployment.entrypoint is None:
                continue

            script = deployment.entrypoint.split(":")[0]
            module = load_script_as_module(script)
            subflows: list[Flow[Any, Any]] = [
                obj for obj in module.__dict__.values() if isinstance(obj, Flow)
            ]
            for flow in subflows:
                schemas[flow.name] = flow.parameters.model_dump()

    return schemas


def _flow_in_schemas(flow: Flow[Any, Any], schemas: dict[str, dict[str, Any]]) -> bool:
    """
    Check if a flow is in the schemas dict, either by name or by name with
    dashes replaced with underscores.
    """
    flow_name_with_dashes = flow.name.replace("_", "-")
    return flow.name in schemas or flow_name_with_dashes in schemas


def _flow_schema_changed(
    flow: Flow[Any, Any], schemas: dict[str, dict[str, Any]]
) -> bool:
    """
    Check if a flow's schemas have changed, either by bame of by name with
    dashes replaced with underscores.
    """
    flow_name_with_dashes = flow.name.replace("_", "-")

    schema = schemas.get(flow.name, None) or schemas.get(flow_name_with_dashes, None)
    if schema is not None and flow.parameters.model_dump() != schema:
        return True
    return False


def _build_generic_endpoint_for_flows(
    runner: "Runner", schemas: dict[str, dict[str, Any]]
) -> Callable[..., Coroutine[Any, Any, JSONResponse]]:
    async def _create_flow_run_for_flow_from_fqn(
        body: RunnerGenericFlowRunRequest,
    ) -> JSONResponse:
        if not runner.has_slots_available():
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"message": "Runner has no available slots"},
            )

        try:
            flow = load_flow_from_entrypoint(body.entrypoint)
        except (FileNotFoundError, MissingFlowError, ScriptError, ModuleNotFoundError):
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"message": "Flow not found"},
            )

        # Verify that the flow we're loading is a subflow this runner is
        # managing
        if not _flow_in_schemas(flow, schemas):
            logger.warning(
                f"Flow {flow.name} is not directly managed by the runner. Please "
                "include it in the runner's served flows' import namespace."
            )
        # Verify that the flow we're loading hasn't changed since the webserver
        # was started
        if _flow_schema_changed(flow, schemas):
            logger.warning(
                "A change in flow parameters has been detected. Please "
                "restart the runner."
            )

        async with get_client() as client:
            flow_run = await client.create_flow_run(
                flow=flow,
                parameters=body.parameters,
                parent_task_run_id=body.parent_task_run_id,
            )
            logger.info(f"Created flow run {flow_run.name!r} from flow {flow.name!r}")
        runner.execute_in_background(
            runner.execute_flow_run, flow_run.id, body.entrypoint
        )

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content=flow_run.model_dump(mode="json"),
        )

    return _create_flow_run_for_flow_from_fqn


@deprecated_callable(
    start_date=datetime(2025, 4, 1),
    end_date=datetime(2025, 10, 1),
    help="Use background tasks (https://docs.prefect.io/v3/develop/deferred-tasks) or `run_deployment` and `.serve` instead of submitting runs to the Runner webserver.",
)
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

    deployments_router, deployment_schemas = await get_deployment_router(runner)
    webserver.include_router(deployments_router)

    subflow_schemas = await get_subflow_schemas(runner)
    webserver.add_api_route(
        "/flow/run",
        _build_generic_endpoint_for_flows(runner=runner, schemas=subflow_schemas),
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


@deprecated_callable(
    start_date=datetime(2025, 4, 1),
    end_date=datetime(2025, 10, 1),
    help="Use background tasks (https://docs.prefect.io/v3/develop/deferred-tasks) or `run_deployment` and `.serve` instead of submitting runs to the Runner webserver.",
)
def start_webserver(runner: "Runner", log_level: str | None = None) -> None:
    """
    Run a FastAPI server for a runner.

    Args:
        runner (Runner): the runner this server interacts with and monitors
        log_level (str): the log level to use for the server
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
