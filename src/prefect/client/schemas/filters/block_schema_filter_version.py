from typing import List, Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel


class BlockSchemaFilterVersion(PrefectBaseModel):
    """Filter by `BlockSchema.capabilities`"""

    any_: Optional[List[str]] = Field(
        default=None,
        examples=[["2.0.0", "2.1.0"]],
        description="A list of block schema versions.",
    )