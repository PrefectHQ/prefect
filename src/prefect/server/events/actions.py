"""
The actions consumer watches for actions that have been triggered by Automations
and carries them out.  Also includes the various concrete subtypes of Actions
"""

import abc
from base64 import b64encode
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Dict,
    List,
    Literal,
    Optional,
    Tuple,
    Union,
)
from uuid import UUID, uuid4

import orjson
import pendulum
from httpx import Response
from typing_extensions import TypeAlias

from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    from pydantic.v1 import Field, PrivateAttr, root_validator, validator
    from pydantic.v1.fields import ModelField
else:
    from pydantic import Field, PrivateAttr, root_validator, validator
    from pydantic.fields import ModelField

from prefect.logging import get_logger
from prefect.server.events.clients import (
    PrefectServerEventsAPIClient,
    PrefectServerEventsClient,
)
from prefect.server.events.schemas.events import Event, RelatedResource, Resource
from prefect.server.schemas.actions import StateCreate
from prefect.server.schemas.core import (
    WorkPool,
)
from prefect.server.schemas.states import StateType, Suspended
from prefect.server.utilities.schemas import PrefectBaseModel

if TYPE_CHECKING:  # pragma: no cover
    from prefect.server.api.clients import OrchestrationClient
    from prefect.server.events.schemas.automations import TriggeredAction

logger = get_logger(__name__)


class ActionFailed(Exception):
    def __init__(self, reason: str):
        self.reason = reason


class Action(PrefectBaseModel, abc.ABC):
    """An Action that may be performed when an Automation is triggered"""

    type: str

    # Captures any additional information about the result of the action we'd like to
    # make available in the payload of the executed or failed events
    _result_details: Dict[str, Any] = PrivateAttr({})
    _resulting_related_resources: List[RelatedResource] = PrivateAttr([])

    @abc.abstractmethod
    async def act(self, triggered_action: "TriggeredAction") -> None:
        """Perform the requested Action"""

    async def fail(self, triggered_action: "TriggeredAction", reason: str) -> None:
        from prefect.server.events.schemas.automations import EventTrigger

        automation = triggered_action.automation
        action = triggered_action.action
        action_index = triggered_action.action_index

        automation_resource_id = f"prefect-cloud.automation.{automation.id}"

        async with PrefectServerEventsClient() as events:
            logger.warning(
                "Action failed: %r",
                reason,
                extra={**self.logging_context(triggered_action)},
            )
            event = Event(
                occurred=pendulum.now("UTC"),
                event="prefect-cloud.automation.action.failed",
                resource={
                    "prefect.resource.id": automation_resource_id,
                    "prefect.resource.name": automation.name,
                    "prefect-cloud.trigger-type": automation.trigger.type,
                },
                related=self._resulting_related_resources,
                payload={
                    "action_index": action_index,
                    "action_type": action.type,
                    "invocation": str(triggered_action.id),
                    "reason": reason,
                    **self._result_details,
                },
                id=uuid4(),
            )
            if isinstance(automation.trigger, EventTrigger):
                event.resource["prefect-cloud.posture"] = automation.trigger.posture
            await events.emit(event)

    async def succeed(self, triggered_action: "TriggeredAction") -> None:
        from prefect.server.events.schemas.automations import EventTrigger

        automation = triggered_action.automation
        action = triggered_action.action
        action_index = triggered_action.action_index

        automation_resource_id = f"prefect-cloud.automation.{automation.id}"

        async with PrefectServerEventsClient() as events:
            event = Event(
                occurred=pendulum.now("UTC"),
                event="prefect-cloud.automation.action.executed",
                resource={
                    "prefect.resource.id": automation_resource_id,
                    "prefect.resource.name": automation.name,
                    "prefect-cloud.trigger-type": automation.trigger.type,
                },
                related=self._resulting_related_resources,
                payload={
                    "action_index": action_index,
                    "action_type": action.type,
                    "invocation": str(triggered_action.id),
                    **self._result_details,
                },
                id=uuid4(),
            )
            if isinstance(automation.trigger, EventTrigger):
                event.resource["prefect-cloud.posture"] = automation.trigger.posture
            await events.emit(event)

    def logging_context(self, triggered_action: "TriggeredAction") -> Dict[str, Any]:
        """Common logging context for all actions"""
        return {
            "automation": str(triggered_action.automation.id),
            "action": self.dict(json_compatible=True),
            "triggering_event": (
                {
                    "id": triggered_action.triggering_event.id,
                    "event": triggered_action.triggering_event.event,
                }
                if triggered_action.triggering_event
                else None
            ),
            "triggering_labels": triggered_action.triggering_labels,
        }


