from datetime import timedelta
from typing import ClassVar

from pydantic import AliasChoices, AliasPath, Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings, build_settings_config


class ServerEventsSettings(PrefectBaseSettings):
    """
    Settings for controlling behavior of the events subsystem
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(
        ("server", "events")
    )

    ###########################################################################
    # Events settings

    stream_out_enabled: bool = Field(
        default=True,
        description="Whether or not to stream events out to the API via websockets.",
        validation_alias=AliasChoices(
            AliasPath("stream_out_enabled"),
            "prefect_server_events_stream_out_enabled",
            "prefect_api_events_stream_out_enabled",
        ),
    )

    related_resource_cache_ttl: timedelta = Field(
        default=timedelta(minutes=5),
        description="The number of seconds to cache related resources for in the API.",
        validation_alias=AliasChoices(
            AliasPath("related_resource_cache_ttl"),
            "prefect_server_events_related_resource_cache_ttl",
            "prefect_api_events_related_resource_cache_ttl",
        ),
    )

    maximum_labels_per_resource: int = Field(
        default=500,
        description="The maximum number of labels a resource may have.",
        validation_alias=AliasChoices(
            AliasPath("maximum_labels_per_resource"),
            "prefect_server_events_maximum_labels_per_resource",
            "prefect_events_maximum_labels_per_resource",
        ),
    )

    maximum_related_resources: int = Field(
        default=100,
        description="The maximum number of related resources an Event may have.",
        validation_alias=AliasChoices(
            AliasPath("maximum_related_resources"),
            "prefect_server_events_maximum_related_resources",
            "prefect_events_maximum_related_resources",
        ),
    )

    maximum_size_bytes: int = Field(
        default=1_500_000,
        description="The maximum size of an Event when serialized to JSON",
        validation_alias=AliasChoices(
            AliasPath("maximum_size_bytes"),
            "prefect_server_events_maximum_size_bytes",
            "prefect_events_maximum_size_bytes",
        ),
    )

    expired_bucket_buffer: timedelta = Field(
        default=timedelta(seconds=60),
        description="The amount of time to retain expired automation buckets",
        validation_alias=AliasChoices(
            AliasPath("expired_bucket_buffer"),
            "prefect_server_events_expired_bucket_buffer",
            "prefect_events_expired_bucket_buffer",
        ),
    )

    proactive_granularity: timedelta = Field(
        default=timedelta(seconds=5),
        description="How frequently proactive automations are evaluated",
        validation_alias=AliasChoices(
            AliasPath("proactive_granularity"),
            "prefect_server_events_proactive_granularity",
            "prefect_events_proactive_granularity",
        ),
    )

    retention_period: timedelta = Field(
        default=timedelta(days=7),
        description="The amount of time to retain events in the database.",
        validation_alias=AliasChoices(
            AliasPath("retention_period"),
            "prefect_server_events_retention_period",
            "prefect_events_retention_period",
        ),
    )

    maximum_websocket_backfill: timedelta = Field(
        default=timedelta(minutes=15),
        description="The maximum range to look back for backfilling events for a websocket subscriber.",
        validation_alias=AliasChoices(
            AliasPath("maximum_websocket_backfill"),
            "prefect_server_events_maximum_websocket_backfill",
            "prefect_events_maximum_websocket_backfill",
        ),
    )

    websocket_backfill_page_size: int = Field(
        default=250,
        gt=0,
        description="The page size for the queries to backfill events for websocket subscribers.",
        validation_alias=AliasChoices(
            AliasPath("websocket_backfill_page_size"),
            "prefect_server_events_websocket_backfill_page_size",
            "prefect_events_websocket_backfill_page_size",
        ),
    )

    messaging_broker: str = Field(
        default="prefect.server.utilities.messaging.memory",
        description="Which message broker implementation to use for the messaging system, should point to a module that exports a Publisher and Consumer class.",
        validation_alias=AliasChoices(
            AliasPath("messaging_broker"),
            "prefect_server_events_messaging_broker",
            "prefect_messaging_broker",
        ),
    )

    messaging_cache: str = Field(
        default="prefect.server.utilities.messaging.memory",
        description="Which cache implementation to use for the events system. Should point to a module that exports a Cache class.",
        validation_alias=AliasChoices(
            AliasPath("messaging_cache"),
            "prefect_server_events_messaging_cache",
            "prefect_messaging_cache",
        ),
    )

    causal_ordering: str = Field(
        default="prefect.server.events.ordering.memory",
        description="Which causal ordering implementation to use for the events system. Should point to a module that exports a CausalOrdering class.",
    )

    maximum_event_name_length: int = Field(
        default=1024,
        gt=0,
        description="The maximum length of an event name.",
        validation_alias=AliasChoices(
            AliasPath("maximum_event_name_length"),
            "prefect_server_events_maximum_event_name_length",
        ),
    )
