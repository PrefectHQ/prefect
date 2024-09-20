import abc
from typing import Any, Dict, Optional, Union
from uuid import UUID

from pydantic import Field, model_validator
from typing_extensions import Literal, Self, TypeAlias

from prefect._internal.schemas.bases import PrefectBaseModel
from prefect.client.schemas.objects import StateType


class Action(PrefectBaseModel, abc.ABC):
    """An Action that may be performed when an Automation is triggered"""

    type: str

    def describe_for_cli(self) -> str:
        """A human-readable description of the action"""
        return self.type.replace("-", " ").capitalize()


class DoNothing(Action):
    """Do nothing when an Automation is triggered"""

    type: Literal["do-nothing"] = "do-nothing"


class DeploymentAction(Action):
    """Base class for Actions that operate on Deployments and need to infer them from
    events"""

    source: Literal["selected", "inferred"] = Field(
        "selected",
        description=(
            "Whether this Action applies to a specific selected "
            "deployment (given by `deployment_id`), or to a deployment that is "
            "inferred from the triggering event.  If the source is 'inferred', "
            "the `deployment_id` may not be set.  If the source is 'selected', the "
            "`deployment_id` must be set."
        ),
    )
    deployment_id: Optional[UUID] = Field(
        None, description="The identifier of the deployment"
    )

    @model_validator(mode="after")
    def selected_deployment_requires_id(self):
        wants_selected_deployment = self.source == "selected"
        has_deployment_id = bool(self.deployment_id)
        if wants_selected_deployment != has_deployment_id:
            raise ValueError(
                "deployment_id is "
                + ("not allowed" if has_deployment_id else "required")
            )
        return self


class RunDeployment(DeploymentAction):
    """Runs the given deployment with the given parameters"""

    type: Literal["run-deployment"] = "run-deployment"

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
            "The job variables to pass to the created flow run, or None "
            "to use the deployment's default job variables"
        ),
    )


class PauseDeployment(DeploymentAction):
    """Pauses the given Deployment"""

    type: Literal["pause-deployment"] = "pause-deployment"


class ResumeDeployment(DeploymentAction):
    """Resumes the given Deployment"""

    type: Literal["resume-deployment"] = "resume-deployment"


class ChangeFlowRunState(Action):
    """Changes the state of a flow run associated with the trigger"""

    type: Literal["change-flow-run-state"] = "change-flow-run-state"

    name: Optional[str] = Field(
        None,
        description="The name of the state to change the flow run to",
    )
    state: StateType = Field(
        ...,
        description="The type of the state to change the flow run to",
    )
    message: Optional[str] = Field(
        None,
        description="An optional message to associate with the state change",
    )


class CancelFlowRun(Action):
    """Cancels a flow run associated with the trigger"""

    type: Literal["cancel-flow-run"] = "cancel-flow-run"


class ResumeFlowRun(Action):
    """Resumes a flow run associated with the trigger"""

    type: Literal["resume-flow-run"] = "resume-flow-run"


class SuspendFlowRun(Action):
    """Suspends a flow run associated with the trigger"""

    type: Literal["suspend-flow-run"] = "suspend-flow-run"


class CallWebhook(Action):
    """Call a webhook when an Automation is triggered."""

    type: Literal["call-webhook"] = "call-webhook"
    block_document_id: UUID = Field(
        description="The identifier of the webhook block to use"
    )
    payload: str = Field(
        default="",
        description="An optional templatable payload to send when calling the webhook.",
    )


class SendNotification(Action):
    """Send a notification when an Automation is triggered"""

    type: Literal["send-notification"] = "send-notification"
    block_document_id: UUID = Field(
        description="The identifier of the notification block to use"
    )
    subject: str = Field("Prefect automated notification")
    body: str = Field(description="The text of the notification to send")


