from typing import List, Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel


class BlockSchemaFilterCapabilities(PrefectBaseModel):
    """Filter by `BlockSchema.capabilities`"""

    all_: Optional[List[str]] = Field(
        default=None,
        examples=[["write-storage", "read-storage"]],
        description=(
            "A list of block capabilities. Block entities will be returned only if an"
            " associated block schema has a superset of the defined capabilities."
        ),
    )