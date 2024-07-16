from uuid import UUID

from pydantic import ConfigDict

from prefect._internal.schemas.bases import PrefectBaseModel


class MinimalConcurrencyLimitResponse(PrefectBaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    name: str
    limit: int
