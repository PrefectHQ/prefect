import abc
from datetime import timedelta
from enum import Enum
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Literal,
    Optional,
    Set,
    Tuple,
    Union,
    cast,
)
from uuid import UUID, uuid4

import pendulum
from typing_extensions import TypeAlias

from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    from pydantic.v1 import Extra, Field, PrivateAttr, root_validator, validator
    from pydantic.v1.fields import ModelField
else:
    from pydantic import Extra, Field, PrivateAttr, root_validator, validator
    from pydantic.fields import ModelField

from prefect._internal.schemas.bases import PrefectBaseModel
from prefect._internal.schemas.fields import DateTimeTZ
from prefect.events.actions import ActionTypes, RunDeployment
from prefect.utilities.collections import AutoEnum

# These are defined by Prefect Cloud
MAXIMUM_LABELS_PER_RESOURCE = 500
MAXIMUM_RELATED_RESOURCES = 500


class Posture(AutoEnum):
    Reactive = "Reactive"
    Proactive = "Proactive"
    Metric = "Metric"


class ResourceSpecification(PrefectBaseModel):
    __root__: Dict[str, Union[str, List[str]]]


class Labelled(PrefectBaseModel):
    """An object defined by string labels and values"""

    __root__: Dict[str, str]

    def keys(self) -> Iterable[str]:
        return self.__root__.keys()

    def items(self) -> Iterable[Tuple[str, str]]:
        return self.__root__.items()

    def __getitem__(self, label: str) -> str:
        return self.__root__[label]

    def __setitem__(self, label: str, value: str) -> str:
        self.__root__[label] = value
        return value


class Resource(Labelled):
    """An observable business object of interest to the user"""

    @root_validator(pre=True)
    def enforce_maximum_labels(cls, values: Dict[str, Any]):
        labels = values.get("__root__")
        if not isinstance(labels, dict):
            return values

        if len(labels) > MAXIMUM_LABELS_PER_RESOURCE:
            raise ValueError(
                "The maximum number of labels per resource "
                f"is {MAXIMUM_LABELS_PER_RESOURCE}"
            )

        return values

    @root_validator(pre=True)
    def requires_resource_id(cls, values: Dict[str, Any]):
        labels = values.get("__root__")
        if not isinstance(labels, dict):
            return values

        labels = cast(Dict[str, str], labels)

        if "prefect.resource.id" not in labels:
            raise ValueError("Resources must include the prefect.resource.id label")
        if not labels["prefect.resource.id"]:
            raise ValueError("The prefect.resource.id label must be non-empty")

        return values

    @property
    def id(self) -> str:
        return self["prefect.resource.id"]


class RelatedResource(Resource):
    """A Resource with a specific role in an Event"""

    @root_validator(pre=True)
    def requires_resource_role(cls, values: Dict[str, Any]):
        labels = values.get("__root__")
        if not isinstance(labels, dict):
            return values

        labels = cast(Dict[str, str], labels)

        if "prefect.resource.role" not in labels:
            raise ValueError(
                "Related Resources must include the prefect.resource.role label"
            )
        if not labels["prefect.resource.role"]:
            raise ValueError("The prefect.resource.role label must be non-empty")

        return values

    @property
    def role(self) -> str:
        return self["prefect.resource.role"]


class Event(PrefectBaseModel):
    """The client-side view of an event that has happened to a Resource"""

    occurred: DateTimeTZ = Field(
        default_factory=pendulum.now,
        description="When the event happened from the sender's perspective",
    )
    event: str = Field(
        description="The name of the event that happened",
    )
    resource: Resource = Field(
        description="The primary Resource this event concerns",
    )
    related: List[RelatedResource] = Field(
        default_factory=list,
        description="A list of additional Resources involved in this event",
    )
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="An open-ended set of data describing what happened",
    )
    id: UUID = Field(
        default_factory=uuid4,
        description="The client-provided identifier of this event",
    )
    follows: Optional[UUID] = Field(
        None,
        description=(
            "The ID of an event that is known to have occurred prior to this "
            "one. If set, this may be used to establish a more precise "
            "ordering of causally-related events when they occur close enough "
            "together in time that the system may receive them out-of-order."
        ),
    )

    @property
    def involved_resources(self) -> Iterable[Resource]:
        return [self.resource] + list(self.related)

    @validator("related")
    def enforce_maximum_related_resources(cls, value: List[RelatedResource]):
        if len(value) > MAXIMUM_RELATED_RESOURCES:
            raise ValueError(
                "The maximum number of related resources "
                f"is {MAXIMUM_RELATED_RESOURCES}"
            )

        return value


