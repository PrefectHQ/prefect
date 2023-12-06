import typing as t

import pendulum
import uvicorn
from prefect._vendor.fastapi import APIRouter, FastAPI, status
from prefect._vendor.fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, create_model

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


def create_model_from_openapi(
    schema: dict[str, t.Any], title: str
) -> t.Type[BaseModel]:
    definitions = schema.get("definitions", {})

    def _get_python_type(type_name: str) -> t.Type:
        if type_name == "integer":
            return int
        elif type_name == "number":
            return float
        elif type_name == "boolean":
            return bool
        elif type_name == "string":
            return str
        elif type_name == "array":
            return list
        elif type_name == "object":
            return dict
        else:
            raise ValueError(f"Unknown type '{type_name}'.")

    def resolve_reference(ref: str, definitions: dict[str, t.Any]) -> t.Type[BaseModel]:
        ref_name = ref.lstrip("#/definitions/")
        ref_schema = definitions.get(ref_name)
        if ref_schema is None:
            raise ValueError(f"Reference {ref!r} not found in definitions.")
        return create_model_from_schema(ref_schema, ref_name, definitions)

    def create_model_from_schema(
        schema: dict[str, t.Any], model_name: str, definitions: dict[str, t.Any]
    ) -> t.Type[BaseModel]:
        model_fields = {}

        for prop_name, prop_info in schema.get("properties", {}).items():
            field_details = (
                prop_info.get("allOf")[0] if "allOf" in prop_info else prop_info
            )

            if "$ref" in field_details:
                python_type = resolve_reference(field_details["$ref"], definitions)
            else:
                python_type = (
                    t.Any
                    if "type" not in field_details
                    else _get_python_type(field_details["type"])
                )

            model_fields[prop_name] = (
                (t.Optional[python_type], Field(default=prop_info.get("default", ...)))
                if prop_name not in schema.get("required", [])
                else (python_type, Field(...))
            )

        return create_model(model_name, **model_fields)

    return create_model_from_schema(schema, title, definitions)


async def _make_run_deployment_endpoint(
    deployment: "Deployment",
) -> t.Callable[..., None]:
    title = f"{deployment.name.title().replace('_', '')}Parameters_{deployment.id}"
    Model: t.Type[BaseModel] = create_model_from_openapi(
        deployment.parameter_openapi_schema, title
    )

    Model.__config__.arbitrary_types_allowed = True

    async def _create_flow_run_for_deployment(m: Model):  # type: ignore
        async with get_client() as client:
            await client.create_flow_run_from_deployment(
                deployment_id=deployment.id,
                parameters=m.dict(),
            )

    return _create_flow_run_for_deployment


@sync_compatible
async def get_deployment_router(runner: "Runner") -> APIRouter:
    from prefect import get_client

    router = APIRouter()
    async with get_client() as client:
        for deployment_id in runner._deployment_ids:
            deployment = await client.read_deployment(deployment_id)
            router.add_api_route(
                f"/deployment/{deployment.id}/run",
                await _make_run_deployment_endpoint(deployment),
                methods=["POST"],
            )
    return router


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

    deployments_router = get_deployment_router(runner)
    webserver.include_router(deployments_router)

    host = PREFECT_RUNNER_SERVER_HOST.value()
    port = PREFECT_RUNNER_SERVER_PORT.value()
    log_level = log_level or PREFECT_RUNNER_SERVER_LOG_LEVEL.value()

    uvicorn.run(webserver, host=host, port=port, log_level=log_level)
