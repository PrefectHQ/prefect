import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Optional

from opentelemetry.propagators.textmap import Setter
from opentelemetry.trace import (
    Status,
    StatusCode,
    get_tracer,
)

import prefect
from prefect.client.schemas import TaskRun
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
    _span = None

    def start_span(
        self,
        task_run: TaskRun,
        parameters: Optional[Dict[str, Any]] = None,
        labels: Optional[Dict[str, Any]] = None,
    ):
        """
        Start a span for a task run.
        """
        if parameters is None:
            parameters = {}
        if labels is None:
            labels = {}
        parameter_attributes = {
            f"prefect.run.parameter.{k}": type(v).__name__
            for k, v in parameters.items()
        }
        self._span = self._tracer.start_span(
            name=task_run.name,
            attributes={
                "prefect.run.type": "task",
                "prefect.run.id": str(task_run.id),
                "prefect.tags": task_run.tags,
                **parameter_attributes,
                **labels,
            },
        )

    def end_span_on_success(self, terminal_message: str) -> None:
        """
        End a span for a task run on success.
        """
        if self._span:
            self._span.set_status(Status(StatusCode.OK), terminal_message)
            self._span.end(time.time_ns())
            self._span = None

    def end_span_on_failure(self, terminal_message: str) -> None:
        """
        End a span for a task run on failure.
        """
        if self._span:
            self._span.set_status(Status(StatusCode.ERROR, terminal_message))
            self._span.end(time.time_ns())
            self._span = None

    def record_exception(self, exc: Exception) -> None:
        """
        Record an exception on a span.
        """
        if self._span:
            self._span.record_exception(exc)

    def update_state(self, new_state: State) -> None:
        """
        Update a span with the state of a task run.
        """
        if self._span:
            self._span.add_event(
                new_state.name or new_state.type,
                {
                    "prefect.state.message": new_state.message or "",
                    "prefect.state.type": new_state.type,
                    "prefect.state.name": new_state.name or new_state.type,
                    "prefect.state.id": str(new_state.id),
                },
            )