class DoNothing(Action):
    """Do nothing when an Automation is triggered"""

    type: Literal["do-nothing"] = "do-nothing"

    async def act(self, triggered_action: "TriggeredAction") -> None:
        logger.info(
            "Doing nothing",
            extra={**self.logging_context(triggered_action)},
        )


class EmitEventAction(Action):
    async def act(self, triggered_action: "TriggeredAction") -> None:
        event = await self.create_event(triggered_action)

        self._result_details["emitted_event"] = str(event.id)

        async with PrefectServerEventsClient() as events:
            await events.emit(event)

    @abc.abstractmethod
    async def create_event(self, triggered_action: "TriggeredAction") -> "Event":
        """Create an event from the TriggeredAction"""


class ExternalDataAction(Action):
    """Base class for Actions that require data from an external source such as
    the Orion or Nebula APIs"""

    async def orchestration_client(
        self, triggered_action: "TriggeredAction"
    ) -> "OrchestrationClient":
        from prefect.server.api.clients import OrchestrationClient

        return OrchestrationClient(
            additional_headers={
                "Prefect-Automation-ID": str(triggered_action.automation.id),
                "Prefect-Automation-Name": (
                    b64encode(triggered_action.automation.name.encode()).decode()
                ),
            },
        )

    async def events_api_client(
        self, triggered_action: "TriggeredAction"
    ) -> PrefectServerEventsAPIClient:
        return PrefectServerEventsAPIClient(
            additional_headers={
                "Prefect-Automation-ID": str(triggered_action.automation.id),
                "Prefect-Automation-Name": (
                    b64encode(triggered_action.automation.name.encode()).decode()
                ),
            },
        )

    def reason_from_response(self, response: Response) -> str:
        # TODO: handle specific status codes here
        return f"Unexpected status from {self.type} action: {response.status_code}"


def _first_resource_of_kind(event: "Event", expected_kind: str) -> Optional["Resource"]:
    for resource in event.involved_resources:
        kind, _, _ = resource.id.rpartition(".")
        if kind == expected_kind:
            return resource

    return None


def _kind_and_id_from_resource(resource) -> Union[Tuple[str, UUID], Tuple[None, None]]:
    kind, _, id = resource.id.rpartition(".")

    try:
        return kind, UUID(id)
    except ValueError:
        pass

    return None, None


def _id_from_resource_id(resource_id: str, expected_kind: str) -> Optional[UUID]:
    kind, _, id = resource_id.rpartition(".")
    if kind == expected_kind:
        try:
            return UUID(id)
        except ValueError:
            pass
    return None


def _id_of_first_resource_of_kind(event: "Event", expected_kind: str) -> Optional[UUID]:
    resource = _first_resource_of_kind(event, expected_kind)
    if resource:
        if id := _id_from_resource_id(resource.id, expected_kind):
            return id
    return None


WorkspaceVariables: TypeAlias = Dict[str, str]
TemplateContextObject: TypeAlias = Union[PrefectBaseModel, WorkspaceVariables, None]


