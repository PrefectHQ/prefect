from datetime import datetime
from typing import TYPE_CHECKING, Any, Iterable, Optional, Union
from uuid import UUID

import anyio
from opentelemetry import trace

import prefect
from prefect._result_records import ResultRecordMetadata
from prefect.client.schemas import FlowRun
from prefect.client.utilities import inject_client
from prefect.context import FlowRunContext, TaskRunContext
from prefect.logging import get_logger
from prefect.states import Pending, Scheduled
from prefect.tasks import Task
from prefect.telemetry.run_telemetry import LABELS_TRACEPARENT_KEY, RunTelemetry
from prefect.types._datetime import now
from prefect.utilities.asyncutils import sync_compatible
from prefect.utilities.slugify import slugify


def _is_instrumentation_enabled() -> bool:
    try:
        from opentelemetry.instrumentation.utils import is_instrumentation_enabled

        return is_instrumentation_enabled()
    except (ImportError, ModuleNotFoundError):
        return False


if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient
    from prefect.client.schemas.objects import FlowRun

prefect.client.schemas.StateCreate.model_rebuild(
    _types_namespace={
        "ResultRecordMetadata": ResultRecordMetadata,
    }
)


if TYPE_CHECKING:
    import logging

logger: "logging.Logger" = get_logger(__name__)


@sync_compatible
@inject_client
async def run_deployment(
    name: Union[str, UUID],
    client: Optional["PrefectClient"] = None,
    parameters: Optional[dict[str, Any]] = None,
    scheduled_time: Optional[datetime] = None,
    flow_run_name: Optional[str] = None,
    timeout: Optional[float] = None,
    poll_interval: Optional[float] = 5,
    tags: Optional[Iterable[str]] = None,
    idempotency_key: Optional[str] = None,
    work_queue_name: Optional[str] = None,
    as_subflow: Optional[bool] = True,
    job_variables: Optional[dict[str, Any]] = None,
) -> "FlowRun":
    """
    Create a flow run for a deployment and return it after completion or a timeout.

    By default, this function blocks until the flow run finishes executing.
    Specify a timeout (in seconds) to wait for the flow run to execute before
    returning flow run metadata. To return immediately, without waiting for the
    flow run to execute, set `timeout=0`.

    Note that if you specify a timeout, this function will return the flow run
    metadata whether or not the flow run finished executing.

    If called within a flow or task, the flow run this function creates will
    be linked to the current flow run as a subflow. Disable this behavior by
    passing `as_subflow=False`.

    Args:
        name: The deployment id or deployment name in the form:
            `"flow name/deployment name"`
        parameters: Parameter overrides for this flow run. Merged with the deployment
            defaults.
        scheduled_time: The time to schedule the flow run for, defaults to scheduling
            the flow run to start now.
        flow_run_name: A name for the created flow run
        timeout: The amount of time to wait (in seconds) for the flow run to
            complete before returning. Setting `timeout` to 0 will return the flow
            run metadata immediately. Setting `timeout` to None will allow this
            function to poll indefinitely. Defaults to None.
        poll_interval: The number of seconds between polls
        tags: A list of tags to associate with this flow run; tags can be used in
            automations and for organizational purposes.
        idempotency_key: A unique value to recognize retries of the same run, and
            prevent creating multiple flow runs.
        work_queue_name: The name of a work queue to use for this run. Defaults to
            the default work queue for the deployment.
        as_subflow: Whether to link the flow run as a subflow of the current
            flow or task run.
        job_variables: A dictionary of dot delimited infrastructure overrides that
            will be applied at runtime; for example `env.CONFIG_KEY=config_value` or
            `namespace='prefect'`
    """
    if timeout is not None and timeout < 0:
        raise ValueError("`timeout` cannot be negative")

    if scheduled_time is None:
        scheduled_time = now("UTC")

    parameters = parameters or {}

    deployment_id = None

    if isinstance(name, UUID):
        deployment_id = name
    else:
        try:
            deployment_id = UUID(name)
        except ValueError:
            pass

    if deployment_id:
        deployment = await client.read_deployment(deployment_id=deployment_id)
    else:
        deployment = await client.read_deployment_by_name(name)

    flow_run_ctx = FlowRunContext.get()
    task_run_ctx = TaskRunContext.get()
    if as_subflow and (flow_run_ctx or task_run_ctx):
        # TODO: this logic can likely be simplified by using `Task.create_run`
        from prefect.utilities._engine import dynamic_key_for_task_run
        from prefect.utilities.engine import collect_task_run_inputs

        # This was called from a flow. Link the flow run as a subflow.
        task_inputs = {
            k: await collect_task_run_inputs(v) for k, v in parameters.items()
        }

        if deployment_id:
            flow = await client.read_flow(deployment.flow_id)
            deployment_name = f"{flow.name}/{deployment.name}"
        else:
            deployment_name = name

        # Generate a task in the parent flow run to represent the result of the subflow
        dummy_task = Task(
            name=deployment_name,
            fn=lambda: None,
            version=deployment.version,
        )
        # Override the default task key to include the deployment name
        dummy_task.task_key = f"{__name__}.run_deployment.{slugify(deployment_name)}"
        flow_run_id = (
            flow_run_ctx.flow_run.id
            if flow_run_ctx
            else task_run_ctx.task_run.flow_run_id
        )
        dynamic_key = (
            dynamic_key_for_task_run(flow_run_ctx, dummy_task)
            if flow_run_ctx
            else task_run_ctx.task_run.dynamic_key
        )
        parent_task_run = await client.create_task_run(
            task=dummy_task,
            flow_run_id=flow_run_id,
            dynamic_key=dynamic_key,
            task_inputs=task_inputs,
            state=Pending(),
        )
        parent_task_run_id = parent_task_run.id
    else:
        parent_task_run_id = None

    if flow_run_ctx and flow_run_ctx.flow_run:
        traceparent = flow_run_ctx.flow_run.labels.get(LABELS_TRACEPARENT_KEY)
    elif _is_instrumentation_enabled():
        traceparent = RunTelemetry.traceparent_from_span(span=trace.get_current_span())
    else:
        traceparent = None

    trace_labels = {LABELS_TRACEPARENT_KEY: traceparent} if traceparent else {}

    flow_run = await client.create_flow_run_from_deployment(
        deployment.id,
        parameters=parameters,
        state=Scheduled(scheduled_time=scheduled_time),
        name=flow_run_name,
        tags=tags,
        idempotency_key=idempotency_key,
        parent_task_run_id=parent_task_run_id,
        work_queue_name=work_queue_name,
        job_variables=job_variables,
        labels=trace_labels,
    )

    flow_run_id = flow_run.id

    if timeout == 0:
        return flow_run

    with anyio.move_on_after(timeout):
        while True:
            flow_run = await client.read_flow_run(flow_run_id)
            flow_state = flow_run.state
            if flow_state and flow_state.is_final():
                return flow_run
            await anyio.sleep(poll_interval)

    return flow_run
