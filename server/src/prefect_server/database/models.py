# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import datetime
from typing import Any, Dict, List

import pendulum
import pydantic
from prefect_server import config
from prefect_server.database.orm import HasuraModel, UUIDString

import prefect


class Flow(HasuraModel):
    __hasura_type__ = "flow"

    id: UUIDString = None
    created: datetime.datetime = None
    updated: datetime.datetime = None
    archived: bool = None
    version: int = None
    version_group_id: str = None
    core_version: str = None
    name: str = None
    description: str = None
    serialized_flow: Dict[str, Any] = None
    environment: Dict[str, Any] = None
    storage: Dict[str, Any] = None
    parameters: List[Dict[str, Any]] = None
    settings: Dict[str, Any] = None

    # relationships
    tasks: List["Task"] = None
    edges: List["Edge"] = None
    flow_runs: List["FlowRun"] = None
    versions: List["Flow"] = None
    schedules: List["Schedule"] = None


class Task(HasuraModel):
    __hasura_type__ = "task"

    id: UUIDString = None
    created: datetime.datetime = None
    updated: datetime.datetime = None
    flow_id: UUIDString = None
    name: str = None
    slug: str = None
    description: str = None
    type: str = None
    max_retries: int = None
    retry_delay: datetime.timedelta = None
    trigger: str = None
    tags: List[str] = None
    mapped: bool = None
    auto_generated: bool = None
    cache_key: str = None
    is_root_task: bool = None
    is_terminal_task: bool = None
    is_reference_task: bool = None


class Edge(HasuraModel):
    __hasura_type__ = "edge"

    id: UUIDString = None
    created: datetime.datetime = None
    updated: datetime.datetime = None
    flow_id: UUIDString = None
    upstream_task_id: UUIDString = None
    downstream_task_id: UUIDString = None
    key: str = None
    mapped: bool = None


class FlowRun(HasuraModel):
    __hasura_type__ = "flow_run"

    id: UUIDString = None
    created: datetime.datetime = None
    updated: datetime.datetime = None
    flow_id: UUIDString = None
    parameters: Dict[str, Any] = None
    context: Dict[str, Any] = None
    version: int = None
    heartbeat: datetime.datetime = None
    scheduled_start_time: datetime.datetime = None
    start_time: datetime.datetime = None
    end_time: datetime.datetime = None
    duration: datetime.timedelta = None
    auto_scheduled: bool = None
    name: str = None
    times_resurrected: int = None
    state_id: str = None

    # state fields
    state: str = None
    state_timestamp: datetime.datetime = None
    state_message: str = None
    state_result: Any = None
    state_start_time: datetime.datetime = None
    serialized_state: Dict[str, Any] = None

    # relationships
    flow: Flow = None
    states: List["FlowRunState"] = None
    task_runs: List["TaskRun"] = None
    logs: List["Log"] = None


class TaskRun(HasuraModel):
    __hasura_type__ = "task_run"

    id: UUIDString = None
    created: datetime.datetime = None
    updated: datetime.datetime = None
    flow_run_id: UUIDString = None
    task_id: UUIDString = None
    map_index: int = None
    version: int = None
    heartbeat: datetime.datetime = None
    start_time: datetime.datetime = None
    end_time: datetime.datetime = None
    duration: datetime.timedelta = None
    run_count: int = None
    cache_key: str = None
    state_id: str = None

    # state fields
    state: str = None
    state_timestamp: datetime.datetime = None
    state_message: str = None
    state_result: Any = None
    state_start_time: datetime.datetime = None
    serialized_state: Dict[str, Any] = None

    # relationships
    flow_run: FlowRun = None
    task: Task = None
    states: List["TaskRunState"] = None
    logs: List["Log"] = None


class FlowRunState(HasuraModel):
    __hasura_type__ = "flow_run_state"

    id: UUIDString = None
    created: datetime.datetime = None
    updated: datetime.datetime = None
    flow_run_id: UUIDString = None
    timestamp: datetime.datetime = None
    message: str = None
    result: str = None
    start_time: datetime.datetime = None
    state: str = None
    version: int = None
    serialized_state: Dict[str, Any] = None

    # relationships
    flow_run: FlowRun = None

    @staticmethod
    def fields_from_state(state: prefect.engine.state.State, timestamp=None):
        """
        Returns a dict that contains fields that could be inferred from a state object
        """
        if timestamp is None:
            timestamp = pendulum.now("utc")

        # update all state columns
        return dict(
            state=type(state).__name__,
            timestamp=timestamp,
            message=state.message,
            result=state.result,
            start_time=getattr(state, "start_time", None),
            serialized_state=state.serialize(),
        )


class TaskRunState(HasuraModel):
    __hasura_type__ = "task_run_state"

    id: UUIDString = None
    created: datetime.datetime = None
    updated: datetime.datetime = None
    task_run_id: UUIDString = None
    timestamp: datetime.datetime = None
    message: str = None
    result: str = None
    start_time: datetime.datetime = None
    state: str = None
    version: int = None
    serialized_state: Dict[str, Any] = None

    # relationships
    task_run: TaskRun = None

    @staticmethod
    def fields_from_state(state: prefect.engine.state.State, timestamp=None):
        """
        Returns a dict that contains fields that could be inferred from a state object
        """
        if timestamp is None:
            timestamp = pendulum.now("utc")

        # update all state columns
        return dict(
            state=type(state).__name__,
            timestamp=timestamp,
            message=state.message,
            result=state.result,
            start_time=getattr(state, "start_time", None),
            serialized_state=state.serialize(),
        )


class Schedule(HasuraModel):
    __hasura_type__ = "schedule"

    id: UUIDString = None
    created: datetime.datetime = None
    updated: datetime.datetime = None
    flow_id: UUIDString = None
    schedule_start: datetime.datetime = None
    schedule_end: datetime.datetime = None
    last_checked: datetime.datetime = None
    last_scheduled_run_time: datetime.datetime = None
    schedule: Dict[str, Any] = None
    active: bool = None

    flow: Flow = None


class Log(HasuraModel):
    __hasura_type__ = "log"

    id: UUIDString = None
    created: datetime.datetime = None
    updated: datetime.datetime = None
    flow_run_id: UUIDString = None
    task_run_id: UUIDString = None
    timestamp: datetime.datetime = None
    name: str = None
    level: str = None
    message: str = None
    info: Dict[str, Any] = None


class ResourcePool(HasuraModel):
    __hasura_type__ = "resource_pool"

    id: UUIDString = None
    created: datetime.datetime = None
    updated: datetime.datetime = None
    name: str = None
    description: str = None
    slots: int = None


# process forward references for all Pydantic models (meaning string class names)
for obj in list(locals().values()):
    if isinstance(obj, type) and issubclass(obj, pydantic.BaseModel):
        obj.update_forward_refs()
