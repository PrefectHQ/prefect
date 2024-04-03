import abc
from typing import TYPE_CHECKING, Any, Dict, Optional, Union
from uuid import UUID, uuid4

import pendulum

from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    from pydantic.v1 import Field
else:
    from pydantic import Field

from typing_extensions import Literal

from prefect._internal.schemas.bases import PrefectBaseModel
from prefect.logging import get_logger
from prefect.server.events.schemas.events import Event

if TYPE_CHECKING:  # pragma: no cover
    from prefect.server.events.clients import PrefectServerEventsClient
    from prefect.server.events.schemas.automations import TriggeredAction

logger = get_logger(__name__)


class Action(PrefectBaseModel):
    """An Action that may be performed when an Automation is triggered"""

    type: str

    @abc.abstractmethod
    async def act(self, triggered_action: "TriggeredAction") -> None:
        """Perform the requested Action"""

    async def fail(self, triggered_action: "TriggeredAction", reason: str) -> None:
        from prefect.server.events.schemas.automations import EventTrigger

        automation = triggered_action.automation
        action = triggered_action.action
        action_index = triggered_action.action_index

        automation_resource_id = f"prefect.automation.{automation.id}"

        async with PrefectServerEventsClient() as events:
            logger.warning(
                "Action failed: %r",
                reason,
                extra={**self.logging_context(triggered_action)},
            )
            event = Event(
                occurred=pendulum.now("UTC"),
                event="prefect.automation.action.failed",
                resource={
                    "prefect.resource.id": automation_resource_id,
                    "prefect.resource.name": automation.name,
                    "prefect.trigger-type": automation.trigger.type,
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
                event.resource["prefect.posture"] = automation.trigger.posture
            await events.emit(event)

    async def succeed(self, triggered_action: "TriggeredAction") -> None:
        from prefect.server.events.schemas.automations import EventTrigger

        automation = triggered_action.automation
        action = triggered_action.action
        action_index = triggered_action.action_index

        automation_resource_id = f"prefect.automation.{automation.id}"

        async with PrefectServerEventsClient() as events:
            event = Event(
                occurred=pendulum.now("UTC"),
                event="prefect.automation.action.executed",
                resource={
                    "prefect.resource.id": automation_resource_id,
                    "prefect.resource.name": automation.name,
                    "prefect.trigger-type": automation.trigger.type,
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
                event.resource["prefect.posture"] = automation.trigger.posture
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


class RunDeployment(Action):
    """Run the given deployment with the given parameters"""

    type: Literal["run-deployment"] = "run-deployment"
    source: Literal["selected"] = "selected"
    parameters: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "The parameters to pass to the deployment, or None to use the "
            "deployment's default parameters"
        ),
    )
    deployment_id: UUID = Field(..., description="The identifier of the deployment")
    job_variables: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Job variables to pass to the run, or None to use the "
            "deployment's default job variables"
        ),
    )

    async def act(self, triggered_action: "TriggeredAction") -> None:
        raise NotImplementedError()


class SendNotification(Action):
    """Send a notification with the given parameters"""

    type: Literal["send-notification"] = "send-notification"
    block_document_id: UUID = Field(
        ..., description="The identifier of the notification block"
    )
    body: str = Field(..., description="Notification body")
    subject: Optional[str] = Field(None, description="Notification subject")

    async def act(self, triggered_action: "TriggeredAction") -> None:
        raise NotImplementedError()


ActionTypes = Union[DoNothing, RunDeployment, SendNotification]
