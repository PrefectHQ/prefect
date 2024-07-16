from typing import List, Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel


class DeploymentFilterName(PrefectBaseModel):
    """Filter by `Deployment.name`."""

    any_: Optional[List[str]] = Field(
        default=None,
        description="A list of deployment names to include",
        examples=[["my-deployment-1", "my-deployment-2"]],
    )

    like_: Optional[str] = Field(
        default=None,
        description=(
            "A case-insensitive partial match. For example, "
            " passing 'marvin' will match "
            "'marvin', 'sad-Marvin', and 'marvin-robot'."
        ),
        examples=["marvin"],
    )
