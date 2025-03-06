from __future__ import annotations

import abc
import re
import weakref
from datetime import timedelta
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Literal,
    Optional,
    Sequence,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
)
from uuid import UUID, uuid4

from pydantic import (
    Field,
    PrivateAttr,
    field_validator,
    model_validator,
)
from typing_extensions import Self, TypeAlias

from prefect.logging import get_logger
from prefect.server.events.actions import ServerActionTypes
from prefect.server.events.schemas.events import (
    ReceivedEvent,
    RelatedResource,
    Resource,
    ResourceSpecification,
    matches,
)
from prefect.server.schemas.actions import ActionBaseModel
from prefect.server.utilities.schemas import ORMBaseModel, PrefectBaseModel
from prefect.types import DateTime
from prefect.utilities.collections import AutoEnum

if TYPE_CHECKING:
    import logging

logger: "logging.Logger" = get_logger(__name__)


class Posture(AutoEnum):
    Reactive = "Reactive"
    Proactive = "Proactive"
    Metric = "Metric"


class TriggerState(AutoEnum):
    Triggered = "Triggered"
    Resolved = "Resolved"


class Trigger(PrefectBaseModel, abc.ABC):
    """
    Base class describing a set of criteria that must be satisfied in order to trigger
    an automation.
    """

    type: str

    id: UUID = Field(default_factory=uuid4, description="The unique ID of this trigger")

    _automation: Optional[weakref.ref] = PrivateAttr(None)
    _parent: Optional[weakref.ref] = PrivateAttr(None)

    @property
    def automation(self) -> "Automation":
        assert self._automation is not None, "Trigger._automation has not been set"
        value = self._automation()
        assert value is not None, "Trigger._automation has been garbage collected"
        return value

    @property
    def parent(self) -> "Union[Trigger, Automation]":
        assert self._parent is not None, "Trigger._parent has not been set"
        value = self._parent()
        assert value is not None, "Trigger._parent has been garbage collected"
        return value

    def _set_parent(self, value: "Union[Trigger, Automation]"):
        if isinstance(value, Automation):
            self._automation = weakref.ref(value)
            self._parent = self._automation
        elif isinstance(value, Trigger):
            self._parent = weakref.ref(value)
            self._automation = value._automation
        else:  # pragma: no cover
            raise ValueError("parent must be an Automation or a Trigger")

    def reset_ids(self) -> None:
        """Resets the ID of this trigger and all of its children"""
        self.id = uuid4()
        for trigger in self.all_triggers():
            trigger.id = uuid4()

    def all_triggers(self) -> Sequence[Trigger]:
        """Returns all triggers within this trigger"""
        return [self]

    @abc.abstractmethod
    def create_automation_state_change_event(
        self, firing: "Firing", trigger_state: TriggerState
    ) -> ReceivedEvent: ...


class CompositeTrigger(Trigger, abc.ABC):
    """
    Requires some number of triggers to have fired within the given time period.
    """

    type: Literal["compound", "sequence"]
    triggers: List["ServerTriggerTypes"]
    within: Optional[timedelta]

    def create_automation_state_change_event(
        self, firing: Firing, trigger_state: TriggerState
    ) -> ReceivedEvent:
        """Returns a ReceivedEvent for an automation state change
        into a triggered or resolved state."""
        automation = firing.trigger.automation
        triggering_event = firing.triggering_event
        return ReceivedEvent(
            occurred=firing.triggered,
            event=f"prefect.automation.{trigger_state.value.lower()}",
            resource={
                "prefect.resource.id": f"prefect.automation.{automation.id}",
                "prefect.resource.name": automation.name,
            },
            related=(
                [
                    {
                        "prefect.resource.id": f"prefect.event.{triggering_event.id}",
                        "prefect.resource.role": "triggering-event",
                    }
                ]
                if triggering_event
                else []
            ),
            payload={
                "triggering_labels": firing.triggering_labels,
                "triggering_event": (
                    triggering_event.model_dump(mode="json")
                    if triggering_event
                    else None
                ),
            },
            id=uuid4(),
        )

    def _set_parent(self, value: "Union[Trigger , Automation]"):
        super()._set_parent(value)
        for trigger in self.triggers:
            trigger._set_parent(self)

    def all_triggers(self) -> Sequence[Trigger]:
        return [self] + [t for child in self.triggers for t in child.all_triggers()]

    @property
    def child_trigger_ids(self) -> List[UUID]:
        return [trigger.id for trigger in self.triggers]

    @property
    def num_expected_firings(self) -> int:
        return len(self.triggers)

    @abc.abstractmethod
    def ready_to_fire(self, firings: Sequence["Firing"]) -> bool: ...