class Trigger(PrefectBaseModel, abc.ABC):
    """
    Base class describing a set of criteria that must be satisfied in order to trigger
    an automation.
    """

    class Config:
        extra = Extra.ignore

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
        minimum = field.field_info.extra["minimum"]
        if value.total_seconds() < minimum:
            raise ValueError("The minimum within is 0 seconds")
        return value

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


class Automation(PrefectBaseModel):
    """Defines an action a user wants to take when a certain number of events
    do or don't happen to the matching resources"""

    class Config:
        extra = Extra.ignore

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


class AutomationCreateFromTrigger(PrefectBaseModel):
    name: Optional[str] = Field(
        None, description="The name to give to the automation created for this trigger."
    )
    description: str = Field("", description="A longer description of this automation")
    enabled: bool = Field(True, description="Whether this automation will be evaluated")

    # from ResourceTrigger

    match: ResourceSpecification = Field(
        default_factory=lambda: ResourceSpecification(__root__={}),
        description="Labels for resources which this trigger will match.",
    )
    match_related: ResourceSpecification = Field(
        default_factory=lambda: ResourceSpecification(__root__={}),
        description="Labels for related resources which this trigger will match.",
    )

    # from both EventTrigger and MetricTrigger

    posture: Posture = Field(
        Posture.Reactive,
        description=(
            "The posture of this trigger, either Reactive, Proactive, or Metric. "
            "Reactive triggers respond to the _presence_ of the expected events, while "
            "Proactive triggers respond to the _absence_ of those expected events.  "
            "Metric triggers periodically evaluate the configured metric query."
        ),
    )

    # from EventTrigger

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

    # from MetricTrigger

    metric: Optional[MetricTriggerQuery] = Field(
        None,
        description="The metric query to evaluate for this trigger. ",
    )

    def as_automation(self) -> Automation:
        assert self.name

        if self.posture == Posture.Metric:
            trigger = MetricTrigger(
                type="metric",
                match=self.match,
                match_related=self.match_related,
                posture=self.posture,
                metric=self.metric,
            )
        else:
            trigger = EventTrigger(
                match=self.match,
                match_related=self.match_related,
                after=self.after,
                expect=self.expect,
                for_each=self.for_each,
                posture=self.posture,
                threshold=self.threshold,
                within=self.within,
            )

        return Automation(
            name=self.name,
            description=self.description,
            enabled=self.enabled,
            trigger=trigger,
            actions=self.actions(),
            owner_resource=self.owner_resource(),
        )

    def owner_resource(self) -> Optional[str]:
        return None

    def actions(self) -> List[ActionTypes]:
        raise NotImplementedError


class DeploymentTrigger(AutomationCreateFromTrigger):
    _deployment_id: Optional[UUID] = PrivateAttr(default=None)
    parameters: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "The parameters to pass to the deployment, or None to use the "
            "deployment's default parameters"
        ),
    )

    def set_deployment_id(self, deployment_id: UUID):
        self._deployment_id = deployment_id

    def owner_resource(self) -> Optional[str]:
        return f"prefect.deployment.{self._deployment_id}"

    def actions(self) -> List[RunDeployment]:
        assert self._deployment_id
        return [
            RunDeployment(
                parameters=self.parameters,
                deployment_id=self._deployment_id,
            )
        ]