class JinjaTemplateAction(ExternalDataAction):
    """Base class for Actions that use Jinja templates supplied by the user and
    are rendered with a context containing data from the triggered action,
    orion and nebula."""

    _object_cache: Dict[str, TemplateContextObject] = PrivateAttr(default_factory=dict)

    @classmethod
    def validate_template(cls, template: str, field_name: str) -> str:
        pass  # TODO: coming in a future update
        return template

    async def _render(
        self, templates: List[str], triggered_action: "TriggeredAction"
    ) -> List[str]:
        raise NotImplementedError("TODO: coming in a future automations update")


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

    @root_validator
    def selected_deployment_requires_id(cls, values):
        wants_selected_deployment = values.get("source") == "selected"
        has_deployment_id = bool(values.get("deployment_id"))
        if wants_selected_deployment != has_deployment_id:
            raise ValueError(
                "deployment_id is "
                + ("not allowed" if has_deployment_id else "required")
            )
        return values

    async def deployment_id_to_use(self, triggered_action: "TriggeredAction") -> UUID:
        if self.source == "selected":
            assert self.deployment_id
            return self.deployment_id

        event = triggered_action.triggering_event
        if not event:
            raise ActionFailed("No event to infer the deployment")

        assert event
        if id := _id_of_first_resource_of_kind(event, "prefect.deployment"):
            return id

        raise ActionFailed("No deployment could be inferred")


class DeploymentCommandAction(DeploymentAction, ExternalDataAction):
    """Executes a command against a matching deployment"""

    _action_description: ClassVar[str]

    async def act(self, triggered_action: "TriggeredAction") -> None:
        deployment_id = await self.deployment_id_to_use(triggered_action)

        self._resulting_related_resources.append(
            RelatedResource.parse_obj(
                {
                    "prefect.resource.id": f"prefect.deployment.{deployment_id}",
                    "prefect.resource.role": "target",
                }
            )
        )

        logger.info(
            self._action_description,
            extra={
                "deployment_id": deployment_id,
                **self.logging_context(triggered_action),
            },
        )

        async with await self.orchestration_client(triggered_action) as orion:
            response = await self.command(orion, deployment_id, triggered_action)

            self._result_details["status_code"] = response.status_code
            if response.status_code >= 300:
                raise ActionFailed(self.reason_from_response(response))

    @abc.abstractmethod
    async def command(
        self,
        orion: "OrchestrationClient",
        deployment_id: UUID,
        triggered_action: "TriggeredAction",
    ) -> Response:
        """Execute the orion deployment command"""


class RunDeployment(JinjaTemplateAction, DeploymentCommandAction):
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

    _action_description: ClassVar[str] = "Running deployment"

    async def command(
        self,
        orion: "OrchestrationClient",
        deployment_id: UUID,
        triggered_action: "TriggeredAction",
    ) -> Response:
        raise NotImplementedError("TODO: coming in a future automations update")

    async def render_parameters(
        self, triggered_action: "TriggeredAction"
    ) -> Dict[str, Any]:
        raise NotImplementedError("TODO: coming in a future automations update")


class PauseDeployment(DeploymentCommandAction):
    """Pauses the given Deployment"""

    type: Literal["pause-deployment"] = "pause-deployment"

    _action_description: ClassVar[str] = "Pausing deployment"

    async def command(
        self,
        orion: "OrchestrationClient",
        deployment_id: UUID,
        triggered_action: "TriggeredAction",
    ) -> Response:
        raise NotImplementedError("TODO: coming in a future automations update")


class ResumeDeployment(DeploymentCommandAction):
    """Resumes the given Deployment"""

    type: Literal["resume-deployment"] = "resume-deployment"

    _action_description: ClassVar[str] = "Resuming deployment"

    async def command(
        self,
        orion: "OrchestrationClient",
        deployment_id: UUID,
        triggered_action: "TriggeredAction",
    ) -> Response:
        raise NotImplementedError("TODO: coming in a future automations update")


