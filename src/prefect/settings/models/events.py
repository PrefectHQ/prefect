from typing import ClassVar

from pydantic import AliasChoices, AliasPath, Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import (
    PrefectBaseSettings,
    build_settings_config,
)


class EventsSettings(PrefectBaseSettings):
    """
    Settings for controlling client-side events behavior
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(("events",))

    worker_queue_max_size: int = Field(
        default=10000,
        description=(
            "Maximum number of events that can be queued for delivery to the "
            "Prefect API. When the queue is full, new events are dropped with "
            "a warning. Set to 0 for unbounded (default behavior before this "
            "change). This prevents memory exhaustion when the API is "
            "unreachable for extended periods."
        ),
        validation_alias=AliasChoices(
            AliasPath("worker_queue_max_size"),
            "prefect_events_worker_queue_max_size",
        ),
    )
