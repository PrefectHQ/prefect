import typing as t

import pendulum
import uvicorn
from prefect._vendor.fastapi import APIRouter, FastAPI, HTTPException, status
from prefect._vendor.fastapi.openapi.utils import get_openapi
from prefect._vendor.fastapi.responses import JSONResponse

from prefect.client.orchestration import get_client
from prefect.settings import (
    PREFECT_RUNNER_POLL_FREQUENCY,
    PREFECT_RUNNER_SERVER_HOST,
    PREFECT_RUNNER_SERVER_LOG_LEVEL,
    PREFECT_RUNNER_SERVER_MISSED_POLLS_TOLERANCE,
    PREFECT_RUNNER_SERVER_PORT,
)
from prefect.utilities.asyncutils import sync_compatible
from prefect.utilities.validation import validate_values_conform_to_schema

if t.TYPE_CHECKING:
    from prefect.deployments import Deployment
    from prefect.runner import Runner


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
    async def _create_flow_run_for_deployment(
        body: t.Dict[t.Any, t.Any]
    ) -> JSONResponse:
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
            await client.create_flow_run_from_deployment(
                deployment_id=deployment.id, parameters=body
            )
        return JSONResponse(
            status_code=status.HTTP_201_CREATED, content={"message": "OK"}
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


def _inject_schemas_into_generated_openapi(
    webserver: FastAPI, schemas: t.Dict[str, t.Any]
) -> t.Dict[str, t.Any]:
    openapi_schema = get_openapi(
        title="FastAPI Prefect Runner", version="2.5.0", routes=webserver.routes
    )

    # Update the components/schemas with definitions from the deployment schemas
    _merge_definitions_into_components(schemas, openapi_schema)

    # Update the paths with correct references based on the components
    _update_paths_with_correct_refs(openapi_schema)

    return openapi_schema


def _merge_definitions_into_components(
    input_schemas: t.Dict[str, t.Any], openapi_schema: t.Dict[str, t.Any]
) -> None:
    components_schemas = openapi_schema.setdefault("components", {}).setdefault(
        "schemas", {}
    )
    for schema in input_schemas.values():
        if "definitions" in schema:
            for def_name, def_value in schema["definitions"].items():
                # Recursively update all $ref in the schema definition
                _recursively_update_refs(def_value, "#/components/schemas/")
                components_schemas[def_name] = def_value


def _recursively_update_refs(item: t.Any, new_ref_base: str) -> None:
    if isinstance(item, dict):
        if "$ref" in item:
            item["$ref"] = item["$ref"].replace("#/definitions/", new_ref_base)
        for value in item.values():
            _recursively_update_refs(value, new_ref_base)
    elif isinstance(item, list):
        for i in item:
            _recursively_update_refs(i, new_ref_base)


def _update_paths_with_correct_refs(openapi_schema: t.Dict[str, t.Any]) -> None:
    for path_item in openapi_schema.get("paths", {}).values():
        for method in path_item.values():
            if "requestBody" in method:
                content = (
                    method["requestBody"].get("content", {}).get("application/json", {})
                )
                if "schema" in content:
                    _recursively_update_refs(content["schema"], "#/components/schemas/")


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