class FlowRunStateChangeAction(ExternalDataAction):
    """Changes the state of a flow run associated with the trigger"""

    async def flow_run_to_change(self, triggered_action: "TriggeredAction") -> UUID:
        # Proactive triggers won't have an event, but they might be tracking
        # buckets per-resource, so check for that first
        labels = triggered_action.triggering_labels
        if triggering_resource_id := labels.get("prefect.resource.id"):
            if id := _id_from_resource_id(triggering_resource_id, "prefect.flow-run"):
                return id

        event = triggered_action.triggering_event
        if event:
            if id := _id_of_first_resource_of_kind(event, "prefect.flow-run"):
                return id

        raise ActionFailed("No flow run could be inferred")

    @abc.abstractmethod
    async def new_state(self, triggered_action: "TriggeredAction") -> StateCreate:
        """Return the new state for the flow run"""

    async def act(self, triggered_action: "TriggeredAction") -> None:
        raise NotImplementedError("TODO: coming in a future automations update")


class ChangeFlowRunState(FlowRunStateChangeAction):
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

    async def new_state(self, triggered_action: "TriggeredAction") -> StateCreate:
        message = (
            self.message
            or f"State changed by Automation {triggered_action.automation.id}"
        )

        return StateCreate(
            name=self.name,
            type=self.state,
            message=message,
        )


class CancelFlowRun(FlowRunStateChangeAction):
    """Cancels a flow run associated with the trigger"""

    type: Literal["cancel-flow-run"] = "cancel-flow-run"

    async def new_state(self, triggered_action: "TriggeredAction") -> StateCreate:
        return StateCreate(
            type=StateType.CANCELLING,
            message=f"Cancelled by Automation {triggered_action.automation.id}",
        )


class SuspendFlowRun(FlowRunStateChangeAction):
    """Suspends a flow run associated with the trigger"""

    type: Literal["suspend-flow-run"] = "suspend-flow-run"

    async def new_state(self, triggered_action: "TriggeredAction") -> StateCreate:
        state = Suspended(
            timeout_seconds=3600,
            message=f"Suspended by Automation {triggered_action.automation.id}",
        )

        return StateCreate(
            type=state.type,
            name=state.name,
            message=state.message,
            state_details=state.state_details,
        )


class CallWebhook(JinjaTemplateAction):
    """Call a webhook when an Automation is triggered."""

    type: Literal["call-webhook"] = "call-webhook"
    block_document_id: UUID = Field(
        description="The identifier of the webhook block to use"
    )
    payload: str = Field(
        default="",
        description="An optional templatable payload to send when calling the webhook.",
    )

    @validator("payload", pre=True)
    def ensure_payload_is_a_string(
        cls, value: Union[str, Dict[str, Any], None]
    ) -> Optional[str]:
        """Temporary measure while we migrate payloads from being a dictionary to
        a string template.  This covers both reading from the database where values
        may currently be a dictionary, as well as the API, where older versions of the
        frontend may be sending a JSON object with the single `"message"` key."""
        if value is None:
            return value

        if isinstance(value, str):
            return value

        return orjson.dumps(value, option=orjson.OPT_INDENT_2).decode()

    @validator("payload")
    def validate_payload_templates(cls, value: Optional[str]) -> Optional[str]:
        """
        Validate user-provided payload template.
        """
        if not value:
            return value

        cls.validate_template(value, "payload")

        return value

    async def act(self, triggered_action: "TriggeredAction") -> None:
        raise NotImplementedError("TODO: coming in a future automations update")


