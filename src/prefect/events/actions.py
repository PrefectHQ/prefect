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


class DoNothing(Action):
    """Do nothing, which may be helpful for testing automations"""

    type: Literal["do-nothing"] = "do-nothing"


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


class SendNotification(Action):
    """Send a notification with the given parameters"""

    type: Literal["send-notification"] = "send-notification"

    block_document_id: UUID = Field(
        ..., description="The identifier of the notification block"
    )
    body: str = Field(..., description="Notification body")
    subject: Optional[str] = Field(None, description="Notification subject")


ActionTypes = Union[DoNothing, RunDeployment, SendNotification]