class CompoundTrigger(CompositeTrigger):
    """A composite trigger that requires some number of triggers to have
    fired within the given time period"""

    type: Literal["compound"] = "compound"
    require: Union[int, Literal["any", "all"]]

    @property
    def num_expected_firings(self) -> int:
        if self.require == "any":
            return 1
        elif self.require == "all":
            return len(self.triggers)
        else:
            return int(self.require)

    def ready_to_fire(self, firings: Sequence["Firing"]) -> bool:
        return len(firings) >= self.num_expected_firings

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


class SequenceTrigger(CompositeTrigger):
    """A composite trigger that requires some number of triggers to have fired
    within the given time period in a specific order"""

    type: Literal["sequence"] = "sequence"

    @property
    def expected_firing_order(self) -> List[UUID]:
        return [trigger.id for trigger in self.triggers]

    def ready_to_fire(self, firings: Sequence["Firing"]) -> bool:
        actual_firing_order = [
            f.trigger.id for f in sorted(firings, key=lambda f: f.triggered)
        ]
        return actual_firing_order == self.expected_firing_order


class ResourceTrigger(Trigger, abc.ABC):
    """
    Base class for triggers that may filter by the labels of resources.
    """

    type: str

    match: ResourceSpecification = Field(
        default_factory=lambda: ResourceSpecification.model_validate({}),
        description="Labels for resources which this trigger will match.",
    )
    match_related: ResourceSpecification = Field(
        default_factory=lambda: ResourceSpecification.model_validate({}),
        description="Labels for related resources which this trigger will match.",
    )

    def covers_resources(
        self, resource: Resource, related: Sequence[RelatedResource]
    ) -> bool:
        if not self.match.includes([resource]):
            return False

        if not self.match_related.includes(related):
            return False

        return True


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
        timedelta(seconds=0),
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
        cls, data: Dict[str, Any] | Any
    ) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return data

        if "within" in data and data["within"] is None:
            raise ValueError("`within` should be a valid timedelta")

        posture: Optional[Posture] = data.get("posture")
        within: Optional[timedelta] = data.get("within")

        if isinstance(within, (int, float)):
            data["within"] = within = timedelta(seconds=within)

        if posture == Posture.Proactive:
            if not within or within == timedelta(0):
                data["within"] = timedelta(seconds=10.0)
            elif within < timedelta(seconds=10.0):
                raise ValueError(
                    "`within` for Proactive triggers must be greater than or equal to "
                    "10 seconds"
                )

        return data

    def covers(self, event: ReceivedEvent) -> bool:
        if not self.covers_resources(event.resource, event.related):
            return False

        if not self.event_pattern.match(event.event):
            return False

        return True

    @property
    def immediate(self) -> bool:
        """Does this reactive trigger fire immediately for all events?"""
        return self.posture == Posture.Reactive and self.within == timedelta(0)

    _event_pattern: Optional[re.Pattern[str]] = PrivateAttr(None)

    @property
    def event_pattern(self) -> re.Pattern[str]:
        """A regular expression which may be evaluated against any event string to
        determine if this trigger would be interested in the event"""
        if self._event_pattern:
            return self._event_pattern

        if not self.expect:
            # This preserves the trivial match for `expect`, and matches the behavior
            # of expects() below
            self._event_pattern = re.compile(".+")
        else:
            patterns = [
                # escape each pattern, then translate wildcards ('*' -> r'.+')
                re.escape(e).replace("\\*", ".+")
                for e in self.expect | self.after
            ]
            self._event_pattern = re.compile("|".join(patterns))

        return self._event_pattern

    def starts_after(self, event: str) -> bool:
        # Warning: Previously we returned 'True' if there was trivial 'after' criteria.
        # Although this is not wrong, it led to automations processing more events
        # than they should have.
        if not self.after:
            return False

        for candidate in self.after:
            if matches(candidate, event):
                return True
        return False

    def expects(self, event: str) -> bool:
        if not self.expect:
            return True

        for candidate in self.expect:
            if matches(candidate, event):
                return True
        return False

    def bucketing_key(self, event: ReceivedEvent) -> Tuple[str, ...]:
        return tuple(
            event.find_resource_label(label) or "" for label in sorted(self.for_each)
        )

    def meets_threshold(self, event_count: int) -> bool:
        if self.posture == Posture.Reactive and event_count >= self.threshold:
            return True

        if self.posture == Posture.Proactive and event_count < self.threshold:
            return True

        return False

    def create_automation_state_change_event(
        self, firing: Firing, trigger_state: TriggerState
    ) -> ReceivedEvent:
        """Returns a ReceivedEvent for an automation state change
        into a triggered or resolved state."""
        automation = firing.trigger.automation
        triggering_event = firing.triggering_event

        resource_data = Resource(
            {
                "prefect.resource.id": f"prefect.automation.{automation.id}",
                "prefect.resource.name": automation.name,
            }
        )

        if self.posture.value:
            resource_data["prefect.posture"] = self.posture.value

        return ReceivedEvent(
            occurred=firing.triggered,
            event=f"prefect.automation.{trigger_state.value.lower()}",
            resource=resource_data,
            related=(
                [
                    RelatedResource(
                        {
                            "prefect.resource.id": f"prefect.event.{triggering_event.id}",
                            "prefect.resource.role": "triggering-event",
                        }
                    )
                ]
                if triggering_event
                else []
            ),
            payload={
                "triggering_labels": firing.triggering_labels,
                "triggering_event": (
                    triggering_event.model_dump(mode="json")
                    if triggering_event
                    else None
                ),
            },
            id=uuid4(),
        )


