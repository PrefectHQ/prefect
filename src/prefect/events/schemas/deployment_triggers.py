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
from typing import (
    Any,
    ClassVar,
    Dict,
    Optional,
    Type,
    Union,
)

from pydantic import Field
from typing_extensions import TypeAlias

from prefect._internal.schemas.bases import PrefectBaseModel

from .automations import (
    CompoundTrigger,
    EventTrigger,
    MetricTrigger,
    SequenceTrigger,
    TriggerTypes,
)


class BaseDeploymentTrigger(PrefectBaseModel, abc.ABC, extra="ignore"):  # type: ignore[call-arg]
    """
    Base class describing a set of criteria that must be satisfied in order to trigger
    an automation.
    """

    # Fields from Automation

    name: Optional[str] = Field(
        default=None,
        description="The name to give to the automation created for this trigger.",
    )
    description: str = Field(
        default="", description="A longer description of this automation"
    )
    enabled: bool = Field(
        default=True, description="Whether this automation will be evaluated"
    )

    # Fields from the RunDeployment action

    parameters: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "The parameters to pass to the deployment, or None to use the "
            "deployment's default parameters"
        ),
    )
    job_variables: Optional[Dict[str, Any]] = Field(
        default=None,
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

    trigger_type: ClassVar[Type[TriggerTypes]] = EventTrigger


class DeploymentMetricTrigger(BaseDeploymentTrigger, MetricTrigger):
    """
    A trigger that fires based on the results of a metric query.
    """

    trigger_type: ClassVar[Type[TriggerTypes]] = MetricTrigger


class DeploymentCompoundTrigger(BaseDeploymentTrigger, CompoundTrigger):
    """A composite trigger that requires some number of triggers to have
    fired within the given time period"""

    trigger_type: ClassVar[Type[TriggerTypes]] = CompoundTrigger


class DeploymentSequenceTrigger(BaseDeploymentTrigger, SequenceTrigger):
    """A composite trigger that requires some number of triggers to have fired
    within the given time period in a specific order"""

    trigger_type: ClassVar[Type[TriggerTypes]] = SequenceTrigger


# Concrete deployment trigger types
DeploymentTriggerTypes: TypeAlias = Union[
    DeploymentEventTrigger,
    DeploymentMetricTrigger,
    DeploymentCompoundTrigger,
    DeploymentSequenceTrigger,
]
