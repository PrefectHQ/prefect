import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional, Union

from opentelemetry import propagate, trace
from opentelemetry.context import Context
from opentelemetry.propagators.textmap import Setter
from opentelemetry.trace import (
    Span,
    Status,
    StatusCode,
    get_tracer,
)
from typing_extensions import TypeAlias

import prefect
from prefect.client.orchestration import PrefectClient, SyncPrefectClient
from prefect.client.schemas import FlowRun, TaskRun
from prefect.client.schemas.objects import State
from prefect.context import FlowRunContext, TaskRunContext
from prefect.types import KeyValueLabels

if TYPE_CHECKING:
    from opentelemetry.trace import Tracer

LABELS_TRACEPARENT_KEY = "__OTEL_TRACEPARENT"
TRACEPARENT_KEY = "traceparent"

FlowOrTaskRun: TypeAlias = Union[FlowRun, TaskRun]


class OTELSetter(Setter[KeyValueLabels]):
    """
    A setter for OpenTelemetry that supports Prefect's custom labels.
    """

    def set(self, carrier: KeyValueLabels, key: str, value: str) -> None:
        carrier[key] = value


@dataclass
class RunTelemetry:
    """
    A class for managing the telemetry of runs.
    """

    _tracer: "Tracer" = field(
        default_factory=lambda: get_tracer("prefect", prefect.__version__)
    )
    span: Optional[Span] = None

    async def async_start_span(
        self,
        run: FlowOrTaskRun,
        client: PrefectClient,
        name: Optional[str] = None,
        parameters: Optional[dict[str, Any]] = None,
    ):
        traceparent, span = self._start_span(run, name, parameters)

        if self._run_type(run) == "flow" and traceparent:
            # Only explicitly update labels if the run is a flow as task runs
            # are updated via events.
            await client.update_flow_run_labels(
                run.id, {LABELS_TRACEPARENT_KEY: traceparent}
            )

        return span

    def start_span(
        self,
        run: FlowOrTaskRun,
        client: SyncPrefectClient,
        name: Optional[str] = None,
        parameters: Optional[dict[str, Any]] = None,
    ):
        traceparent, span = self._start_span(run, name, parameters)

        if self._run_type(run) == "flow" and traceparent:
            # Only explicitly update labels if the run is a flow as task runs
            # are updated via events.
            client.update_flow_run_labels(run.id, {LABELS_TRACEPARENT_KEY: traceparent})

        return span

    def _start_span(
        self,
        run: FlowOrTaskRun,
        name: Optional[str] = None,
        parameters: Optional[dict[str, Any]] = None,
    ) -> tuple[Optional[str], Span]:
        """
        Start a span for a run.
        """
        if parameters is None:
            parameters = {}

        parameter_attributes = {
            f"prefect.run.parameter.{k}": type(v).__name__
            for k, v in parameters.items()
        }

        # Use existing trace context if this run already has one (e.g., from
        # server operations like Late), otherwise use parent's trace context if
        # available (e.g., nested flow / task runs). If neither exists, this
        # will be a root span (e.g., a top-level flow run).
        if LABELS_TRACEPARENT_KEY in run.labels:
            context = self._trace_context_from_labels(run.labels)
        else:
            parent_run = self._parent_run()
            parent_labels = parent_run.labels if parent_run else {}
            if LABELS_TRACEPARENT_KEY in parent_labels:
                context = self._trace_context_from_labels(parent_labels)
            else:
                context = None

        run_type = self._run_type(run)

        self.span = self._tracer.start_span(
            name=name or run.name,
            context=context,
            attributes={
                "prefect.run.name": name or run.name,
                "prefect.run.type": run_type,
                "prefect.run.id": str(run.id),
                "prefect.tags": run.tags,
                **parameter_attributes,
                **{
                    key: value
                    for key, value in run.labels.items()
                    if not key.startswith("__")  # exclude internal labels
                },
            },
        )

        if traceparent := self._traceparent_from_span(self.span):
            run.labels[LABELS_TRACEPARENT_KEY] = traceparent

        return traceparent, self.span

    def _run_type(self, run: FlowOrTaskRun) -> str:
        return "task" if isinstance(run, TaskRun) else "flow"

    def _trace_context_from_labels(
        self, labels: Optional[KeyValueLabels]
    ) -> Optional[Context]:
        """Get trace context from run labels if it exists."""
        if not labels or LABELS_TRACEPARENT_KEY not in labels:
            return None
        traceparent = labels[LABELS_TRACEPARENT_KEY]
        carrier = {TRACEPARENT_KEY: traceparent}
        return propagate.extract(carrier)

    def _traceparent_from_span(self, span: Span) -> Optional[str]:
        carrier: dict[str, Any] = {}
        propagate.inject(carrier, context=trace.set_span_in_context(span))
        return carrier.get(TRACEPARENT_KEY)

    def end_span_on_success(self) -> None:
        """
        End a span for a run on success.
        """
        if self.span:
            self.span.set_status(Status(StatusCode.OK))
            self.span.end(time.time_ns())
            self.span = None

    def end_span_on_failure(self, terminal_message: Optional[str] = None) -> None:
        """
        End a span for a run on failure.
        """
        if self.span:
            self.span.set_status(
                Status(StatusCode.ERROR, terminal_message or "Run failed")
            )
            self.span.end(time.time_ns())
            self.span = None

    def record_exception(self, exc: BaseException) -> None:
        """
        Record an exception on a span.
        """
        if self.span:
            self.span.record_exception(exc)

    def update_state(self, new_state: State) -> None:
        """
        Update a span with the state of a run.
        """
        if self.span:
            self.span.add_event(
                new_state.name or new_state.type,
                {
                    "prefect.state.message": new_state.message or "",
                    "prefect.state.type": new_state.type,
                    "prefect.state.name": new_state.name or new_state.type,
                    "prefect.state.id": str(new_state.id),
                },
            )

    def _parent_run(self) -> Union[FlowOrTaskRun, None]:
        """
        Identify the "parent run" for the current execution context.

        Both flows and tasks can be nested "infinitely," and each creates a
        corresponding context when executed. This method determines the most
        appropriate parent context (either a task run or a flow run) based on
        their relationship in the current hierarchy.

        Returns:
            FlowOrTaskRun: The parent run object (task or flow) if applicable.
            None: If there is no parent context, implying the current run is the top-level parent.
        """
        parent_flow_run_context = FlowRunContext.get()
        parent_task_run_context = TaskRunContext.get()

        if parent_task_run_context and parent_flow_run_context:
            # If both contexts exist, which is common for nested flows or tasks,
            # check if the task's flow_run_id matches the current flow_run.
            # If they match, the task is a child of the flow and is the parent of the current run.
            flow_run_id = getattr(parent_flow_run_context.flow_run, "id", None)
            if parent_task_run_context.task_run.flow_run_id == flow_run_id:
                return parent_task_run_context.task_run
            # Otherwise, assume the flow run is the entry point and is the parent.
            return parent_flow_run_context.flow_run
        elif parent_flow_run_context:
            return parent_flow_run_context.flow_run
        elif parent_task_run_context:
            return parent_task_run_context.task_run

        return None