ServerTriggerTypes: TypeAlias = Union[EventTrigger, CompoundTrigger, SequenceTrigger]
"""The union of all concrete trigger types that a user may actually create"""

T = TypeVar("T", bound=Trigger)


class AutomationCore(PrefectBaseModel, extra="ignore"):
    """Defines an action a user wants to take when a certain number of events
    do or don't happen to the matching resources"""

    name: str = Field(default=..., description="The name of this automation")
    description: str = Field(
        default="", description="A longer description of this automation"
    )

    enabled: bool = Field(
        default=True, description="Whether this automation will be evaluated"
    )

    trigger: ServerTriggerTypes = Field(
        default=...,
        description=(
            "The criteria for which events this Automation covers and how it will "
            "respond to the presence or absence of those events"
        ),
    )

    actions: list[ServerActionTypes] = Field(
        default=...,
        description="The actions to perform when this Automation triggers",
    )

    actions_on_trigger: list[ServerActionTypes] = Field(
        default_factory=list,
        description="The actions to perform when an Automation goes into a triggered state",
    )

    actions_on_resolve: list[ServerActionTypes] = Field(
        default_factory=list,
        description="The actions to perform when an Automation goes into a resolving state",
    )

    def triggers(self) -> Sequence[Trigger]:
        """Returns all triggers within this automation"""
        return self.trigger.all_triggers()

    def triggers_of_type(self, trigger_type: Type[T]) -> Sequence[T]:
        """Returns all triggers of the specified type within this automation"""
        return [t for t in self.triggers() if isinstance(t, trigger_type)]

    def trigger_by_id(self, trigger_id: UUID) -> Optional[Trigger]:
        """Returns the trigger with the given ID, or None if no such trigger exists"""
        for trigger in self.triggers():
            if trigger.id == trigger_id:
                return trigger
        return None

    @model_validator(mode="after")
    def prevent_run_deployment_loops(self) -> Self:
        """Detects potential infinite loops in automations with RunDeployment actions"""
        from prefect.server.events.actions import RunDeployment

        if not self.enabled:
            # Disabled automations can't cause problems
            return self

        if (
            not self.trigger
            or not isinstance(self.trigger, EventTrigger)
            or self.trigger.posture != Posture.Reactive
        ):
            # Only reactive automations can cause infinite amplification
            return self

        if not any(e.startswith("prefect.flow-run.") for e in self.trigger.expect):
            # Only flow run events can cause infinite amplification
            return self

        # Every flow run created by a Deployment goes through these states
        problematic_events = {
            "prefect.flow-run.Scheduled",
            "prefect.flow-run.Pending",
            "prefect.flow-run.Running",
            "prefect.flow-run.*",
        }
        if not problematic_events.intersection(self.trigger.expect):
            return self

        actions = [a for a in self.actions if isinstance(a, RunDeployment)]
        for action in actions:
            if action.source == "inferred":
                # Inferred deployments for flow run state change events will always
                # cause infinite loops, because no matter what filters we place on the
                # flow run, we're inferring the deployment from it, so we'll always
                # produce a new flow run that matches those filters.
                raise ValueError(
                    "Running an inferred deployment from a flow run state change event "
                    "will lead to an infinite loop of flow runs.  Please choose a "
                    "specific deployment and add additional filtering labels to the "
                    "match or match_related for this automation's trigger."
                )

            if action.source == "selected":
                # Selected deployments for flow run state changes can cause infinite
                # loops if there aren't enough filtering labels on the trigger's match
                # or match_related.  While it's still possible to have infinite loops
                # with additional filters, it's less likely.
                if self.trigger.match.matches_every_resource_of_kind(
                    "prefect.flow-run"
                ) and self.trigger.match_related.matches_every_resource_of_kind(
                    "prefect.flow-run"
                ):
                    raise ValueError(
                        "Running a selected deployment from a flow run state change "
                        "event may lead to an infinite loop of flow runs.  Please "
                        "include additional filtering labels on either match or "
                        "match_related to narrow down which flow runs will trigger "
                        "this automation to exclude flow runs from the deployment "
                        "you've selected."
                    )

        return self


