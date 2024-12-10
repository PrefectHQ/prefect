import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Optional, Union

from opentelemetry.propagators.textmap import Setter
from opentelemetry.trace import (
    Span,
    Status,
    StatusCode,
    get_tracer,
)

import prefect
from prefect.client.schemas import FlowRun, TaskRun
from prefect.client.schemas.objects import State
from prefect.types import KeyValueLabels

if TYPE_CHECKING:
    from opentelemetry.trace import Tracer


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

    def start_span(
        self,
        run: Union[TaskRun, FlowRun],
        name: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        parent_labels: Optional[Dict[str, Any]] = None,
    ):
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
        run_type = "task" if isinstance(run, TaskRun) else "flow"

        self.span = self._tracer.start_span(
            name=name or run.name,
            attributes={
                f"prefect.{run_type}.name": name or run.name,
                "prefect.run.type": run_type,
                "prefect.run.id": str(run.id),
                "prefect.tags": run.tags,
                **parameter_attributes,
                **parent_labels,
            },
        )
        return self.span

    def end_span_on_success(self, terminal_message: str) -> None:
        """
        End a span for a task run on success.
        """
        if self.span:
            self.span.set_status(Status(StatusCode.OK), terminal_message)
            self.span.end(time.time_ns())
            self.span = None

    def end_span_on_failure(self, terminal_message: str) -> None:
        """
        End a span for a task run on failure.
        """
        if self.span:
            self.span.set_status(Status(StatusCode.ERROR, terminal_message))
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