class SendNotification(JinjaTemplateAction):
    """Send a notification when an Automation is triggered"""

    type: Literal["send-notification"] = "send-notification"
    block_document_id: UUID = Field(
        description="The identifier of the notification block to use"
    )
    subject: str = Field("Prefect automated notification")
    body: str = Field(description="The text of the notification to send")

    @validator("subject", "body")
    def is_valid_template(cls, value: str, field: ModelField) -> str:
        return cls.validate_template(value, field.name)

    async def act(self, triggered_action: "TriggeredAction") -> None:
        raise NotImplementedError("TODO: coming in a future automations update")

    async def render(self, triggered_action: "TriggeredAction") -> List[str]:
        return await self._render([self.subject, self.body], triggered_action)


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

    @root_validator
    def selected_work_pool_requires_id(cls, values):
        wants_selected_work_pool = values.get("source") == "selected"
        has_work_pool_id = bool(values.get("work_pool_id"))
        if wants_selected_work_pool != has_work_pool_id:
            raise ValueError(
                "work_pool_id is " + ("not allowed" if has_work_pool_id else "required")
            )
        return values

    async def work_pool_id_to_use(self, triggered_action: "TriggeredAction") -> UUID:
        if self.source == "selected":
            assert self.work_pool_id
            return self.work_pool_id

        event = triggered_action.triggering_event
        if not event:
            raise ActionFailed("No event to infer the work pool")

        assert event
        if id := _id_of_first_resource_of_kind(event, "prefect.work-pool"):
            return id

        raise ActionFailed("No work pool could be inferred")


class WorkPoolCommandAction(WorkPoolAction, ExternalDataAction):
    _action_description: ClassVar[str]

    _target_work_pool: Optional[WorkPool] = PrivateAttr(default=None)

    async def target_work_pool(self, triggered_action: "TriggeredAction") -> WorkPool:
        raise NotImplementedError("TODO: coming in a future automations update")

    async def act(self, triggered_action: "TriggeredAction") -> None:
        raise NotImplementedError("TODO: coming in a future automations update")

    @abc.abstractmethod
    async def command(
        self,
        orion: "OrchestrationClient",
        work_pool: WorkPool,
        triggered_action: "TriggeredAction",
    ) -> Response:
        """Issue the command to the Work Pool"""


class PauseWorkPool(WorkPoolCommandAction):
    """Pauses a Work Pool"""

    type: Literal["pause-work-pool"] = "pause-work-pool"

    _action_description: ClassVar[str] = "Pausing work pool"

    async def command(
        self,
        orion: "OrchestrationClient",
        work_pool: WorkPool,
        triggered_action: "TriggeredAction",
    ) -> Response:
        raise NotImplementedError("TODO: coming in a future automations update")


class ResumeWorkPool(WorkPoolCommandAction):
    """Resumes a Work Pool"""

    type: Literal["resume-work-pool"] = "resume-work-pool"

    _action_description: ClassVar[str] = "Resuming work pool"

    async def command(
        self,
        orion: "OrchestrationClient",
        work_pool: WorkPool,
        triggered_action: "TriggeredAction",
    ) -> Response:
        raise NotImplementedError("TODO: coming in a future automations update")


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

    @root_validator
    def selected_work_queue_requires_id(cls, values):
        wants_selected_work_queue = values.get("source") == "selected"
        has_work_queue_id = bool(values.get("work_queue_id"))
        if wants_selected_work_queue != has_work_queue_id:
            raise ValueError(
                "work_queue_id is "
                + ("not allowed" if has_work_queue_id else "required")
            )
        return values

    async def work_queue_id_to_use(self, triggered_action: "TriggeredAction") -> UUID:
        if self.source == "selected":
            assert self.work_queue_id
            return self.work_queue_id

        event = triggered_action.triggering_event
        if not event:
            raise ActionFailed("No event to infer the work queue")

        assert event
        if id := _id_of_first_resource_of_kind(event, "prefect.work-queue"):
            return id

        raise ActionFailed("No work queue could be inferred")


class WorkQueueCommandAction(WorkQueueAction, ExternalDataAction):
    _action_description: ClassVar[str]

    async def act(self, triggered_action: "TriggeredAction") -> None:
        raise NotImplementedError("TODO: coming in a future automations update")

    @abc.abstractmethod
    async def command(
        self,
        orion: "OrchestrationClient",
        work_queue_id: UUID,
        triggered_action: "TriggeredAction",
    ) -> Response:
        """Issue the command to the Work Queue"""


