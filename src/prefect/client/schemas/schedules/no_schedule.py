from pydantic import ConfigDict

from prefect._internal.schemas.bases import PrefectBaseModel


class NoSchedule(PrefectBaseModel):
    model_config = ConfigDict(extra="forbid")