class Automation(ORMBaseModel, AutomationCore, extra="ignore"):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.trigger._set_parent(self)

    @classmethod
    def model_validate(
        cls: type[Self],
        obj: Any,
        *,
        strict: bool | None = None,
        from_attributes: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> Self:
        automation = super().model_validate(
            obj, strict=strict, from_attributes=from_attributes, context=context
        )
        automation.trigger._set_parent(automation)
        return automation


class AutomationCreate(AutomationCore, ActionBaseModel, extra="forbid"):
    owner_resource: Optional[str] = Field(
        default=None, description="The resource to which this automation belongs"
    )


class AutomationUpdate(AutomationCore, ActionBaseModel, extra="forbid"):
    pass


class AutomationPartialUpdate(ActionBaseModel, extra="forbid"):
    enabled: bool = Field(True, description="Whether this automation will be evaluated")


class AutomationSort(AutoEnum):
    """Defines automations sorting options."""

    CREATED_DESC = "CREATED_DESC"
    UPDATED_DESC = "UPDATED_DESC"
    NAME_ASC = "NAME_ASC"
    NAME_DESC = "NAME_DESC"


class Firing(PrefectBaseModel):
    """Represents one instance of a trigger firing"""

    id: UUID = Field(default_factory=uuid4)

    trigger: ServerTriggerTypes = Field(
        default=..., description="The trigger that is firing"
    )
    trigger_states: Set[TriggerState] = Field(
        default=...,
        description="The state changes represented by this Firing",
    )
    triggered: DateTime = Field(
        default=...,
        description=(
            "The time at which this trigger fired, which may differ from the "
            "occurred time of the associated event (as events processing may always "
            "be slightly delayed)."
        ),
    )
    triggering_labels: Dict[str, str] = Field(
        default_factory=dict,
        description=(
            "The labels associated with this Firing, derived from the underlying "
            "for_each values of the trigger.  Only used in the context "
            "of EventTriggers."
        ),
    )
    triggering_firings: List[Firing] = Field(
        default_factory=list,
        description=(
            "The firings of the triggers that caused this trigger to fire.  Only used "
            "in the context of CompoundTriggers."
        ),
    )
    triggering_event: Optional[ReceivedEvent] = Field(
        default=None,
        description=(
            "The most recent event associated with this Firing.  This may be the "
            "event that caused the trigger to fire (for Reactive triggers), or the "
            "last event to match the trigger (for Proactive triggers), or the state "
            "change event (for a Metric trigger)."
        ),
    )
    triggering_value: Optional[Any] = Field(
        default=None,
        description=(
            "A value associated with this firing of a trigger.  Maybe used to "
            "convey additional information at the point of firing, like the value of "
            "the last query for a MetricTrigger"
        ),
    )

    @field_validator("trigger_states")
    @classmethod
    def validate_trigger_states(cls, value: set[TriggerState]) -> set[TriggerState]:
        if not value:
            raise ValueError("At least one trigger state must be provided")
        return value

    def all_firings(self) -> Sequence[Firing]:
        return [self] + [
            f for child in self.triggering_firings for f in child.all_firings()
        ]

    def all_events(self) -> Sequence[ReceivedEvent]:
        events = [self.triggering_event] if self.triggering_event else []
        return events + [
            e for child in self.triggering_firings for e in child.all_events()
        ]


class TriggeredAction(PrefectBaseModel):
    """An action caused as the result of an automation"""

    automation: Automation = Field(
        ..., description="The Automation that caused this action"
    )

    id: UUID = Field(
        default_factory=uuid4,
        description="A unique key representing a single triggering of an action",
    )

    firing: Firing = Field(None, description="The Firing that prompted this action")

    triggered: DateTime = Field(..., description="When this action was triggered")
    triggering_labels: Dict[str, str] = Field(
        ...,
        description=(
            "The subset of labels of the Event that triggered this action, "
            "corresponding to the Automation's for_each.  If no for_each is specified, "
            "this will be an empty set of labels"
        ),
    )
    triggering_event: Optional[ReceivedEvent] = Field(
        ...,
        description=(
            "The last Event to trigger this automation, if applicable.  For reactive "
            "triggers, this will be the event that caused the trigger to fire.  For "
            "proactive triggers, this will be the last event to match the automation, "
            "if there was one."
        ),
    )
    action: ServerActionTypes = Field(
        ...,
        description="The action to perform",
    )
    action_index: int = Field(
        0,
        description="The index of the action within the automation",
    )

    def idempotency_key(self) -> str:
        """Produce a human-friendly idempotency key for this action"""
        return ", ".join(
            [
                f"automation {self.automation.id}",
                f"action {self.action_index}",
                f"invocation {self.id}",
            ]
        )

    def all_firings(self) -> Sequence[Firing]:
        return self.firing.all_firings() if self.firing else []

    def all_events(self) -> Sequence[ReceivedEvent]:
        return self.firing.all_events() if self.firing else []


CompoundTrigger.model_rebuild()
SequenceTrigger.model_rebuild()
