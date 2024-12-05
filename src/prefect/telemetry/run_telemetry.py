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
from prefect.client.schemas import FlowRun, TaskRun
from prefect.client.schemas.objects import State
from prefect.types import KeyValueLabels

if TYPE_CHECKING:
    from opentelemetry.trace import Tracer


class OTELSetter(Setter[KeyValueLabels]):
    def set(self, carrier: KeyValueLabels, key: str, value: str) -> None:
        carrier[key] = value


@dataclass
class RunTelemetry:
    _tracer: "Tracer" = field(
        default_factory=lambda: get_tracer("prefect", prefect.__version__)
    )
    _span = None

    def start_span(
        self,
        run: TaskRun | FlowRun,
        name: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        parent_labels: Optional[Dict[str, Any]] = None,
    ):
        if parameters is None:
            parameters = {}
        if parent_labels is None:
            parent_labels = {}
        parameter_attributes = {
            f"prefect.run.parameter.{k}": type(v).__name__
            for k, v in parameters.items()
        }
        run_type = "task" if isinstance(run, TaskRun) else "flow"
        print(f"__________parent_labels: {parent_labels}")
        self._span = self._tracer.start_span(
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
        return self._span

    def end_span_on_success(self, terminal_message: Optional[str] = None):
        if self._span:
            self._span.set_status(Status(StatusCode.OK), terminal_message)
            self._span.end(time.time_ns())
            self._span = None

    def end_span_on_failure(self, terminal_message: Optional[str] = None):
        if self._span:
            self._span.set_status(Status(StatusCode.ERROR, terminal_message))
            self._span.end(time.time_ns())
            self._span = None

    def record_exception(self, exc: BaseException):
        if self._span:
            self._span.record_exception(exc)

    def update_state(self, new_state: State):
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
