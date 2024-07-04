from typing import (
    Dict,
    Optional,
    Union,
)

import pendulum
from pydantic import Field
from pydantic_extra_types.pendulum_dt import DateTime

from prefect.client.orchestration import PrefectClient, SyncPrefectClient

from .base import ContextModel


class RunContext(ContextModel):
    """
    The base context for a flow or task run. Data in this context will always be
    available when `get_run_context` is called.

    Attributes:
        start_time: The time the run context was entered
        client: The Prefect client instance being used for API communication
    """

    start_time: DateTime = Field(default_factory=lambda: pendulum.now("UTC"))
    input_keyset: Optional[Dict[str, Dict[str, str]]] = None
    client: Union[PrefectClient, SyncPrefectClient]

    def serialize(self):
        return self.model_dump(
            include={"start_time", "input_keyset"},
            exclude_unset=True,
        )
