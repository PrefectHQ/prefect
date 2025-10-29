from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Coroutine, Hashable, Optional

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from typing_extensions import Literal

from prefect._internal.schemas.validators import validate_values_conform_to_schema
from prefect.client.orchestration import get_client
from prefect.flows import Flow
from prefect.logging import get_logger
from prefect.settings import (
    PREFECT_RUNNER_POLL_FREQUENCY,
    PREFECT_RUNNER_SERVER_MISSED_POLLS_TOLERANCE,
)
from prefect.types._datetime import now as now_fn
from prefect.utilities.importtools import load_script_as_module

if TYPE_CHECKING:
    import logging

    from prefect.client.schemas.responses import DeploymentResponse
    from prefect.runner import Runner


logger: "logging.Logger" = get_logger("runner.webserver")

RunnableEndpoint = Literal["deployment", "flow", "task"]


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