class WorkPoolAction(Action):
    """Base class for Actions that operate on Work Pools and need to infer them from
    events"""

    source: Literal["selected", "inferred"] = Field(
        "selected",
        description=(
            "Whether this Action applies to a specific selected "
            "work pool (given by `work_pool_id`), or to a work pool that is "
            "inferred from the triggering event.  If the source is 'inferred', "
            "the `work_pool_id` may not be set.  If the source is 'selected', the "
            "`work_pool_id` must be set."
        ),
    )
    work_pool_id: Optional[UUID] = Field(
        None,
        description="The identifier of the work pool to pause",
    )


class PauseWorkPool(WorkPoolAction):
    """Pauses a Work Pool"""

    type: Literal["pause-work-pool"] = "pause-work-pool"


class ResumeWorkPool(WorkPoolAction):
    """Resumes a Work Pool"""

    type: Literal["resume-work-pool"] = "resume-work-pool"


class WorkQueueAction(Action):
    """Base class for Actions that operate on Work Queues and need to infer them from
    events"""

    source: Literal["selected", "inferred"] = Field(
        "selected",
        description=(
            "Whether this Action applies to a specific selected "
            "work queue (given by `work_queue_id`), or to a work queue that is "
            "inferred from the triggering event.  If the source is 'inferred', "
            "the `work_queue_id` may not be set.  If the source is 'selected', the "
            "`work_queue_id` must be set."
        ),
    )
    work_queue_id: Optional[UUID] = Field(
        None, description="The identifier of the work queue to pause"
    )

    @model_validator(mode="after")
    def selected_work_queue_requires_id(self) -> Self:
        wants_selected_work_queue = self.source == "selected"
        has_work_queue_id = bool(self.work_queue_id)
        if wants_selected_work_queue != has_work_queue_id:
            raise ValueError(
                "work_queue_id is "
                + ("not allowed" if has_work_queue_id else "required")
            )
        return self


class PauseWorkQueue(WorkQueueAction):
    """Pauses a Work Queue"""

    type: Literal["pause-work-queue"] = "pause-work-queue"


class ResumeWorkQueue(WorkQueueAction):
    """Resumes a Work Queue"""

    type: Literal["resume-work-queue"] = "resume-work-queue"


class AutomationAction(Action):
    """Base class for Actions that operate on Automations and need to infer them from
    events"""

    source: Literal["selected", "inferred"] = Field(
        "selected",
        description=(
            "Whether this Action applies to a specific selected "
            "automation (given by `automation_id`), or to an automation that is "
            "inferred from the triggering event.  If the source is 'inferred', "
            "the `automation_id` may not be set.  If the source is 'selected', the "
            "`automation_id` must be set."
        ),
    )
    automation_id: Optional[UUID] = Field(
        None, description="The identifier of the automation to act on"
    )

    @model_validator(mode="after")
    def selected_automation_requires_id(self) -> Self:
        wants_selected_automation = self.source == "selected"
        has_automation_id = bool(self.automation_id)
        if wants_selected_automation != has_automation_id:
            raise ValueError(
                "automation_id is "
                + ("not allowed" if has_automation_id else "required")
            )
        return self


class PauseAutomation(AutomationAction):
    """Pauses a Work Queue"""

    type: Literal["pause-automation"] = "pause-automation"


class ResumeAutomation(AutomationAction):
    """Resumes a Work Queue"""

    type: Literal["resume-automation"] = "resume-automation"


class DeclareIncident(Action):
    """Declares an incident for the triggering event.  Only available on Prefect Cloud"""

    type: Literal["declare-incident"] = "declare-incident"


# The actual action types that we support.  It's important to update this
# Union when adding new subclasses of Action so that they are available for clients
# and in the OpenAPI docs
ActionTypes: TypeAlias = Union[
    DoNothing,
    RunDeployment,
    PauseDeployment,
    ResumeDeployment,
    CancelFlowRun,
    ChangeFlowRunState,
    PauseWorkQueue,
    ResumeWorkQueue,
    SendNotification,
    CallWebhook,
    PauseAutomation,
    ResumeAutomation,
    SuspendFlowRun,
    PauseWorkPool,
    ResumeWorkPool,
    # Prefect Cloud only
    DeclareIncident,
]
