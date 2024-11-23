from pydantic import AliasChoices, AliasPath, Field

from prefect.settings.base import PrefectBaseSettings, _build_settings_config


class EventsSettings(PrefectBaseSettings):
    """
    Settings for controlling behavior of the events subsystem
    """

    model_config = _build_settings_config(("events",))

    maximum_event_name_length: int = Field(
        default=1024,
        description="The maximum length of an event name.",
        validation_alias=AliasChoices(
            AliasPath("maximum_event_name_length"),
            "prefect_events_maximum_event_name_length",
        ),
    )
