from __future__ import annotations

import abc
import textwrap
from datetime import timedelta
from enum import Enum
from typing import (
    Annotated,
    Any,
    Dict,
    List,
    Literal,
    Optional,
    Set,
    Union,
    cast,
)
from uuid import UUID

from pydantic import (
    Discriminator,
    Field,
    PrivateAttr,
    Tag,
    field_validator,
    model_validator,
)
from typing_extensions import Self, TypeAlias

from prefect._internal.schemas.bases import PrefectBaseModel
from prefect.events.actions import ActionTypes, RunDeployment
from prefect.utilities.collections import AutoEnum

from .events import ResourceSpecification


class Posture(AutoEnum):
    Reactive = "Reactive"
    Proactive = "Proactive"
    Metric = "Metric"


class Trigger(PrefectBaseModel, abc.ABC, extra="ignore"):  # type: ignore[call-arg]
    """
    Base class describing a set of criteria that must be satisfied in order to trigger
    an automation.
    """

    type: str

    @abc.abstractmethod
    def describe_for_cli(self, indent: int = 0) -> str:
        """Return a human-readable description of this trigger for the CLI"""

    # The following allows the regular Trigger class to be used when serving or
    # deploying flows, analogous to how the Deployment*Trigger classes work

    _deployment_id: Optional[UUID] = PrivateAttr(default=None)

    def set_deployment_id(self, deployment_id: UUID) -> None:
        self._deployment_id = deployment_id

    def owner_resource(self) -> Optional[str]:
        return f"prefect.deployment.{self._deployment_id}"

    def actions(self) -> List[ActionTypes]:
        assert self._deployment_id
        return [
            RunDeployment(
                source="selected",
                deployment_id=self._deployment_id,
                parameters=getattr(self, "parameters", None),
                job_variables=getattr(self, "job_variables", None),
                schedule_after=getattr(self, "schedule_after", timedelta(0)),
            )
        ]

    def as_automation(self) -> "AutomationCore":
        assert self._deployment_id

        trigger: TriggerTypes = cast(TriggerTypes, self)

        # This is one of the Deployment*Trigger classes, so translate it over to a
        # plain Trigger
        if hasattr(self, "trigger_type"):
            trigger = self.trigger_type(**self.model_dump())

        return AutomationCore(
            name=(
                getattr(self, "name", None)
                or f"Automation for deployment {self._deployment_id}"
            ),
            description=getattr(self, "description", ""),
            enabled=getattr(self, "enabled", True),
            trigger=trigger,
            actions=self.actions(),
            owner_resource=self.owner_resource(),
        )


class ResourceTrigger(Trigger, abc.ABC):
    """
    Base class for triggers that may filter by the labels of resources.
    """

    type: str

    match: ResourceSpecification = Field(
        default_factory=lambda: ResourceSpecification.model_validate({}),
        description="Labels for resources which this trigger will match.",
    )
    match_related: Union[ResourceSpecification, list[ResourceSpecification]] = Field(
        default_factory=lambda: ResourceSpecification.model_validate({}),
        description="Labels for related resources which this trigger will match.",
    )


