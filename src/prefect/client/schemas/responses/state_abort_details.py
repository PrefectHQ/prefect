from typing import Optional

from pydantic import Field
from typing_extensions import Literal

from prefect._internal.schemas.bases import PrefectBaseModel


class StateAbortDetails(PrefectBaseModel):
    """Details associated with an ABORT state transition."""

    type: Literal["abort_details"] = Field(
        default="abort_details",
        description=(
            "The type of state transition detail. Used to ensure pydantic does not"
            " coerce into a different type."
        ),
    )
    reason: Optional[str] = Field(
        default=None, description="The reason why the state transition was aborted."
    )
