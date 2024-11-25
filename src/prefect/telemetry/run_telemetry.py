import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Optional

from opentelemetry.trace import (
    Status,
    StatusCode,
    get_tracer,
)

import prefect
from prefect.client.schemas import TaskRun
from prefect.client.schemas.objects import State

if TYPE_CHECKING:
    from opentelemetry.sdk.trace import Tracer


@dataclass
class RunTelemetry:
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

    def end_span_on_success(self, terminal_message: str):
        if self._span:
            self._span.set_status(Status(StatusCode.OK), terminal_message)
            self._span.end(time.time_ns())
            self._span = None

    def end_span_on_failure(self, terminal_message: str):
        if self._span:
            self._span.set_status(Status(StatusCode.ERROR, terminal_message))
            self._span.end(time.time_ns())
            self._span = None

    def record_exception(self, exc: Exception):
        if self._span:
            self._span.record_exception(exc)

    def update_state(self, new_state: State):
        if self._span:
            self._span.add_event(
                new_state.name,
                {
                    "prefect.state.message": new_state.message or "",
                    "prefect.state.type": new_state.type,
                    "prefect.state.name": new_state.name or new_state.type,
                    "prefect.state.id": str(new_state.id),
                },
            )
