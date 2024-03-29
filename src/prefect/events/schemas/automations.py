import abc
from datetime import timedelta
from enum import Enum
from typing import (
    Any,
    Dict,
    List,
    Literal,
    Optional,
    Set,
    Union,
)
from uuid import UUID

from typing_extensions import TypeAlias

from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect._internal.schemas.validators import validate_trigger_within

if HAS_PYDANTIC_V2:
    from pydantic.v1 import Field, root_validator, validator
    from pydantic.v1.fields import ModelField
else:
    from pydantic import Field, root_validator, validator
    from pydantic.fields import ModelField

from prefect._internal.schemas.bases import PrefectBaseModel
from prefect.events.actions import ActionTypes
from prefect.utilities.collections import AutoEnum

from .events import ResourceSpecification


class Posture(AutoEnum):
    Reactive = "Reactive"
    Proactive = "Proactive"
    Metric = "Metric"


class Trigger(PrefectBaseModel, abc.ABC, extra="ignore"):
    """
    Base class describing a set of criteria that must be satisfied in order to trigger
    an automation.
    """

    type: str


class ResourceTrigger(Trigger, abc.ABC):
    """
    Base class for triggers that may filter by the labels of resources.
    """

    type: str

    match: ResourceSpecification = Field(
        default_factory=lambda: ResourceSpecification(__root__={}),
        description="Labels for resources which this trigger will match.",
    )
    match_related: ResourceSpecification = Field(
        default_factory=lambda: ResourceSpecification(__root__={}),
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
        ...,
        description=(
            "The posture of this trigger, either Reactive or Proactive.  Reactive "
            "triggers respond to the _presence_ of the expected events, while "
            "Proactive triggers respond to the _absence_ of those expected events."
        ),
    )
    threshold: int = Field(
        1,
        description=(
            "The number of events required for this trigger to fire (for "
            "Reactive triggers), or the number of events expected (for Proactive "
            "triggers)"
        ),
    )
    within: timedelta = Field(
        timedelta(0),
        minimum=0.0,
        exclusiveMinimum=False,
        description=(
            "The time period over which the events must occur.  For Reactive triggers, "
            "this may be as low as 0 seconds, but must be at least 10 seconds for "
            "Proactive triggers"
        ),
    )

    @validator("within")
    def enforce_minimum_within(
        cls, value: timedelta, values, config, field: ModelField
    ):
        return validate_trigger_within(value, field)

    @root_validator(skip_on_failure=True)
    def enforce_minimum_within_for_proactive_triggers(cls, values: Dict[str, Any]):
        posture: Optional[Posture] = values.get("posture")
        within: Optional[timedelta] = values.get("within")

        if posture == Posture.Proactive:
            if not within or within == timedelta(0):
                values["within"] = timedelta(seconds=10.0)
            elif within < timedelta(seconds=10.0):
                raise ValueError(
                    "The minimum within for Proactive triggers is 10 seconds"
                )

        return values


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
            "The threshold value against which we'll compare " "the query result."
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
        minimum=300.0,
        exclusiveMinimum=False,
        description=(
            "The lookback duration (seconds) for a metric query. This duration is "
            "used to determine the time range over which the query will be executed. "
            "The minimum value is 300 seconds (5 minutes)."
        ),
    )
    firing_for: timedelta = Field(
        timedelta(seconds=300),  # defaults to 5 minutes
        minimum=300.0,
        exclusiveMinimum=False,
        description=(
            "The duration (seconds) for which the metric query must breach "
            "or resolve continuously before the state is updated and the "
            "automation is triggered. "
            "The minimum value is 300 seconds (5 minutes)."
        ),
    )


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


class CompositeTrigger(Trigger, abc.ABC):
    """
    Requires some number of triggers to have fired within the given time period.
    """

    type: Literal["compound", "sequence"]
    triggers: List["TriggerTypes"]
    within: Optional[timedelta]


class CompoundTrigger(CompositeTrigger):
    """A composite trigger that requires some number of triggers to have
    fired within the given time period"""

    type: Literal["compound"] = "compound"
    require: Union[int, Literal["any", "all"]]

    @root_validator
    def validate_require(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        require = values.get("require")

        if isinstance(require, int):
            if require < 1:
                raise ValueError("required must be at least 1")
            if require > len(values["triggers"]):
                raise ValueError(
                    "required must be less than or equal to the number of triggers"
                )

        return values


class SequenceTrigger(CompositeTrigger):
    """A composite trigger that requires some number of triggers to have fired
    within the given time period in a specific order"""

    type: Literal["sequence"] = "sequence"


TriggerTypes: TypeAlias = Union[
    EventTrigger, MetricTrigger, CompoundTrigger, SequenceTrigger
]
"""The union of all concrete trigger types that a user may actually create"""

CompoundTrigger.update_forward_refs()
SequenceTrigger.update_forward_refs()


class Automation(PrefectBaseModel, extra="ignore"):
    """Defines an action a user wants to take when a certain number of events
    do or don't happen to the matching resources"""

    name: str = Field(..., description="The name of this automation")
    description: str = Field("", description="A longer description of this automation")

    enabled: bool = Field(True, description="Whether this automation will be evaluated")

    trigger: TriggerTypes = Field(
        ...,
        description=(
            "The criteria for which events this Automation covers and how it will "
            "respond to the presence or absence of those events"
        ),
    )

    actions: List[ActionTypes] = Field(
        ...,
        description="The actions to perform when this Automation triggers",
    )
    owner_resource: Optional[str] = Field(
        default=None, description="The owning resource of this automation"
    )


class ExistingAutomation(Automation):
    id: UUID = Field(..., description="The ID of this automation")
