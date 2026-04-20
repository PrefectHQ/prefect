from typing import ClassVar

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings, build_settings_config


class EventsSettings(PrefectBaseSettings):
    """
    Settings for controlling events behavior
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(("events",))

    worker_max_queue_size: int = Field(
        default=0,
        ge=0,
        description="""
        Maximum number of events that can be queued for delivery to the
        Prefect server. When the queue is full, new events are dropped with
        a warning. Set to 0 for unbounded (the default).

        Warning: setting this value too low may result in data loss as events
        will be silently dropped when the queue is full.
        """,
    )
