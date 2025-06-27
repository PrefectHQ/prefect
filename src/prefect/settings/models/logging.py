from functools import partial
from pathlib import Path
from typing import Annotated, Any, ClassVar, Literal, Union

from pydantic import (
    AliasChoices,
    AliasPath,
    BeforeValidator,
    Field,
    model_validator,
)
from pydantic_settings import SettingsConfigDict
from typing_extensions import Self

from prefect.settings.base import PrefectBaseSettings, build_settings_config
from prefect.types import LogLevel, validate_set_T_from_delim_string

from ._defaults import default_logging_config_path


def max_log_size_smaller_than_batch_size(values: dict[str, Any]) -> dict[str, Any]:
    """
    Validator for settings asserting the batch size and match log size are compatible
    """
    if values["batch_size"] < values["max_log_size"]:
        raise ValueError(
            "`PREFECT_LOGGING_TO_API_MAX_LOG_SIZE` cannot be larger than"
            " `PREFECT_LOGGING_TO_API_BATCH_SIZE`"
        )
    return values


class LoggingToAPISettings(PrefectBaseSettings):
    """
    Settings for controlling logging to the API
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(
        ("logging", "to_api")
    )

    enabled: bool = Field(
        default=True,
        description="If `True`, logs will be sent to the API.",
    )

    batch_interval: float = Field(
        default=2.0,
        description="The number of seconds between batched writes of logs to the API.",
    )

    batch_size: int = Field(
        default=4_000_000,
        description="The number of logs to batch before sending to the API.",
    )

    max_log_size: int = Field(
        default=1_000_000,
        description="The maximum size in bytes for a single log.",
    )

    when_missing_flow: Literal["warn", "error", "ignore"] = Field(
        default="warn",
        description="""
        Controls the behavior when loggers attempt to send logs to the API handler from outside of a flow.
        
        All logs sent to the API must be associated with a flow run. The API log handler can
        only be used outside of a flow by manually providing a flow run identifier. Logs
        that are not associated with a flow run will not be sent to the API. This setting can
        be used to determine if a warning or error is displayed when the identifier is missing.

        The following options are available:

        - "warn": Log a warning message.
        - "error": Raise an error.
        - "ignore": Do not log a warning message or raise an error.
        """,
    )

    @model_validator(mode="after")
    def emit_warnings(self) -> Self:
        """Emits warnings for misconfiguration of logging settings."""
        values = self.model_dump()
        values = max_log_size_smaller_than_batch_size(values)
        return self


class LoggingSettings(PrefectBaseSettings):
    """
    Settings for controlling logging behavior
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(("logging",))

    level: LogLevel = Field(
        default="INFO",
        description="The default logging level for Prefect loggers.",
    )

    config_path: Path = Field(
        default_factory=default_logging_config_path,
        description="A path to a logging configuration file. Defaults to $PREFECT_HOME/logging.yml",
        validation_alias=AliasChoices(
            AliasPath("config_path"),
            "prefect_logging_config_path",
            "prefect_logging_settings_path",
        ),
    )

    extra_loggers: Annotated[
        Union[str, list[str], None],
        BeforeValidator(partial(validate_set_T_from_delim_string, type_=str)),
    ] = Field(
        default=None,
        description="Additional loggers to attach to Prefect logging at runtime.",
    )

    log_prints: bool = Field(
        default=False,
        description="If `True`, `print` statements in flows and tasks will be redirected to the Prefect logger for the given run.",
    )

    colors: bool = Field(
        default=True,
        description="If `True`, use colors in CLI output. If `False`, output will not include colors codes.",
    )

    markup: bool = Field(
        default=False,
        description="""
        Whether to interpret strings wrapped in square brackets as a style.
        This allows styles to be conveniently added to log messages, e.g.
        `[red]This is a red message.[/red]`. However, the downside is, if enabled,
        strings that contain square brackets may be inaccurately interpreted and
        lead to incomplete output, e.g.
        `[red]This is a red message.[/red]` may be interpreted as
        `[red]This is a red message.[/red]`.
        """,
    )

    to_api: LoggingToAPISettings = Field(
        default_factory=LoggingToAPISettings,
        description="Settings for controlling logging to the API",
    )
