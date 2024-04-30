"""
Schemas for defining triggers within a Prefect deployment YAML.  This is a separate
parallel hierarchy for representing triggers so that they can also include the
information necessary to create an automation.

These triggers should follow the validation rules of the main Trigger class hierarchy as
closely as possible (because otherwise users will get validation errors creating
triggers), but we can be more liberal with the defaults here to make it simpler to
create them from YAML.
"""

import abc
import textwrap
from datetime import timedelta
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Set,
    Union,
)
from uuid import UUID

from typing_extensions import TypeAlias

from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    from pydantic.v1 import Field, PrivateAttr
else:
    from pydantic import Field, PrivateAttr  # type: ignore

from prefect._internal.compatibility.deprecated import deprecated_class
from prefect._internal.schemas.bases import PrefectBaseModel
from prefect.events.actions import ActionTypes, RunDeployment

from .automations import (
    AutomationCore,
    CompoundTrigger,
    EventTrigger,
    MetricTrigger,
    MetricTriggerQuery,
    Posture,
    SequenceTrigger,
    TriggerTypes,
)
from .events import ResourceSpecification


class BaseDeploymentTrigger(PrefectBaseModel, abc.ABC, extra="ignore"):  # type: ignore[call-arg]
    """
    Base class describing a set of criteria that must be satisfied in order to trigger
    an automation.
    """

    # Fields from Automation

    name: Optional[str] = Field(
        None, description="The name to give to the automation created for this trigger."
    )
    description: str = Field("", description="A longer description of this automation")
    enabled: bool = Field(True, description="Whether this automation will be evaluated")

    # Fields from the RunDeployment action

    parameters: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "The parameters to pass to the deployment, or None to use the "
            "deployment's default parameters"
        ),
    )
    job_variables: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Job variables to pass to the deployment, or None to use the "
            "deployment's default job variables"
        ),
    )


class DeploymentEventTrigger(BaseDeploymentTrigger, EventTrigger):
    """
    A trigger that fires based on the presence or absence of events within a given
    period of time.
    """

    trigger_type = EventTrigger


class DeploymentMetricTrigger(BaseDeploymentTrigger, MetricTrigger):
    """
    A trigger that fires based on the results of a metric query.
    """

    trigger_type = MetricTrigger


class DeploymentCompoundTrigger(BaseDeploymentTrigger, CompoundTrigger):
    """A composite trigger that requires some number of triggers to have
    fired within the given time period"""

    trigger_type = CompoundTrigger


class DeploymentSequenceTrigger(BaseDeploymentTrigger, SequenceTrigger):
    """A composite trigger that requires some number of triggers to have fired
    within the given time period in a specific order"""

    trigger_type = SequenceTrigger


# Concrete deployment trigger types
DeploymentTriggerTypes: TypeAlias = Union[
    DeploymentEventTrigger,
    DeploymentMetricTrigger,
    DeploymentCompoundTrigger,
    DeploymentSequenceTrigger,
]


# The deprecated all-in-one DeploymentTrigger


@deprecated_class(
    start_date="Mar 2024",
    help=textwrap.dedent(
        """
    To associate a specific kind of trigger with a Deployment, use one of the more
    specific deployment trigger types instead:

    * DeploymentEventTrigger to associate an EventTrigger with a deployment
    * DeploymentMetricTrigger to associate an MetricTrigger with a deployment
    * DeploymentCompoundTrigger to associate an CompoundTrigger with a deployment
    * DeploymentSequenceTrigger to associate an SequenceTrigger with a deployment

    In other cases, use the Automation and Trigger class hierarchy directly.
    """
    ),
)
class DeploymentTrigger(PrefectBaseModel):
    name: Optional[str] = Field(
        None, description="The name to give to the automation created for this trigger."
    )
    description: str = Field("", description="A longer description of this automation")
    enabled: bool = Field(True, description="Whether this automation will be evaluated")
    job_variables: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Job variables to pass to the run, or None to use the "
            "deployment's default job variables"
        ),
    )

    # from ResourceTrigger

    match: ResourceSpecification = Field(
        default_factory=lambda: ResourceSpecification.parse_obj({}),
        description="Labels for resources which this trigger will match.",
    )
    match_related: ResourceSpecification = Field(
        default_factory=lambda: ResourceSpecification.parse_obj({}),
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

    _deployment_id: Optional[UUID] = PrivateAttr(default=None)
    parameters: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "The parameters to pass to the deployment, or None to use the "
            "deployment's default parameters"
        ),
    )

    def as_automation(self) -> AutomationCore:
        assert self.name

        trigger: TriggerTypes

        if self.posture == Posture.Metric:
            assert self.metric
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

        return AutomationCore(
            name=self.name,
            description=self.description,
            enabled=self.enabled,
            trigger=trigger,
            actions=self.actions(),
            owner_resource=self.owner_resource(),
        )

    def set_deployment_id(self, deployment_id: UUID):
        self._deployment_id = deployment_id

    def owner_resource(self) -> Optional[str]:
        return f"prefect.deployment.{self._deployment_id}"

    def actions(self) -> List[ActionTypes]:
        assert self._deployment_id
        return [
            RunDeployment(
                source="selected",
                deployment_id=self._deployment_id,
                parameters=self.parameters,
                job_variables=self.job_variables,
            )
        ]
