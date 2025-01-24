"""
A class for configuring or automatically discovering settings to be used with PrefectDbtRunner.
"""

from pathlib import Path

from dbt_common.events.base_types import EventLevel
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PrefectDbtSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DBT_")

    profiles_dir: Path = Field(default=Path.home() / ".dbt")
    project_dir: Path = Field(default_factory=Path.cwd)
    log_level: EventLevel = Field(default=EventLevel.INFO)
