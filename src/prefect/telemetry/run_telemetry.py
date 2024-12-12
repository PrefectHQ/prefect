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
from prefect.context import FlowRunContext
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
        parent_labels: Optional[dict[str, Any]] = None,
    ):
        should_set_traceparent = self._should_set_traceparent(run)
        traceparent, span = self._start_span(run, name, parameters, parent_labels)

        if should_set_traceparent and traceparent:
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
        parent_labels: Optional[dict[str, Any]] = None,
    ):
        should_set_traceparent = self._should_set_traceparent(run)
        traceparent, span = self._start_span(run, name, parameters, parent_labels)

        if should_set_traceparent and traceparent:
            client.update_flow_run_labels(run.id, {LABELS_TRACEPARENT_KEY: traceparent})

        return span

    def _start_span(
        self,
        run: FlowOrTaskRun,
        name: Optional[str] = None,
        parameters: Optional[dict[str, Any]] = None,
        parent_labels: Optional[dict[str, Any]] = None,
    ) -> tuple[Optional[str], Span]:
        """
        Start a span for a task run.
        """
        if parameters is None:
            parameters = {}
        if parent_labels is None:
            parent_labels = {}
        parameter_attributes = {
            f"prefect.run.parameter.{k}": type(v).__name__
            for k, v in parameters.items()
        }

        traceparent, context = self._traceparent_and_context_from_labels(
            {**parent_labels, **run.labels}
        )
        run_type = self._run_type(run)

        self.span = self._tracer.start_span(
            name=name or run.name,
            context=context,
            attributes={
                f"prefect.{run_type}.name": name or run.name,
                "prefect.run.type": run_type,
                "prefect.run.id": str(run.id),
                "prefect.tags": run.tags,
                **parameter_attributes,
                **parent_labels,
            },
        )

        if not traceparent:
            traceparent = self._traceparent_from_span(self.span)

        if traceparent and LABELS_TRACEPARENT_KEY not in run.labels:
            run.labels[LABELS_TRACEPARENT_KEY] = traceparent

        return traceparent, self.span

    def _run_type(self, run: FlowOrTaskRun) -> str:
        return "task" if isinstance(run, TaskRun) else "flow"

    def _should_set_traceparent(self, run: FlowOrTaskRun) -> bool:
        # If the run is a flow run and it doesn't already have a traceparent,
        # we need to update its labels with the traceparent so that its
        # propagated to child runs. Task runs are updated via events so we
        # don't need to update them via the client in the same way.
        return (
            LABELS_TRACEPARENT_KEY not in run.labels and self._run_type(run) == "flow"
        )

    def _traceparent_and_context_from_labels(
        self, labels: Optional[KeyValueLabels]
    ) -> tuple[Optional[str], Optional[Context]]:
        """Get trace context from run labels if it exists."""
        if not labels or LABELS_TRACEPARENT_KEY not in labels:
            return None, None
        traceparent = labels[LABELS_TRACEPARENT_KEY]
        carrier = {TRACEPARENT_KEY: traceparent}
        return str(traceparent), propagate.extract(carrier)

    def _traceparent_from_span(self, span: Span) -> Optional[str]:
        carrier = {}
        propagate.inject(carrier, context=trace.set_span_in_context(span))
        return carrier.get(TRACEPARENT_KEY)

    def end_span_on_success(self) -> None:
        """
        End a span for a task run on success.
        """
        if self.span:
            self.span.set_status(Status(StatusCode.OK))
            self.span.end(time.time_ns())
            self.span = None

    def end_span_on_failure(self, terminal_message: Optional[str] = None) -> None:
        """
        End a span for a task run on failure.
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
        Update a span with the state of a task run.
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

    def propagate_traceparent(self) -> Optional[KeyValueLabels]:
        """
        Propagate a traceparent to a span.
        """
        parent_flow_run_ctx = FlowRunContext.get()

        if parent_flow_run_ctx and parent_flow_run_ctx.flow_run:
            if traceparent := parent_flow_run_ctx.flow_run.labels.get(
                LABELS_TRACEPARENT_KEY
            ):
                carrier: KeyValueLabels = {TRACEPARENT_KEY: traceparent}
                propagate.get_global_textmap().inject(
                    carrier={TRACEPARENT_KEY: traceparent},
                    setter=OTELSetter(),
                )
                return carrier
            else:
                if self.span:
                    carrier: KeyValueLabels = {}
                    propagate.get_global_textmap().inject(
                        carrier,
                        context=trace.set_span_in_context(self.span),
                        setter=OTELSetter(),
                    )
                    return carrier
