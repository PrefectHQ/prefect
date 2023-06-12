from typing import Any, Dict, Optional
from typing_extensions import Literal
from uuid import UUID

from pydantic import Field

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


ActionTypes = RunDeployment
