from pydantic import Field
from typing_extensions import Literal

from prefect._internal.schemas.bases import PrefectBaseModel


class StateAcceptDetails(PrefectBaseModel):
    """Details associated with an ACCEPT state transition."""

    type: Literal["accept_details"] = Field(
        default="accept_details",
        description=(
            "The type of state transition detail. Used to ensure pydantic does not"
            " coerce into a different type."
        ),
    )
