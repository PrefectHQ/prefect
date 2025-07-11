from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from pydantic import AliasChoices, AliasPath, Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings, build_settings_config
from prefect.types import LogLevel

from .._defaults import default_memo_store_path
from .api import ServerAPISettings
from .database import ServerDatabaseSettings
from .deployments import ServerDeploymentsSettings
from .ephemeral import ServerEphemeralSettings
from .events import ServerEventsSettings
from .flow_run_graph import ServerFlowRunGraphSettings
from .logs import ServerLogsSettings
from .services import ServerServicesSettings
from .tasks import ServerTasksSettings
from .ui import ServerUISettings


class ServerSettings(PrefectBaseSettings):
    """
    Settings for controlling server behavior
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(("server",))

    logging_level: LogLevel = Field(
        default="WARNING",
        description="The default logging level for the Prefect API server.",
        validation_alias=AliasChoices(
            AliasPath("logging_level"),
            "prefect_server_logging_level",
            "prefect_logging_server_level",
        ),
    )

    analytics_enabled: bool = Field(
        default=True,
        description="""
        When enabled, Prefect sends anonymous data (e.g. count of flow runs, package version)
        on server startup to help us improve our product.
        """,
    )

    metrics_enabled: bool = Field(
        default=False,
        description="Whether or not to enable Prometheus metrics in the API.",
        validation_alias=AliasChoices(
            AliasPath("metrics_enabled"),
            "prefect_server_metrics_enabled",
            "prefect_api_enable_metrics",
        ),
    )

    log_retryable_errors: bool = Field(
        default=False,
        description="If `True`, log retryable errors in the API and it's services.",
        validation_alias=AliasChoices(
            AliasPath("log_retryable_errors"),
            "prefect_server_log_retryable_errors",
            "prefect_api_log_retryable_errors",
        ),
    )

    register_blocks_on_start: bool = Field(
        default=True,
        description="If set, any block types that have been imported will be registered with the backend on application startup. If not set, block types must be manually registered.",
        validation_alias=AliasChoices(
            AliasPath("register_blocks_on_start"),
            "prefect_server_register_blocks_on_start",
            "prefect_api_blocks_register_on_start",
        ),
    )

    memoize_block_auto_registration: bool = Field(
        default=True,
        description="Controls whether or not block auto-registration on start",
        validation_alias=AliasChoices(
            AliasPath("memoize_block_auto_registration"),
            "prefect_server_memoize_block_auto_registration",
            "prefect_memoize_block_auto_registration",
        ),
    )

    memo_store_path: Path = Field(
        default_factory=default_memo_store_path,
        description="Path to the memo store file. Defaults to $PREFECT_HOME/memo_store.toml",
        validation_alias=AliasChoices(
            AliasPath("memo_store_path"),
            "prefect_server_memo_store_path",
            "prefect_memo_store_path",
        ),
    )

    deployment_schedule_max_scheduled_runs: int = Field(
        default=50,
        description="The maximum number of scheduled runs to create for a deployment.",
        validation_alias=AliasChoices(
            AliasPath("deployment_schedule_max_scheduled_runs"),
            "prefect_server_deployment_schedule_max_scheduled_runs",
            "prefect_deployment_schedule_max_scheduled_runs",
        ),
    )

    api: ServerAPISettings = Field(
        default_factory=ServerAPISettings,
        description="Settings for controlling API server behavior",
    )
    database: ServerDatabaseSettings = Field(
        default_factory=ServerDatabaseSettings,
        description="Settings for controlling server database behavior",
    )
    deployments: ServerDeploymentsSettings = Field(
        default_factory=ServerDeploymentsSettings,
        description="Settings for controlling server deployments behavior",
    )
    ephemeral: ServerEphemeralSettings = Field(
        default_factory=ServerEphemeralSettings,
        description="Settings for controlling ephemeral server behavior",
    )
    events: ServerEventsSettings = Field(
        default_factory=ServerEventsSettings,
        description="Settings for controlling server events behavior",
    )
    flow_run_graph: ServerFlowRunGraphSettings = Field(
        default_factory=ServerFlowRunGraphSettings,
        description="Settings for controlling flow run graph behavior",
    )
    logs: ServerLogsSettings = Field(
        default_factory=ServerLogsSettings,
        description="Settings for controlling server logs behavior",
    )
    services: ServerServicesSettings = Field(
        default_factory=ServerServicesSettings,
        description="Settings for controlling server services behavior",
    )
    tasks: ServerTasksSettings = Field(
        default_factory=ServerTasksSettings,
        description="Settings for controlling server tasks behavior",
    )
    ui: ServerUISettings = Field(
        default_factory=ServerUISettings,
        description="Settings for controlling server UI behavior",
    )
