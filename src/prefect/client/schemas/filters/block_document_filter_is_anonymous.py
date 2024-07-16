from typing import Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel


class BlockDocumentFilterIsAnonymous(PrefectBaseModel):
    """Filter by `BlockDocument.is_anonymous`."""

    eq_: Optional[bool] = Field(
        default=None,
        description=(
            "Filter block documents for only those that are or are not anonymous."
        ),
    )