class EventTrigger(ResourceTrigger):
    """
    A trigger that fires based on the presence or absence of events within a given
    period of time.
    """

    type: Literal["event"] = "event"

    after: Set[str] = Field(
        default_factory=set,
        description=(
            "The event(s) which must first been seen to fire this trigger.  If "
            "empty, then fire this trigger immediately.  Events may include "
            "trailing wildcards, like `prefect.flow-run.*`"
        ),
    )
    expect: Set[str] = Field(
        default_factory=set,
        description=(
            "The event(s) this trigger is expecting to see.  If empty, this "
            "trigger will match any event.  Events may include trailing wildcards, "
            "like `prefect.flow-run.*`"
        ),
    )

    for_each: Set[str] = Field(
        default_factory=set,
        description=(
            "Evaluate the trigger separately for each distinct value of these labels "
            "on the resource.  By default, labels refer to the primary resource of the "
            "triggering event.  You may also refer to labels from related "
            "resources by specifying `related:<role>:<label>`.  This will use the "
            "value of that label for the first related resource in that role.  For "
            'example, `"for_each": ["related:flow:prefect.resource.id"]` would '
            "evaluate the trigger for each flow."
        ),
    )
    posture: Literal[Posture.Reactive, Posture.Proactive] = Field(  # type: ignore[valid-type]
        default=Posture.Reactive,
        description=(
            "The posture of this trigger, either Reactive or Proactive.  Reactive "
            "triggers respond to the _presence_ of the expected events, while "
            "Proactive triggers respond to the _absence_ of those expected events."
        ),
    )
    threshold: int = Field(
        default=1,
        description=(
            "The number of events required for this trigger to fire (for "
            "Reactive triggers), or the number of events expected (for Proactive "
            "triggers)"
        ),
    )
    within: timedelta = Field(
        default=timedelta(seconds=0),
        ge=timedelta(seconds=0),
        description=(
            "The time period over which the events must occur.  For Reactive triggers, "
            "this may be as low as 0 seconds, but must be at least 10 seconds for "
            "Proactive triggers"
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def enforce_minimum_within_for_proactive_triggers(
        cls, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return data

        if "within" in data and data["within"] is None:
            raise ValueError("`within` should be a valid timedelta")

        posture: Optional[Posture] = data.get("posture")
        within: Optional[timedelta] = data.get("within")

        if isinstance(within, (int, float)):
            within = timedelta(seconds=within)

        if posture == Posture.Proactive:
            if not within or within == timedelta(0):
                within = timedelta(seconds=10.0)
            elif within < timedelta(seconds=10.0):
                raise ValueError(
                    "`within` for Proactive triggers must be greater than or equal to "
                    "10 seconds"
                )

        if within:
            data = {**data, "within": within}
        return data

    def describe_for_cli(self, indent: int = 0) -> str:
        """Return a human-readable description of this trigger for the CLI"""
        if self.posture == Posture.Reactive:
            return textwrap.indent(
                "\n".join(
                    [
                        f"Reactive: expecting {self.threshold} of {self.expect}",
                    ],
                ),
                prefix="  " * indent,
            )
        else:
            return textwrap.indent(
                "\n".join(
                    [
                        f"Proactive: expecting {self.threshold} {self.expect} event "
                        f"within {self.within}",
                    ],
                ),
                prefix="  " * indent,
            )


class MetricTriggerOperator(Enum):
    LT = "<"
    LTE = "<="
    GT = ">"
    GTE = ">="


class PrefectMetric(Enum):
    lateness = "lateness"
    duration = "duration"
    successes = "successes"


class MetricTriggerQuery(PrefectBaseModel):
    """Defines a subset of the Trigger subclass, which is specific
    to Metric automations, that specify the query configurations
    and breaching conditions for the Automation"""

    name: PrefectMetric = Field(
        ...,
        description="The name of the metric to query.",
    )
    threshold: float = Field(
        ...,
        description=(
            "The threshold value against which we'll compare the query result."
        ),
    )
    operator: MetricTriggerOperator = Field(
        ...,
        description=(
            "The comparative operator (LT / LTE / GT / GTE) used to compare "
            "the query result against the threshold value."
        ),
    )
    range: timedelta = Field(
        timedelta(seconds=300),  # defaults to 5 minutes
        description=(
            "The lookback duration (seconds) for a metric query. This duration is "
            "used to determine the time range over which the query will be executed. "
            "The minimum value is 300 seconds (5 minutes)."
        ),
    )
    firing_for: timedelta = Field(
        timedelta(seconds=300),  # defaults to 5 minutes
        description=(
            "The duration (seconds) for which the metric query must breach "
            "or resolve continuously before the state is updated and the "
            "automation is triggered. "
            "The minimum value is 300 seconds (5 minutes)."
        ),
    )

    @field_validator("range", "firing_for")
    def enforce_minimum_range(cls, value: timedelta) -> timedelta:
        if value < timedelta(seconds=300):
            raise ValueError("The minimum range is 300 seconds (5 minutes)")
        return value


class MetricTrigger(ResourceTrigger):
    """
    A trigger that fires based on the results of a metric query.
    """

    type: Literal["metric"] = "metric"

    posture: Literal[Posture.Metric] = Field(  # type: ignore[valid-type]
        Posture.Metric,
        description="Periodically evaluate the configured metric query.",
    )

    metric: MetricTriggerQuery = Field(
        ...,
        description="The metric query to evaluate for this trigger. ",
    )

    def describe_for_cli(self, indent: int = 0) -> str:
        """Return a human-readable description of this trigger for the CLI"""
        m = self.metric
        return textwrap.indent(
            "\n".join(
                [
                    f"Metric: {m.name.value} {m.operator.value} {m.threshold} for {m.range}",
                ]
            ),
            prefix="  " * indent,
        )


class CompositeTrigger(Trigger, abc.ABC):
    """
    Requires some number of triggers to have fired within the given time period.
    """

    type: Literal["compound", "sequence"]
    triggers: List["TriggerTypes"]
    within: Optional[timedelta] = Field(
        None,
        description=(
            "The time period over which the events must occur.  For Reactive triggers, "
            "this may be as low as 0 seconds, but must be at least 10 seconds for "
            "Proactive triggers"
        ),
    )


class CompoundTrigger(CompositeTrigger):
    """A composite trigger that requires some number of triggers to have
    fired within the given time period"""

    type: Literal["compound"] = "compound"
    require: Union[int, Literal["any", "all"]]

    @model_validator(mode="after")
    def validate_require(self) -> Self:
        if isinstance(self.require, int):
            if self.require < 1:
                raise ValueError("require must be at least 1")
            if self.require > len(self.triggers):
                raise ValueError(
                    "require must be less than or equal to the number of triggers"
                )

        return self

    def describe_for_cli(self, indent: int = 0) -> str:
        """Return a human-readable description of this trigger for the CLI"""
        return textwrap.indent(
            "\n".join(
                [
                    f"{str(self.require).capitalize()} of:",
                    "\n".join(
                        [
                            trigger.describe_for_cli(indent=indent + 1)
                            for trigger in self.triggers
                        ]
                    ),
                ]
            ),
            prefix="  " * indent,
        )


class SequenceTrigger(CompositeTrigger):
    """A composite trigger that requires some number of triggers to have fired
    within the given time period in a specific order"""

    type: Literal["sequence"] = "sequence"

    def describe_for_cli(self, indent: int = 0) -> str:
        """Return a human-readable description of this trigger for the CLI"""
        return textwrap.indent(
            "\n".join(
                [
                    "In this order:",
                    "\n".join(
                        [
                            trigger.describe_for_cli(indent=indent + 1)
                            for trigger in self.triggers
                        ]
                    ),
                ]
            ),
            prefix="  " * indent,
        )


def trigger_discriminator(value: Any) -> str:
    """Discriminator for triggers that defaults to 'event' if no type is specified."""
    if isinstance(value, dict):
        # Check for explicit type first
        if "type" in value:
            return value["type"]
        # Check for compound/sequence specific fields
        if "triggers" in value and "require" in value:
            return "compound"
        if "triggers" in value and "require" not in value:
            return "sequence"
        # Check for metric-specific posture
        if value.get("posture") == "Metric":
            return "metric"
        # Default to event
        return "event"
    return getattr(value, "type", "event")


TriggerTypes: TypeAlias = Annotated[
    Union[
        Annotated[EventTrigger, Tag("event")],
        Annotated[MetricTrigger, Tag("metric")],
        Annotated[CompoundTrigger, Tag("compound")],
        Annotated[SequenceTrigger, Tag("sequence")],
    ],
    Discriminator(trigger_discriminator),
]
"""The union of all concrete trigger types that a user may actually create"""

CompoundTrigger.model_rebuild()
SequenceTrigger.model_rebuild()


class AutomationCore(PrefectBaseModel, extra="ignore"):  # type: ignore[call-arg]
    """Defines an action a user wants to take when a certain number of events
    do or don't happen to the matching resources"""

    name: str = Field(default=..., description="The name of this automation")
    description: str = Field(
        default="", description="A longer description of this automation"
    )

    enabled: bool = Field(
        default=True, description="Whether this automation will be evaluated"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="A list of tags associated with this automation",
    )

    trigger: TriggerTypes = Field(
        default=...,
        description=(
            "The criteria for which events this Automation covers and how it will "
            "respond to the presence or absence of those events"
        ),
    )

    actions: List[ActionTypes] = Field(
        default=...,
        description="The actions to perform when this Automation triggers",
    )

    actions_on_trigger: List[ActionTypes] = Field(
        default_factory=list,
        description="The actions to perform when an Automation goes into a triggered state",
    )

    actions_on_resolve: List[ActionTypes] = Field(
        default_factory=list,
        description="The actions to perform when an Automation goes into a resolving state",
    )

    owner_resource: Optional[str] = Field(
        default=None, description="The owning resource of this automation"
    )


class Automation(AutomationCore):
    id: UUID = Field(default=..., description="The ID of this automation")
