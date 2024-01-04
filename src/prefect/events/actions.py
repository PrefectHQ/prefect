from typing import Any, Dict, Optional, Union
from uuid import UUID

from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    from pydantic.v1 import Field
else:
    from pydantic import Field

from typing_extensions import Literal

from prefect._internal.schemas.bases import PrefectBaseModel


class Action(PrefectBaseModel):
    """An Action that may be performed when an Automation is triggered"""

    type: str


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


class SendNotification(Action):
    """Send a notification with the given parameters"""

    type: Literal["send-notification"] = "send-notification"
    block_document_id: UUID = Field(
        ..., description="The identifier of the notification block"
    )
    body: str = Field(..., description="Notification body")
    subject: Optional[str] = Field(None, description="Notification subject")


ActionTypes = Union[RunDeployment, SendNotification]