class PauseWorkQueue(WorkQueueCommandAction):
    """Pauses a Work Queue"""

    type: Literal["pause-work-queue"] = "pause-work-queue"

    _action_description: ClassVar[str] = "Pausing work queue"

    async def command(
        self,
        orion: "OrchestrationClient",
        work_queue_id: UUID,
        triggered_action: "TriggeredAction",
    ) -> Response:
        raise NotImplementedError("TODO: coming in a future automations update")


class ResumeWorkQueue(WorkQueueCommandAction):
    """Resumes a Work Queue"""

    type: Literal["resume-work-queue"] = "resume-work-queue"

    _action_description: ClassVar[str] = "Resuming work queue"

    async def command(
        self,
        orion: "OrchestrationClient",
        work_queue_id: UUID,
        triggered_action: "TriggeredAction",
    ) -> Response:
        raise NotImplementedError("TODO: coming in a future automations update")


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

    @root_validator
    def selected_automation_requires_id(cls, values):
        wants_selected_automation = values.get("source") == "selected"
        has_automation_id = bool(values.get("automation_id"))
        if wants_selected_automation != has_automation_id:
            raise ValueError(
                "automation_id is "
                + ("not allowed" if has_automation_id else "required")
            )
        return values

    async def automation_id_to_use(self, triggered_action: "TriggeredAction") -> UUID:
        if self.source == "selected":
            assert self.automation_id
            return self.automation_id

        event = triggered_action.triggering_event
        if not event:
            raise ActionFailed("No event to infer the automation")

        assert event
        if id := _id_of_first_resource_of_kind(event, "prefect-cloud.automation"):
            return id

        raise ActionFailed("No automation could be inferred")


class AutomationCommandAction(AutomationAction, ExternalDataAction):
    _action_description: ClassVar[str]

    async def act(self, triggered_action: "TriggeredAction") -> None:
        automation_id = await self.automation_id_to_use(triggered_action)

        self._resulting_related_resources += [
            RelatedResource.parse_obj(
                {
                    "prefect.resource.id": f"prefect-cloud.automation.{automation_id}",
                    "prefect.resource.role": "target",
                }
            )
        ]

        logger.info(
            self._action_description,
            extra={
                "automation_id": automation_id,
                **self.logging_context(triggered_action),
            },
        )

        async with await self.events_api_client(triggered_action) as events:
            response = await self.command(events, automation_id, triggered_action)

            self._result_details["status_code"] = response.status_code
            if response.status_code >= 300:
                raise ActionFailed(self.reason_from_response(response))

    @abc.abstractmethod
    async def command(
        self,
        events: PrefectServerEventsAPIClient,
        automation_id: UUID,
        triggered_action: "TriggeredAction",
    ) -> Response:
        """Issue the command to the Work Queue"""


class PauseAutomation(AutomationCommandAction):
    """Pauses a Work Queue"""

    type: Literal["pause-automation"] = "pause-automation"

    _action_description: ClassVar[str] = "Pausing automation"

    async def command(
        self,
        events: PrefectServerEventsAPIClient,
        automation_id: UUID,
        triggered_action: "TriggeredAction",
    ) -> Response:
        raise NotImplementedError("TODO: coming in a future automations update")


class ResumeAutomation(AutomationCommandAction):
    """Resumes a Work Queue"""

    type: Literal["resume-automation"] = "resume-automation"

    _action_description: ClassVar[str] = "Resuming auitomation"

    async def command(
        self,
        events: PrefectServerEventsAPIClient,
        automation_id: UUID,
        triggered_action: "TriggeredAction",
    ) -> Response:
        raise NotImplementedError("TODO: coming in a future automations update")


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
]
