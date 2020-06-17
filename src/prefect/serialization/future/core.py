import datetime
import json
from typing import Any, Callable, Dict, List, Union

from pydantic import Field

import prefect
from prefect.utilities.serialization_future import (
    FunctionReference,
    PolymorphicSerializable,
    Serializable,
)


class Environment(Serializable):
    class Config:
        extra = "allow"

    # for ALL environments
    labels: List[str] = Field(default_factory=list)

    # DaskKubernetes
    docker_secret: str = None
    private_registry: bool = None
    min_workers: int = None
    max_workers: int = None

    # Remote
    executor: str = None
    executor_kwargs: Dict[str, Any] = None

    # RemoteDaskEnvironment
    address: str = None

    @classmethod
    def from_environment(cls, obj: prefect.environments.Environment) -> "Environment":
        return super()._from_object(obj)


class Storage(PolymorphicSerializable):
    class Config:
        extra = "allow"

    # for ALL storage
    flows: Dict[str, str]
    secrets: List[str] = None
    prefect_version: str = None

    # Azure
    container: str = None
    blob_name: str = None

    # Docker
    registry_url: str = None
    image_name: str = None
    image_tag: str = None

    # Local
    directory: str = None

    # GCS / S3
    bucket: str = None
    key: str = None

    # GCS
    project: str = None

    # S3
    client_options: Dict[str, Any] = None

    @classmethod
    def from_storage(cls, obj: prefect.environments.storage.Storage) -> "Storage":
        return super()._from_object(obj)


class Clock(PolymorphicSerializable):
    # all clocks
    start_date: datetime.datetime = None
    end_date: datetime.datetime = None
    parameter_defaults: Dict[str, Any] = None

    # IntervalClock
    interval: datetime.timedelta = None

    # CronClock
    cron: str = None

    # DatesClock
    dates: List[datetime.datetime] = None

    @classmethod
    def from_clock(cls, clock: prefect.schedules.clocks.Clock) -> "Clock":
        return super()._from_object(clock)

    def to_clock(self) -> prefect.schedules.clocks.Clock:
        return super()._to_object()


ScheduleFunctions = List[Union[Callable[[datetime.datetime], bool], Serializable]]


class Schedule(Serializable):
    clocks: List[Clock]
    filters: ScheduleFunctions = Field(default_factory=list)
    or_filters: ScheduleFunctions = Field(default_factory=list)
    not_filters: ScheduleFunctions = Field(default_factory=list)
    adjustments: ScheduleFunctions = Field(default_factory=list)

    @classmethod
    def from_schedule(cls, schedule: prefect.schedules.Schedule) -> "Schedule":
        return super()._from_object(
            schedule, clocks=[Clock.from_clock(c) for c in schedule.clocks]
        )

    def to_schedule(self) -> prefect.schedules.Schedule:
        return super()._to_object()


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


class Result(Serializable):
    class Config:
        extra = "allow"

    # for ALL results
    location: str = None

    # for SafeResults
    value: Union[List, Dict, float, bool, int, str] = None

    # Azure
    container: str = None

    # GCS, S3
    bucket: str = None

    # Local
    dir: str = None

    # Secret
    secret_type: Callable = None

    @classmethod
    def from_result(cls, obj: prefect.engine.result.base.Result) -> "Result":
        return super()._from_object(obj)


class State(PolymorphicSerializable):

    # for ALL states
    message: str = None
    result: Result = None
    context: Dict[str, Any] = Field(default_factory=dict)
    cached_inputs: Dict[str, Any] = Field(default_factory=dict)

    # for SCHEDULED states
    start_time: datetime.datetime = None

    # for METASTATE states
    state: "State" = None

    # for RETRYING states
    run_count: int = None

    # for LOOPED states
    loop_count: int = None

    # for CACHED states
    cached_parameters: Dict[str, Any] = None
    cached_result_expiration: datetime.datetime = None

    @classmethod
    def from_state(cls, state: prefect.engine.state.State) -> "State":
        return super()._from_object(obj=state, result=Result.from_result(state._result))

    def to_state(self):
        return super()._to_object()


State.update_forward_refs()
