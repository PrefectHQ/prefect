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
import warnings
from datetime import timedelta
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

from prefect._internal.compatibility.deprecated import deprecated_class
from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect._internal.schemas.validators import validate_trigger_within

if HAS_PYDANTIC_V2:
    from pydantic.v1 import Field, PrivateAttr, root_validator, validator
    from pydantic.v1.fields import ModelField
else:
    from pydantic import Field, PrivateAttr, root_validator, validator
    from pydantic.fields import ModelField

from prefect._internal.compatibility.experimental import (
    EXPERIMENTAL_WARNING,
    PREFECT_EXPERIMENTAL_WARN,
    ExperimentalFeature,
    experiment_enabled,
)
from prefect._internal.schemas.bases import PrefectBaseModel
from prefect.events.actions import RunDeployment
from prefect.settings import (
    PREFECT_EXPERIMENTAL_WARN_FLOW_RUN_INFRA_OVERRIDES,
)

from .automations import (
    Automation,
    CompoundTrigger,
    EventTrigger,
    MetricTrigger,
    MetricTriggerQuery,
    Posture,
    SequenceTrigger,
    Trigger,
    TriggerTypes,
)
from .events import ResourceSpecification


class BaseDeploymentTrigger(PrefectBaseModel, abc.ABC, extra="ignore"):
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

    # Fields from Trigger

    type: str

    # Fields from Deployment

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
    _deployment_id: Optional[UUID] = PrivateAttr(default=None)

    def set_deployment_id(self, deployment_id: UUID):
        self._deployment_id = deployment_id

    def owner_resource(self) -> Optional[str]:
        return f"prefect.deployment.{self._deployment_id}"

    def actions(self) -> List[RunDeployment]:
        if self.job_variables is not None and experiment_enabled(
            "flow_run_infra_overrides"
        ):
            if (
                PREFECT_EXPERIMENTAL_WARN
                and PREFECT_EXPERIMENTAL_WARN_FLOW_RUN_INFRA_OVERRIDES
            ):
                warnings.warn(
                    EXPERIMENTAL_WARNING.format(
                        feature="Flow run job variables",
                        group="flow_run_infra_overrides",
                        help="To use this feature, update your workers to Prefect 2.16.4 or later. ",
                    ),
                    ExperimentalFeature,
                    stacklevel=3,
                )
        if not experiment_enabled("flow_run_infra_overrides"):
            # nullify job_variables if the flag is disabled
            self.job_variables = None

        assert self._deployment_id
        return [
            RunDeployment(
                parameters=self.parameters,
                deployment_id=self._deployment_id,
                job_variables=self.job_variables,
            )
        ]

    def as_automation(self) -> Automation:
        if not self.name:
            raise ValueError("name is required")

        return Automation(
            name=self.name,
            description=self.description,
            enabled=self.enabled,
            trigger=self.as_trigger(),
            actions=self.actions(),
            owner_resource=self.owner_resource(),
        )

    @abc.abstractmethod
    def as_trigger(self) -> Trigger:
        ...


class DeploymentResourceTrigger(BaseDeploymentTrigger, abc.ABC):
    """
    Base class for triggers that may filter by the labels of resources.
    """

    type: str

    match: ResourceSpecification = Field(
        default_factory=lambda: ResourceSpecification.parse_obj({}),
        description="Labels for resources which this trigger will match.",
    )
    match_related: ResourceSpecification = Field(
        default_factory=lambda: ResourceSpecification.parse_obj({}),
        description="Labels for related resources which this trigger will match.",
    )


class DeploymentEventTrigger(DeploymentResourceTrigger):
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
        Posture.Reactive,
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

    def as_trigger(self) -> Trigger:
        return EventTrigger(
            match=self.match,
            match_related=self.match_related,
            after=self.after,
            expect=self.expect,
            for_each=self.for_each,
            posture=self.posture,
            threshold=self.threshold,
            within=self.within,
        )


class DeploymentMetricTrigger(DeploymentResourceTrigger):
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

    def as_trigger(self) -> Trigger:
        return MetricTrigger(
            match=self.match,
            match_related=self.match_related,
            posture=self.posture,
            metric=self.metric,
            job_variables=self.job_variables,
        )


class DeploymentCompositeTrigger(BaseDeploymentTrigger, abc.ABC):
    """
    Requires some number of triggers to have fired within the given time period.
    """

    type: Literal["compound", "sequence"]
    triggers: List["TriggerTypes"]
    within: Optional[timedelta]


class DeploymentCompoundTrigger(DeploymentCompositeTrigger):
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

    def as_trigger(self) -> Trigger:
        return CompoundTrigger(
            require=self.require,
            triggers=self.triggers,
            within=self.within,
            job_variables=self.job_variables,
        )


class DeploymentSequenceTrigger(DeploymentCompositeTrigger):
    """A composite trigger that requires some number of triggers to have fired
    within the given time period in a specific order"""

    type: Literal["sequence"] = "sequence"

    def as_trigger(self) -> Trigger:
        return SequenceTrigger(
            triggers=self.triggers,
            within=self.within,
            job_variables=self.job_variables,
        )


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

    def set_deployment_id(self, deployment_id: UUID):
        self._deployment_id = deployment_id

    def owner_resource(self) -> Optional[str]:
        return f"prefect.deployment.{self._deployment_id}"

    def actions(self) -> List[RunDeployment]:
        if self.job_variables is not None and experiment_enabled(
            "flow_run_infra_overrides"
        ):
            if (
                PREFECT_EXPERIMENTAL_WARN
                and PREFECT_EXPERIMENTAL_WARN_FLOW_RUN_INFRA_OVERRIDES
            ):
                warnings.warn(
                    EXPERIMENTAL_WARNING.format(
                        feature="Flow run job variables",
                        group="flow_run_infra_overrides",
                        help="To use this feature, update your workers to Prefect 2.16.4 or later. ",
                    ),
                    ExperimentalFeature,
                    stacklevel=3,
                )
        if not experiment_enabled("flow_run_infra_overrides"):
            # nullify job_variables if the flag is disabled
            self.job_variables = None

        assert self._deployment_id
        return [
            RunDeployment(
                parameters=self.parameters,
                deployment_id=self._deployment_id,
                job_variables=self.job_variables,
            )
        ]
