import json
import datetime
from pydantic import Field
from typing import Dict, List, Any, Callable
import prefect
from prefect.utilities.serialization_future import (
    Serializable,
    FunctionReference,
)
from prefect.serialization.future.environments import Environment, Storage
from prefect.serialization.future.schedules import Schedule


class Edge(Serializable):
    upstream_task_slug: str
    downstream_task_slug: str
    key: str = None
    mapped: bool = False

    @classmethod
    def from_edge(cls, edge: prefect.core.edge.Edge) -> "Edge":
        return super()._from_object(
            edge,
            upstream_task_slug=edge.upstream_task.slug,
            downstream_task_slug=edge.downstream_task.slug,
            key=edge.key,
            mapped=edge.mapped,
        )


class Task(Serializable):
    slug: str
    name: str = None
    tags: List[str] = Field(default_factory=list)
    max_retries: int
    retry_delay: datetime.timedelta = None
    timeout: int = None
    trigger: FunctionReference
    skip_on_upstream_skip: bool
    cache_for: datetime.timedelta = None
    cache_key: str = None
    cache_validator: FunctionReference = None
    auto_generated: bool = False
    is_mapped: bool = False
    is_reference_task: bool = False
    is_root_task: bool = False
    is_terminal_task: bool = False

    @classmethod
    def from_task(
        cls,
        task: prefect.core.task.Task,
        is_mapped: bool = False,
        is_reference_task: bool = False,
        is_root_task: bool = False,
        is_terminal_task: bool = False,
    ) -> "Task":
        return super()._from_object(
            task,
            slug=task.slug,
            name=task.name,
            tags=list(sorted(task.tags)),
            max_retries=task.max_retries,
            retry_delay=task.retry_delay,
            timeout=task.timeout,
            trigger=task.trigger,
            skip_on_upstream_skip=task.skip_on_upstream_skip,
            cache_for=task.cache_for,
            cache_key=task.cache_key,
            cache_validator=task.cache_validator,
            auto_generated=task.auto_generated,
            is_mapped=is_mapped,
            is_reference_task=is_reference_task,
            is_root_task=is_root_task,
            is_terminal_task=is_terminal_task,
        )

    def to_task(self) -> prefect.core.Task:
        return prefect.core.Task(
            slug=self.slug,
            name=self.name,
            tags=self.tags,
            max_retries=self.max_retries,
            retry_delay=self.retry_delay,
            timeout=self.timeout,
            trigger=self.trigger,
            skip_on_upstream_skip=self.skip_on_upstream_skip,
            cache_for=self.cache_for,
            cache_key=self.cache_key,
            cache_validator=self.cache_validator if self.cache_for else None,
        )


class Parameter(Serializable):
    slug: str
    name: str
    required: bool
    default: Any

    @classmethod
    def from_parameter(cls, parameter: prefect.core.task.Parameter) -> "Parameter":
        default = parameter.default
        # check if default can be serialized
        try:
            json.dumps(parameter.default)
        except TypeError:
            default = "<Default value could not be serialized>"

        return super()._from_object(
            parameter,
            slug=parameter.slug,
            name=parameter.name,
            default=default,
            required=parameter.required,
        )

    def to_parameter(self) -> prefect.core.Parameter:
        return prefect.core.Parameter(
            name=self.name, required=self.required, default=self.default
        )


class Flow(Serializable):
    name: str
    schedule: Schedule = None
    environment: Environment = None
    storage: Storage = None
    tasks: List[Task] = Field(default_factory=list)
    edges: List[Edge] = Field(default_factory=list)
    parameters: List[Parameter] = Field(default_factory=list)

    @classmethod
    def from_flow(cls, flow: prefect.core.flow.Flow) -> "Flow":
        return super()._from_object(
            flow,
            name=flow.name,
            tasks=[
                Task.from_task(
                    t,
                    is_mapped=any(e.mapped for e in flow.edges_to(t)),
                    is_reference_task=(t in flow.reference_tasks()),
                    is_root_task=(t in flow.root_tasks()),
                    is_terminal_task=(t in flow.terminal_tasks()),
                )
                for t in flow.tasks
                if not isinstance(t, prefect.Parameter)
            ],
            edges=[Edge.from_edge(e) for e in flow.edges],
            environment=Environment.from_environment(flow.environment),
            parameters=[Parameter.from_parameter(p) for p in flow.parameters()],
            schedule=Schedule.from_schedule(flow.schedule),
        )

    def to_flow(self) -> prefect.core.Flow:
        tasks = [t.to_task() for t in self.tasks]
        tasks.extend(p.to_parameter() for p in self.parameters)

        task_lookup = {t.slug: t for t in tasks}
        edges = [
            prefect.core.Edge(
                upstream_task=task_lookup[e.upstream_task_slug],
                downstream_task=task_lookup[e.downstream_task_slug],
                key=e.key,
                mapped=e.mapped,
            )
            for e in self.edges
        ]

        return prefect.core.Flow(
            name=self.name,
            tasks=tasks,
            edges=edges,
            environment=self.environment._to_object() if self.environment else None,
            storage=self.storage._to_object() if self.storage else None,
            schedule=self.schedule._to_object() if self.schedule else None,
        )
