from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from prefect._experimental.sla.objects import SlaTypes
from prefect.client.schemas.actions import DeploymentScheduleCreate
from prefect.client.schemas.schedules import SCHEDULE_TYPES


class WorkPoolConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = None
    work_queue_name: Optional[str] = None
    job_variables: Dict[str, Any] = Field(default_factory=dict)


class DeploymentConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # base metadata
    name: Optional[str] = None
    version: Optional[str] = None
    version_type: Optional[str] = None
    tags: Optional[Union[str, list[Any]]] = (
        None  # allow raw templated string or list; templating will normalize
    )
    description: Optional[str] = None

    # schedule metadata
    schedule: Optional["ScheduleItem"] = None
    schedules: Optional[List["ScheduleItem"]] = None
    paused: Optional[bool] = None
    concurrency_limit: Optional[Union[int, "ConcurrencyLimitSpec"]] = None

    # flow-specific
    flow_name: Optional[str] = None
    entrypoint: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    enforce_parameter_schema: Optional[bool] = None

    # per-deployment actions (optional overrides)
    # Accept list, mapping (empty or step), or null for flexibility
    build: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None
    push: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None
    pull: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None

    # infra-specific
    work_pool: Optional[WorkPoolConfig] = None

    # automations metadata
    # Triggers are stored as raw dicts to allow Jinja templating (e.g., enabled: "{{ prefect.variables.is_prod }}")
    # Strict validation happens later in _initialize_deployment_triggers after template resolution
    triggers: Optional[List[Dict[str, Any]]] = None
    sla: Optional[List[SlaTypes]] = None


class PrefectYamlModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    # generic metadata (currently unused by CLI but allowed)
    prefect_version: Optional[str] = Field(default=None, alias="prefect-version")
    name: Optional[str] = None

    # global actions
    build: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None
    push: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None
    pull: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None

    # deployments
    deployments: List[DeploymentConfig] = Field(default_factory=list)

    @staticmethod
    def _validate_action_steps(steps: Optional[List[Dict[str, Any]]]) -> None:
        # Light validation: allow any mapping; prefer single-key style but do not enforce
        if not steps:
            return
        for step in steps:
            if not isinstance(step, dict):
                raise TypeError("Each action step must be a mapping")
            # empty or multi-key steps will be passed through unchanged

    @field_validator("build", "push", "pull")
    @classmethod
    def _validate_actions(cls, v: Optional[List[Dict[str, Any]]]):
        cls._validate_action_steps(v)
        return v

    @field_validator("deployments")
    @classmethod
    def _validate_deployments(cls, v: List[DeploymentConfig]):
        # Ensure deployments is a list
        return v or []


class ConcurrencyLimitSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    limit: Optional[int] = None
    collision_strategy: Optional[str] = None
    grace_period_seconds: Optional[int] = None


class RawScheduleConfig(BaseModel):
    """
    Strongly-typed schedule config that mirrors the CLI's accepted YAML shape.
    Exactly one of cron, interval, or rrule must be provided.
    """

    model_config = ConfigDict(extra="forbid")

    # One-of schedule selectors
    cron: Optional[str] = None
    interval: Optional[timedelta] = (
        None  # accepts int/float (seconds), ISO 8601, HH:MM:SS
    )
    rrule: Optional[str] = None

    # Common extras
    timezone: Optional[str] = None
    anchor_date: Optional[str] = None
    active: Optional[Union[bool, str]] = None  # Allow string for template values
    parameters: Dict[str, Any] = Field(default_factory=dict)
    slug: Optional[str] = None

    # Cron-specific
    day_or: Optional[Union[bool, str]] = None  # Allow string for template values

    @model_validator(mode="after")
    def _one_of_schedule(self):
        provided = [v is not None for v in (self.cron, self.interval, self.rrule)]
        if sum(provided) != 1:
            raise ValueError(
                "Exactly one of 'cron', 'interval', or 'rrule' must be provided"
            )
        return self


ScheduleItem = Union[
    RawScheduleConfig, DeploymentScheduleCreate, SCHEDULE_TYPES, Dict[None, None]
]
